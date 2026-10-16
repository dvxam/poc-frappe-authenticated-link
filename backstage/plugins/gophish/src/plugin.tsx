import {
  createFrontendPlugin,
  PageBlueprint,
} from '@backstage/frontend-plugin-api';
import SecurityIcon from '@material-ui/icons/Security';
import { rootRouteRef } from './routes';

/**
 * The GoPhish page extension. In the new frontend system a page's `title` and
 * `icon` are what populate the sidebar automatically (the app's Sidebar renders
 * every page via `nav.rest()`), so this is all that's needed for the left-menu
 * item to appear.
 */
const gophishPage = PageBlueprint.make({
  params: {
    routeRef: rootRouteRef,
    path: '/gophish',
    title: 'Phishing',
    icon: <SecurityIcon />,
    loader: () =>
      import('./components/GophishPage').then(m => <m.GophishPage />),
  },
});

export const gophishPlugin = createFrontendPlugin({
  pluginId: 'gophish',
  extensions: [gophishPage],
  routes: {
    root: rootRouteRef,
  },
});
