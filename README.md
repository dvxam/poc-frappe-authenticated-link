# VIDI SI Platform - Frappe POC

Docker stack for a security-awareness platform:

| # | Component | Role | Database |
|---|-----------|------|----------|
| 1 | **GoPhish** | Simulated phishing campaigns + result tracking | SQLite (volume) |
| 2 | **Frappe LMS** | Training platform (modules/plugins, courses) | MariaDB + Redis |
| 3 | **Backstage** | Admin platform / "the link" | SQLite (volume) |
| — | **Mailpit** | Local mail catcher for testing (no real delivery) | in-memory |


> Backstage is our **own** app, built from source in [`./backstage/`](./backstage)
> (scaffold it once with `./scaffold-backstage.sh`). This is where the real
> GoPhish ↔ Frappe integration code will live. See [Backstage](#backstage).

## Getting started

```bash
cp .env.example .env          # then edit the secrets (a dev .env is already provided)
./scaffold-backstage.sh       # once: generate the Backstage app in ./backstage/
docker compose up -d          # GoPhish + Frappe + Backstage
```

> The `backstage` service builds from `./backstage/`, so it must be scaffolded
> first (the step above). See [Backstage](#backstage) for details.

Create the Frappe site **once** (manual step):

```bash
docker compose run --rm frappe-create-site
docker compose restart frappe-backend frappe-frontend
```

Access:

- GoPhish admin  → http://localhost:3333
- GoPhish phish  → http://localhost:8080
- Frappe LMS     → http://localhost:8000  (host `lms.localhost`)
- Backstage      → http://localhost:7007
- Mailpit inbox  → http://localhost:8025  (captured test emails)


## Magic login links (`vidi_integration` app)

Custom Frappe app (`./frappe-apps/vidi_integration`) that generates auto-login
links to an LMS course: click → the user is authenticated → redirected **straight
to the course's first lesson** (`/lms/courses/<course>/learn/1-1`), so there's no
"Continue Learning" click. Token is **hashed** (SHA-256) in the database, with a
**TTL** (7 days by default), **reusable** until expiry, and revocable. An external
system calls the API and sends the email itself.

> The landing target is resolved dynamically from the course outline. Pass an
> explicit `redirect_to` when minting to override it (e.g. the course overview
> `/lms/courses/<course>`).

**Build + install (once)** — overlay on top of `vidi-lms:latest`:

```bash
./build-lms-image.sh          # 1. base (if not already built)
./build-app-image.sh          # 2. overlay + vidi_integration -> vidi-lms:latest
docker compose up -d
docker compose run --rm frappe-install-app     # adds to apps.txt + installs on the site
docker compose restart frappe-backend frappe-scheduler frappe-queue frappe-websocket
```

**Generate a link** (from the CLI, or via the REST API for Backstage):

**API access (Backstage / external).** The `create_magic_link` endpoint is
protected. To call it, use an **API-only service user** (only the `Magic Link Manager` role, no desk access). Create it and
retrieve its key/secret (once):

```bash
docker compose run --rm frappe-create-service-user
# -> { "user": "svc-magic-link@vidi.local", "api_key": "...", "api_secret": "..." }
# (re-running rotates the secret)
```

Then call over HTTP:

```bash
curl -X POST http://localhost:8000/api/method/vidi_integration.api.create_magic_link \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"user":"learner@vidi.local","course":"<course-name>","ttl_days":7}'
```

Open `magic_url` in a private window → you land **logged in** on the course.


## Local email testing (Mailpit)

GoPhish has **no built-in mail transport** — it relays through an SMTP server defined
in a **Sending Profile**. For local testing the stack ships **Mailpit**, a mail catcher
that accepts SMTP and shows every message in a web inbox but **delivers nothing
externally** — no message can reach a real mailbox, whatever recipient you use.

Mailpit runs automatically with `docker compose up -d`. Inbox UI → http://localhost:8025.

Create the Sending Profile **once**, in the GoPhish admin UI
(http://localhost:3333 → **Sending Profiles → New Profile**):

| Field | Value |
|-------|-------|
| Name | `Local Mailpit` |
| From | `security-training@vidi.local` (anything) |
| Host | `mailpit:1025` |
| Username / Password | *(leave blank)* |

Leave "Ignore Certificate Errors" unchecked (Mailpit uses plain SMTP, no TLS). Click
**Send Test Email**, then open http://localhost:8025 to confirm it arrived. Campaigns
then send to Mailpit and nowhere else (use test recipients like `alice@vidi.local`).

> Ports are configurable via `MAILPIT_UI_PORT` / `MAILPIT_SMTP_PORT` in `.env`.
> GoPhish reaches Mailpit in-network at `mailpit:1025`.


## Create a user

```bash
docker compose exec frappe-backend \
  bench --site lms.localhost add-system-manager admin@vidi.local \
    --first-name Admin --password 'VidiAdmin123!'
```


## Things to know

**GoPhish** — SQLite database (`config/gophish/config.json` → `db_name: sqlite3`),
persisted in the `gophish-data` volume (file `/opt/gophish/data/gophish.db`).

**Frappe** — `FRAPPE_IMAGE` must point to an image that contains the `lms` app.
If `frappe/lms:latest` doesn't work, build an image with
[frappe_docker](https://github.com/frappe/frappe_docker) via `apps.json` and your
own plugins/courses, then update `.env`.

**Frappe LMS** — the published `ghcr.io/frappe/lms:*` images (tested `stable` and
`v2.65.0`) only contain the `frappe` app, not `lms` (`ls apps` → `frappe` only).
So you must **build a custom image** with the app baked in:

```bash
./build-lms-image.sh                         # -> local image vidi-lms:latest
# verify:
docker run --rm --entrypoint bash vidi-lms:latest -lc 'ls -1 apps; python -c "import lms"'
# then in .env:  FRAPPE_IMAGE=vidi-lms:latest
docker compose up -d
docker compose run --rm frappe-create-site
```

The script clones [frappe_docker](https://github.com/frappe/frappe_docker) and
builds via `apps.json` (passed as a BuildKit secret), the official method
described here:
[docs/02-setup/02-build-setup.md](https://github.com/frappe/frappe_docker/blob/main/docs/02-setup/02-build-setup.md).
This is also where you add your own plugins/courses (add their repos to the
`apps.json` in `build-lms-image.sh`).

<a name="backstage"></a>
**Backstage** — our **own** app, scaffolded into `./backstage/` and built from
source (no third-party demo image). The host needs no Node toolchain: scaffolding
and building both run in Docker.

```bash
./scaffold-backstage.sh                 # once: generates ./backstage/ (owned, committed)
docker compose up -d --build backstage  # build + run (first build is slow: full yarn + tsc)
docker compose logs -f backstage        # wait for the backend listening on :7007
# -> http://localhost:7007  (sign in as "Guest")
```

- **Database:** persistent SQLite in the `backstage-data` volume (`/data`), one
  file per plugin. State survives restarts.
- **Auth:** guest sign-in, enabled via `dangerouslyAllowOutsideDevelopment` in
  `backstage/app-config.production.yaml`. **POC only** — Backstage's guest
  provider is not meant for real deployments; swap in a real auth provider before
  going beyond local use.
- **Customize:** edit `backstage/packages/app` (frontend) / `packages/backend`,
  or add plugins under `backstage/plugins/`, then rebuild with
  `docker compose up -d --build backstage`.
- Build-time **and** runtime use `node:24-trixie-slim` (`backstage/Dockerfile`);
  keep them in sync or the `better-sqlite3` native module fails at runtime.

### GoPhish stats plugin

`backstage/plugins/gophish` — a frontend plugin (new frontend system) that adds a
**Phishing** item to the left menu. The page lists GoPhish campaigns; selecting
one shows its stats (recipients, sent, opened, clicked, submitted data, reported,
errors) **and the list of users who clicked** the link — email, name, status,
click time, and IP (derived from the campaign's per-recipient results + timeline).

- Calls go through the **Backstage proxy** (`proxy.endpoints./gophish` in
  `app-config.yaml` → `http://gophish:3333`), which injects the API key
  **server-side** — it never reaches the browser, and there's no CORS.
- Set `GOPHISH_API_KEY` in `.env` first: log in to GoPhish, go to
  **Settings → API key**, copy it. The `backstage` service passes it through.
- After editing plugin code, the committed `yarn.lock` must cover any new
  package, so re-run the in-place install (below) before rebuilding.

```bash
# 1. regenerate the lockfile in place (needed after adding/removing a package)
docker run --rm -v "$PWD/backstage":/app -w /app node:24-trixie-slim \
  bash -lc 'corepack enable && yarn install --mode=skip-build && chown -R '"$(id -u)":"$(id -g)"' /app'
# 2. rebuild + run
docker compose up -d --build backstage
```

#### "Send training email" button

Each clicker row has a **Send training email** button. It calls the backend
plugin `backstage/plugins/gophish-backend`
(`POST /api/gophish/send-training-email`), which:

1. mints a Frappe **magic login link** for that user, pointing at the course
   `a-guide-to-frappe-learning` (configurable in `app-config.yaml` →
   `gophish.training.course`), authenticating as the least-privilege service user;
2. renders `email-templates/education-email.html`, replacing `{{TRAINING_LINK}}`
   with the magic link (the template is mounted read-only, so you can edit it
   without rebuilding Backstage);
3. sends the email over SMTP to **Mailpit** — view it at http://localhost:8025.

The magic link's host is rewritten to `gophish.training.lmsPublicUrl`
(`http://localhost:8000`) so it resolves from the recipient's browser.

**Prerequisites** (one-time):

```bash
# Provision the Frappe service user and copy its key/secret into .env
docker compose run --rm frappe-create-service-user
#   -> set FRAPPE_API_KEY / FRAPPE_API_SECRET in .env
```

Also make sure the target **user exists** in Frappe (magic links require a
pre-existing, enabled user) and the **course `a-guide-to-frappe-learning`
exists** in the LMS. The Frappe/SMTP credentials and template path live
server-side (`gophish.training.*` in `app-config.yaml`); they never reach the
browser.

