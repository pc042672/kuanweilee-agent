import { Component, signal, computed, output, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';
import { AuthService } from '../../shared/services/auth.service';
import { ChatSession, ChatSessionService } from '../../shared/services/chat-session.service';

interface NavItem {
  label: string;
  icon: string;
  route?: string;
  children?: NavItem[];
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, ButtonModule, TooltipModule],
  template: `
    <aside class="sidebar" [class.collapsed]="collapsed()">
      <!-- Header -->
      <div class="sidebar-header">
        <button class="toggle-btn" (click)="toggleCollapse()">
          <i class="pi" [class.pi-bars]="collapsed()" [class.pi-times]="!collapsed()"></i>
        </button>
        @if (!collapsed()) {
          <span class="logo-text">AICDP</span>
        }
      </div>

      <!-- Navigation -->
      <nav class="sidebar-nav">
        @if (!collapsed()) {
          <!-- Settings Section -->
          <div class="nav-section">
            <button
              class="section-header"
              [class.expanded]="settingsExpanded()"
              (click)="toggleSettings()"
            >
              <i class="pi pi-cog"></i>
              <span>Settings</span>
              <i class="pi pi-chevron-down chevron"></i>
            </button>
            @if (settingsExpanded()) {
              <div class="section-children">
                <button
                  class="nav-item"
                  [class.active]="isActive('/ontology')"
                  (click)="navigateTo('/ontology')"
                >
                  <i class="pi pi-sitemap"></i>
                  <span>Ontology</span>
                </button>
                <button
                  class="nav-item"
                  [class.active]="isActive('/rules')"
                  (click)="navigateTo('/rules')"
                >
                  <i class="pi pi-sliders-h"></i>
                  <span>Rules</span>
                </button>
                <button
                  class="nav-item"
                  [class.active]="isActive('/strategies')"
                  (click)="navigateTo('/strategies')"
                >
                  <i class="pi pi-bolt"></i>
                  <span>Strategy</span>
                </button>
                <button
                  class="nav-item"
                  [class.active]="isActive('/integrations')"
                  (click)="navigateTo('/integrations')"
                >
                  <i class="pi pi-link"></i>
                  <span>Integrations</span>
                </button>
                <button
                  class="nav-item"
                  [class.active]="isActive('/help')"
                  (click)="navigateTo('/help')"
                >
                  <i class="pi pi-question-circle"></i>
                  <span>Help</span>
                </button>
              </div>
            }
          </div>

          <!-- Workspace Section -->
          <div class="nav-section">
            <button
              class="section-header"
              [class.expanded]="workspaceExpanded()"
              (click)="toggleWorkspace()"
            >
              <i class="pi pi-th-large"></i>
              <span>Workspace</span>
              <i class="pi pi-chevron-down chevron"></i>
            </button>
            @if (workspaceExpanded()) {
              <div class="section-children">
                <button
                  class="nav-item"
                  [class.active]="isActive('/plans')"
                  (click)="navigateTo('/plans')"
                >
                  <i class="pi pi-list"></i>
                  <span>Plans</span>
                </button>
                <button
                  class="nav-item"
                  [class.active]="isActive('/workspace')"
                  (click)="onAnalysisClick()"
                >
                  <i class="pi pi-comments"></i>
                  <span>Analysis</span>
                </button>

                <!-- Divider -->
                <div class="nav-divider"></div>

                <!-- Chat History -->
                @if (allSessions().length > 0) {
                  <div class="chat-history">
                    @if (starredSessions().length > 0) {
                      <div class="section-label">Starred</div>
                      @for (session of starredSessions(); track session.id) {
                        <button
                          class="chat-item"
                          [class.active]="isActiveSession(session.id)"
                          (click)="selectSession(session)"
                        >
                          <i class="pi pi-star-fill starred-icon"></i>
                          <span class="chat-title">{{ session.title }}</span>
                        </button>
                      }
                    }

                    @if (recentSessions().length > 0) {
                      <div class="section-label">Recents</div>
                      @for (session of recentSessions(); track session.id) {
                        <button
                          class="chat-item"
                          [class.active]="isActiveSession(session.id)"
                          (click)="selectSession(session)"
                        >
                          <span class="chat-title">{{ session.title }}</span>
                        </button>
                      }
                    }
                  </div>
                }
              </div>
            }
          </div>
        } @else {
          <!-- Collapsed state -->
          <button
            class="nav-icon"
            [class.active]="isActive('/ontology') || isActive('/rules') || isActive('/strategies') || isActive('/integrations') || isActive('/help')"
            pTooltip="Settings"
            tooltipPosition="right"
            (click)="toggleSettings()"
          >
            <i class="pi pi-cog"></i>
          </button>
          <button
            class="nav-icon"
            [class.active]="isActive('/workspace') || isActive('/plans')"
            pTooltip="Workspace"
            tooltipPosition="right"
            (click)="navigateTo('/workspace')"
          >
            <i class="pi pi-th-large"></i>
          </button>
          <button
            class="nav-icon"
            pTooltip="New Chat"
            tooltipPosition="right"
            (click)="onNewChat()"
          >
            <i class="pi pi-plus"></i>
          </button>
        }
      </nav>

      <!-- Footer -->
      <div class="sidebar-footer">
        <div class="user-card" [class.collapsed]="collapsed()">
          <div class="user-avatar">
            <span>{{ userInitials() }}</span>
          </div>
          @if (!collapsed()) {
            <div class="user-info">
              <span class="user-name">{{ userName() }}</span>
              <button class="logout-btn" (click)="onLogout()">Logout</button>
            </div>
          } @else {
            <button
              class="logout-icon-btn"
              (click)="onLogout()"
              pTooltip="Logout"
              tooltipPosition="right"
            >
              <i class="pi pi-sign-out"></i>
            </button>
          }
        </div>
      </div>
    </aside>
  `,
  styles: [`
    .sidebar {
      position: fixed;
      left: 0;
      top: 0;
      height: 100vh;
      width: var(--sidebar-width-expanded);
      background: var(--surface-0, #ffffff);
      border-right: 1px solid var(--surface-200, #e4e4e7);
      display: flex;
      flex-direction: column;
      transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      z-index: 100;

      &.collapsed {
        width: var(--sidebar-width-collapsed);

        .sidebar-header {
          justify-content: center;
        }
      }
    }

    .sidebar-header {
      display: flex;
      align-items: center;
      gap: var(--spacing-3);
      padding: var(--spacing-4);
      height: var(--header-height);
    }

    .toggle-btn {
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      border-radius: 10px;
      cursor: pointer;
      color: var(--surface-600, #52525b);
      transition: all 0.2s ease;

      &:hover {
        background: rgba(124, 58, 237, 0.08);
        color: var(--primary-700, #7c3aed);
      }

      i {
        font-size: 1.25rem;
      }
    }

    .logo-text {
      font-size: var(--font-size-xl);
      font-weight: var(--font-weight-bold);
      background: linear-gradient(135deg, var(--primary-700, #7c3aed), var(--primary-500, #a78bfa));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    /* Navigation */
    .sidebar-nav {
      flex: 1;
      overflow-y: auto;
      padding: var(--spacing-2) var(--spacing-3);
      display: flex;
      flex-direction: column;
    }

    .nav-section {
      margin-bottom: var(--spacing-2);
    }

    .section-header {
      width: 100%;
      display: flex;
      align-items: center;
      gap: var(--spacing-2);
      padding: 10px 12px;
      background: transparent;
      border: none;
      border-radius: 8px;
      font-size: var(--font-size-sm);
      font-weight: var(--font-weight-medium);
      color: var(--text-color, #3f3f46);
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        background: var(--surface-100, #f4f4f5);
      }

      &.expanded {
        color: var(--primary-700, #7c3aed);
      }

      i:first-child {
        font-size: 1.125rem;
        width: 20px;
      }

      span {
        flex: 1;
        text-align: left;
      }

      .chevron {
        font-size: 0.75rem;
        transition: transform 0.2s ease;
      }

      &.expanded .chevron {
        transform: rotate(180deg);
      }
    }

    .section-children {
      margin-top: var(--spacing-1);
      padding-left: var(--spacing-4);
    }

    .nav-item {
      width: 100%;
      display: flex;
      align-items: center;
      gap: var(--spacing-2);
      padding: 8px 12px;
      background: transparent;
      border: none;
      border-radius: 8px;
      font-size: var(--font-size-sm);
      color: var(--text-color-secondary, #71717a);
      text-align: left;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        background: var(--surface-100, #f4f4f5);
        color: var(--text-color, #3f3f46);
      }

      &.active {
        background: rgba(124, 58, 237, 0.08);
        color: var(--primary-700, #7c3aed);
      }

      i {
        font-size: 1rem;
        width: 18px;
      }
    }

    /* Divider between nav items and chat history */
    .nav-divider {
      height: 1px;
      background: linear-gradient(
        90deg,
        transparent 0%,
        var(--surface-200, #e4e4e7) 20%,
        var(--surface-200, #e4e4e7) 80%,
        transparent 100%
      );
      margin: var(--spacing-3) 0;
    }

    .nav-icon {
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      border-radius: 10px;
      color: var(--text-color-secondary, #71717a);
      cursor: pointer;
      margin: 0 auto var(--spacing-2);
      transition: all 0.2s ease;

      &:hover {
        background: var(--surface-100, #f4f4f5);
        color: var(--text-color, #3f3f46);
      }

      &.active {
        background: rgba(124, 58, 237, 0.08);
        color: var(--primary-700, #7c3aed);
      }

      i {
        font-size: 1.25rem;
      }
    }

    /* Chat History */
    .chat-history {
      margin-top: var(--spacing-1);
      padding-left: var(--spacing-3);
    }

    .section-label {
      font-size: 10px;
      font-weight: var(--font-weight-medium);
      color: var(--text-color-secondary, #71717a);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: var(--spacing-2) var(--spacing-2) var(--spacing-1);
    }

    .chat-item {
      width: 100%;
      display: flex;
      align-items: center;
      gap: var(--spacing-2);
      padding: 6px 12px;
      background: transparent;
      border: none;
      border-radius: 6px;
      font-size: var(--font-size-xs);
      color: var(--text-color-secondary, #71717a);
      text-align: left;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        background: var(--surface-100, #f4f4f5);
        color: var(--text-color, #3f3f46);
      }

      &.active {
        background: rgba(124, 58, 237, 0.08);
        color: var(--primary-700, #7c3aed);
      }

      .starred-icon {
        font-size: 0.5rem;
        color: var(--warning-color, #f59e0b);
      }

      .chat-title {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    /* Footer */
    .sidebar-footer {
      padding: var(--spacing-3);
      border-top: 1px solid var(--surface-200, #e4e4e7);
    }

    .user-card {
      display: flex;
      align-items: center;
      gap: var(--spacing-3);
      padding: var(--spacing-3);
      background: var(--surface-50, #fafafa);
      border-radius: 12px;

      &.collapsed {
        flex-direction: column;
        padding: var(--spacing-2);
        gap: var(--spacing-2);
      }
    }

    .user-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--primary-700, #7c3aed), var(--primary-500, #a78bfa));
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: var(--font-size-sm);
      font-weight: var(--font-weight-semibold);
      flex-shrink: 0;
    }

    .user-info {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .user-name {
      font-size: var(--font-size-sm);
      font-weight: var(--font-weight-medium);
      color: var(--text-color, #3f3f46);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .logout-btn {
      background: none;
      border: none;
      padding: 0;
      font-size: var(--font-size-xs);
      color: var(--text-color-secondary, #71717a);
      cursor: pointer;
      text-align: left;

      &:hover {
        color: var(--error-color, #ef4444);
      }
    }

    .logout-icon-btn {
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      color: var(--text-color-secondary, #71717a);
      transition: all 0.2s ease;

      &:hover {
        background: rgba(239, 68, 68, 0.1);
        color: var(--error-color, #ef4444);
      }
    }
  `]
})
export class SidebarComponent implements OnInit {
  collapsed = signal(false);
  collapsedChange = output<boolean>();
  newChat = output<void>();
  sessionSelected = output<ChatSession>();

  settingsExpanded = signal(false);
  workspaceExpanded = signal(true);

  private authService = inject(AuthService);
  private chatSessionService = inject(ChatSessionService);
  private router = inject(Router);

  allSessions = this.chatSessionService.getSessions();

  starredSessions = computed(() =>
    this.allSessions().filter(s => s.starred === true).slice(0, 5)
  );

  recentSessions = computed(() =>
    this.allSessions()
      .filter(s => !s.starred)
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
      .slice(0, 10)
  );

  userName = computed(() => {
    const user = this.authService.currentUser();
    return user?.name || 'User';
  });

  userInitials = computed(() => {
    const name = this.userName();
    const parts = name.split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  });

  currentSessionId = signal<string | null>(null);

  ngOnInit(): void {
    // Sessions are loaded automatically by the service constructor
  }

  toggleCollapse(): void {
    this.collapsed.update(v => !v);
    this.collapsedChange.emit(this.collapsed());
  }

  toggleSettings(): void {
    this.settingsExpanded.update(v => !v);
  }

  toggleWorkspace(): void {
    this.workspaceExpanded.update(v => !v);
  }

  navigateTo(route: string): void {
    this.router.navigate([route]);
  }

  isActive(route: string): boolean {
    if (route === '/workspace') {
      return this.router.url === '/workspace' || this.router.url.startsWith('/workspace/chat');
    }
    return this.router.url.startsWith(route);
  }

  onAnalysisClick(): void {
    // Navigate to workspace - creates new chat if no sessions exist
    this.router.navigate(['/workspace']);
  }

  onNewChat(): void {
    this.newChat.emit();
    this.router.navigate(['/workspace']);
  }

  selectSession(session: ChatSession): void {
    this.currentSessionId.set(session.id);
    this.sessionSelected.emit(session);
    this.router.navigate(['/workspace/chat', session.id]);
  }

  isActiveSession(sessionId: string): boolean {
    return this.currentSessionId() === sessionId ||
      this.router.url.includes(sessionId);
  }

  onLogout(): void {
    this.authService.logout();
  }
}
