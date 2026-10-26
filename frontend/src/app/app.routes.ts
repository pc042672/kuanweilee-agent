import { Routes } from '@angular/router';
import { authGuard, publicGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'workspace',
    pathMatch: 'full'
  },
  {
    path: 'login',
    canActivate: [publicGuard],
    loadComponent: () => import('./core/auth/login.component').then(m => m.LoginComponent)
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./core/layout/app-shell.component').then(m => m.AppShellComponent),
    children: [
      // Workspace (Chat-centric)
      {
        path: 'workspace',
        loadComponent: () => import('./features/workspace/workspace.component').then(m => m.WorkspaceComponent)
      },
      {
        path: 'workspace/chat/:sessionId',
        loadComponent: () => import('./features/workspace/workspace.component').then(m => m.WorkspaceComponent)
      },
      // Plans
      {
        path: 'plans',
        loadComponent: () => import('./features/plans/plan-list.component').then(m => m.PlanListComponent)
      },
      {
        path: 'plans/new',
        loadComponent: () => import('./features/plans/plan-editor.component').then(m => m.PlanEditorComponent)
      },
      {
        path: 'plans/:id',
        loadComponent: () => import('./features/plans/plan-editor.component').then(m => m.PlanEditorComponent)
      },
      // Ontology / Rules / Strategy — one editor, route-driven mode
      {
        path: 'ontology',
        data: { mode: 'structure' },
        loadComponent: () => import('./features/settings/ontology-v2-settings.component').then(m => m.OntologyV2SettingsComponent)
      },
      {
        path: 'rules',
        data: { mode: 'rules' },
        loadComponent: () => import('./features/settings/ontology-v2-settings.component').then(m => m.OntologyV2SettingsComponent)
      },
      {
        path: 'strategies',
        data: { mode: 'strategy' },
        loadComponent: () => import('./features/settings/ontology-v2-settings.component').then(m => m.OntologyV2SettingsComponent)
      },
      // Integrations — data sources + external service credentials
      {
        path: 'integrations',
        loadComponent: () => import('./features/settings/integrations-settings.component').then(m => m.IntegrationsSettingsComponent)
      },
      // Legacy redirects
      { path: 'ontology-settings', redirectTo: 'ontology' },
      { path: 'labels', redirectTo: 'strategies' },
      // Help page (placeholder)
      {
        path: 'help',
        loadComponent: () => import('./features/help/help.component').then(m => m.HelpComponent)
      },
      { path: 'settings', redirectTo: 'ontology' },
      { path: 'settings/ontology', redirectTo: 'ontology' },
      { path: 'settings/labels', redirectTo: 'strategies' },
      {
        path: 'chat',
        redirectTo: 'workspace'
      }
    ]
  },
  {
    path: '**',
    redirectTo: 'workspace'
  }
];
