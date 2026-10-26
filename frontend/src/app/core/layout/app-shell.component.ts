import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { SidebarComponent } from './sidebar.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [CommonModule, RouterOutlet, SidebarComponent],
  template: `
    <div class="app-shell" [class.sidebar-collapsed]="sidebarCollapsed()">
      <app-sidebar (collapsedChange)="onSidebarCollapse($event)" />

      <main class="main-content">
        <router-outlet />
      </main>
    </div>
  `,
  styles: [`
    .app-shell {
      min-height: 100vh;
      background: var(--bg-atmosphere);
    }

    .main-content {
      margin-left: var(--sidebar-width-expanded);
      min-height: 100vh;
      transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .app-shell.sidebar-collapsed .main-content {
      margin-left: var(--sidebar-width-collapsed);
    }
  `]
})
export class AppShellComponent {
  sidebarCollapsed = signal(false);

  onSidebarCollapse(collapsed: boolean): void {
    this.sidebarCollapsed.set(collapsed);
  }
}
