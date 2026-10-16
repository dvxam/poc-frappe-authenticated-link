import { createFrontendModule } from '@backstage/frontend-plugin-api';
import { HomePageWidgetBlueprint } from '@backstage/plugin-home-react/alpha';
import { VidiQuickLinks } from './VidiQuickLinks';

// Quick-link cards to the platform components. The `name` ("VidiQuickLinks")
// must match the `component` referenced in app-config.yaml (page:home defaultConfig).
const quickLinksWidget = HomePageWidgetBlueprint.make({
  name: 'vidi-quick-links',
  params: {
    name: 'VidiQuickLinks',
    title: 'Platform components',
    description: 'Quick links to GoPhish, the LMS, Mailpit and the phishing stats',
    components: async () => ({
      Content: VidiQuickLinks,
    }),
  },
});

export const homeModule = createFrontendModule({
  pluginId: 'home',
  extensions: [quickLinksWidget],
});
