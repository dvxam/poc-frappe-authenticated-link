import {
  LoggerService,
  RootConfigService,
} from '@backstage/backend-plugin-api';
import express from 'express';
import Router from 'express-promise-router';
import { createTransport } from 'nodemailer';
import { readFile } from 'node:fs/promises';

/** Placeholder replaced in the email template with the per-user magic link. */
const LINK_PLACEHOLDER = '{{TRAINING_LINK}}';

export interface RouterOptions {
  logger: LoggerService;
  config: RootConfigService;
}

/** Read the `gophish.training` settings. Done lazily (per request) so a missing
 *  or malformed config never prevents the plugin from starting — it surfaces as
 *  a clear HTTP error instead. */
function readSettings(config: RootConfigService) {
  const t = config.getConfig('gophish.training');
  return {
    course: t.getOptionalString('course') ?? 'a-guide-to-frappe-learning',
    // Exact landing path; overrides the course's first lesson when set.
    redirectTo: t.getOptionalString('redirectTo'),
    frappeUrl: t.getString('frappeUrl').replace(/\/+$/, ''),
    lmsPublicUrl: t.getOptionalString('lmsPublicUrl')?.replace(/\/+$/, ''),
    // Secrets come from env directly, not Backstage config: an unset/empty
    // ${FRAPPE_API_KEY} makes config.getString throw ("got empty-string"),
    // and process.env tolerates an empty value (handled below as "not set").
    apiKey: process.env.FRAPPE_API_KEY ?? '',
    apiSecret: process.env.FRAPPE_API_SECRET ?? '',
    templatePath:
      t.getOptionalString('templatePath') ??
      '/email-templates/education-email.html',
    from:
      t.getOptionalString('from') ??
      'Security Awareness <security-awareness@vidi.local>',
    subject:
      t.getOptionalString('subject') ??
      'Formation sécurité obligatoire — simulation de phishing',
    smtpHost: t.getOptionalString('smtp.host') ?? 'mailpit',
    smtpPort: t.getOptionalNumber('smtp.port') ?? 1025,
  };
}

/**
 * Backend for the "send a training email" button. On POST it:
 *   1. mints a magic login link in Frappe (as the least-privilege service user),
 *   2. renders the email template with that link,
 *   3. sends it over SMTP (Mailpit in dev).
 *
 * The Frappe API key/secret and SMTP live here, server-side — never in the browser.
 */
export async function createRouter({
  logger,
  config,
}: RouterOptions): Promise<express.Router> {
  const router = Router();
  router.use(express.json());

  router.get('/health', (_req, res) => {
    res.json({ status: 'ok' });
  });

  router.post('/send-training-email', async (req, res) => {
    const email = String(req.body?.email ?? '').trim();
    if (!email) {
      res.status(400).json({ error: 'email is required' });
      return;
    }

    let s: ReturnType<typeof readSettings>;
    try {
      s = readSettings(config);
    } catch (e) {
      logger.error(`gophish.training config error: ${(e as Error).message}`);
      res
        .status(500)
        .json({ error: `Config error: ${(e as Error).message}` });
      return;
    }

    if (!s.apiKey || !s.apiSecret) {
      res.status(400).json({
        error:
          'Frappe service credentials are not set. Provision them with ' +
          '`docker compose run --rm frappe-create-service-user` and put ' +
          'FRAPPE_API_KEY / FRAPPE_API_SECRET in .env.',
      });
      return;
    }

    // 1. Mint the magic link in Frappe (authenticated as the service user).
    let mintRes: Response;
    try {
      mintRes = await fetch(
        `${s.frappeUrl}/api/method/vidi_integration.api.create_magic_link`,
        {
          method: 'POST',
          headers: {
            Authorization: `token ${s.apiKey}:${s.apiSecret}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user: email,
            course: s.course,
            ...(s.redirectTo ? { redirect_to: s.redirectTo } : {}),
          }),
        },
      );
    } catch (e) {
      logger.error(`Cannot reach Frappe at ${s.frappeUrl}: ${e}`);
      res
        .status(502)
        .json({ error: `Cannot reach Frappe at ${s.frappeUrl}: ${e}` });
      return;
    }
    if (!mintRes.ok) {
      const detail = (await mintRes.text()).slice(0, 300);
      logger.error(
        `create_magic_link failed for ${email}: ${mintRes.status} ${detail}`,
      );
      res.status(502).json({
        error: `Frappe create_magic_link failed (${mintRes.status})`,
        detail,
      });
      return;
    }
    // Frappe wraps whitelisted return values in { message: ... }.
    const mint = ((await mintRes.json()) as any)?.message ?? {};
    const rawUrl: string | undefined = mint.magic_url;
    if (!rawUrl) {
      res.status(502).json({ error: 'Frappe did not return a magic_url' });
      return;
    }

    // Rewrite the host to the public LMS origin so the link works from the
    // user's browser (keep Frappe's path + token query intact).
    let trainingLink = rawUrl;
    if (s.lmsPublicUrl) {
      const u = new URL(rawUrl);
      trainingLink = `${s.lmsPublicUrl}${u.pathname}${u.search}`;
    }

    // 2. Render the template.
    let html: string;
    try {
      html = await readFile(s.templatePath, 'utf8');
    } catch (e) {
      logger.error(`Cannot read email template at ${s.templatePath}: ${e}`);
      res
        .status(500)
        .json({ error: `Email template not found at ${s.templatePath}` });
      return;
    }
    html = html.split(LINK_PLACEHOLDER).join(trainingLink);

    // 3. Send it.
    try {
      const mailer = createTransport({
        host: s.smtpHost,
        port: s.smtpPort,
        secure: false,
      });
      await mailer.sendMail({ from: s.from, to: email, subject: s.subject, html });
    } catch (e) {
      logger.error(`SMTP send to ${email} failed: ${e}`);
      res.status(502).json({ error: `SMTP send failed: ${e}` });
      return;
    }
    logger.info(`Training email sent to ${email} (course=${s.course})`);

    res.json({
      ok: true,
      email,
      course: s.course,
      magic_url: trainingLink,
      expires_on: mint.expires_on,
    });
  });

  return router;
}
