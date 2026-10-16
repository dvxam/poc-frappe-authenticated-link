import {
  coreServices,
  createBackendPlugin,
} from '@backstage/backend-plugin-api';
import { createRouter } from './service/router';

/**
 * Backend plugin `gophish` — exposes POST /api/gophish/send-training-email.
 * Shares the `gophish` plugin id with the frontend plugin so the frontend can
 * reach it via `discoveryApi.getBaseUrl('gophish')`.
 */
export const gophishBackendPlugin = createBackendPlugin({
  pluginId: 'gophish',
  register(env) {
    env.registerInit({
      deps: {
        logger: coreServices.logger,
        config: coreServices.rootConfig,
        httpRouter: coreServices.httpRouter,
      },
      async init({ logger, config, httpRouter }) {
        httpRouter.use(await createRouter({ logger, config }));
        // POC: the app runs on guest auth; allow the button to call this
        // without token plumbing. Tighten once real auth is in place.
        httpRouter.addAuthPolicy({
          path: '/send-training-email',
          allow: 'unauthenticated',
        });
        httpRouter.addAuthPolicy({ path: '/health', allow: 'unauthenticated' });
      },
    });
  },
});
