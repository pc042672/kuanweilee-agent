import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-settings-shell',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="settings-container">
      <aside class="settings-nav glass-card">
        <h2>Settings</h2>
        <nav>
          <a routerLink="ontology" routerLinkActive="active">
            <i class="pi pi-sitemap"></i>
            <span>Ontology</span>
          </a>
          <a routerLink="labels" routerLinkActive="active">
            <i class="pi pi-tags"></i>
            <span>Label Rules</span>
          </a>
        </nav>
      </aside>

      <main class="settings-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: [`
    .settings-container {
      display: grid;
      grid-template-columns: 240px 1fr;
      gap: var(--spacing-6);
      height: 100%;
      padding: var(--spacing-6);
    }

    .settings-nav {
      padding: var(--spacing-5);
      height: fit-content;
      position: sticky;
      top: var(--spacing-6);

      h2 {
        font-size: var(--font-size-lg);
        font-weight: var(--font-weight-semibold);
        color: var(--surface-700);
        margin: 0 0 var(--spacing-4) 0;
        padding-bottom: var(--spacing-3);
        border-bottom: 1px solid var(--surface-200);
      }

      nav {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-1);
      }

      a {
        display: flex;
        align-items: center;
        gap: var(--spacing-3);
        padding: var(--spacing-3) var(--spacing-4);
        border-radius: 10px;
        text-decoration: none;
        color: var(--surface-600);
        font-size: var(--font-size-sm);
        font-weight: var(--font-weight-medium);
        transition: all 0.2s ease;

        &:hover {
          background: var(--glass-overlay);
          color: var(--primary-700);
        }

        &.active {
          background: rgba(124, 58, 237, 0.1);
          color: var(--primary-700);
        }

        i {
          font-size: 1rem;
          width: 20px;
        }
      }
    }

    .settings-content {
      flex: 1;
      min-width: 0;
    }
  `]
})
export class SettingsShellComponent {}
