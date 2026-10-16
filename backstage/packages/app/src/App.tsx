import { createApp } from '@backstage/frontend-defaults';
import catalogPlugin from '@backstage/plugin-catalog/alpha';
import gophishPlugin from '@internal/plugin-gophish';
import { navModule } from './modules/nav';
import { homeModule } from './modules/home';

export default createApp({
  features: [catalogPlugin, gophishPlugin, navModule, homeModule],
});
