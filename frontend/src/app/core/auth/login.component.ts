import { Component, ElementRef, ViewChild, AfterViewInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../shared/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="login-page">
      <div class="login-card glass-card">
        <div class="login-header">
          <div class="logo-icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <defs>
                <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#7c3aed"/>
                  <stop offset="100%" stop-color="#a78bfa"/>
                </linearGradient>
              </defs>
              <rect width="48" height="48" rx="12" fill="url(#logoGradient)"/>
              <path d="M24 12L32 18V30L24 36L16 30V18L24 12Z" stroke="white" stroke-width="2" fill="none"/>
              <circle cx="24" cy="24" r="4" fill="white"/>
            </svg>
          </div>
          <h1>AICDP</h1>
          <p>AI-Powered CDP Platform</p>
        </div>

        <div class="google-signin">
          <div #googleBtn></div>
        </div>

        @if (error()) {
          <div class="error-message">{{ error() }}</div>
        }

        <div class="login-footer">
          <p>&copy; 2025 AICDP. All rights reserved.</p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .login-page {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-atmosphere);
      padding: var(--spacing-4);
    }

    .login-card {
      width: 100%;
      max-width: 420px;
      padding: var(--spacing-8);
    }

    .login-header {
      text-align: center;
      margin-bottom: var(--spacing-8);

      .logo-icon { margin-bottom: var(--spacing-4); }

      h1 {
        font-size: var(--font-size-3xl);
        font-weight: var(--font-weight-bold);
        color: var(--surface-900);
        margin: 0 0 var(--spacing-2) 0;
        background: linear-gradient(135deg, var(--primary-700), var(--primary-500));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }

      p {
        font-size: var(--font-size-sm);
        color: var(--surface-500);
        margin: 0;
      }
    }

    .google-signin {
      display: flex;
      justify-content: center;
      margin-bottom: var(--spacing-6);
    }

    .error-message {
      padding: var(--spacing-3);
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.2);
      border-radius: 8px;
      color: #dc2626;
      font-size: var(--font-size-sm);
      text-align: center;
    }

    .login-footer {
      margin-top: var(--spacing-8);
      text-align: center;

      p {
        font-size: var(--font-size-xs);
        color: var(--surface-400);
        margin: 0;
      }
    }
  `]
})
export class LoginComponent implements AfterViewInit {
  @ViewChild('googleBtn') googleBtn!: ElementRef;
  error = signal<string | null>(null);

  constructor(private authService: AuthService) {}

  ngAfterViewInit(): void {
    setTimeout(() => {
      this.authService.initGoogleSignIn(this.googleBtn.nativeElement);
    }, 100);
  }
}
