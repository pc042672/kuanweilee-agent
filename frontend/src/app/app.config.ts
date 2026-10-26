import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { authInterceptor } from './shared/auth.interceptor';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { providePrimeNG } from 'primeng/config';
import { provideCopilotKit } from '@copilotkitnext/angular';
import { HttpAgent } from '@ag-ui/client';
import Aura from '@primeuix/themes/aura';
import { routes } from './app.routes';

const backendAgent = new HttpAgent({
  url: '/ag-ui',
  agentId: 'revive_ai'
});

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAnimationsAsync(),
    providePrimeNG({
      theme: {
        preset: Aura,
        options: { darkModeSelector: '.dark-mode' }
      }
    }),
    provideCopilotKit({
      agents: {
        'revive_ai': backendAgent
      }
    })
  ]
};
