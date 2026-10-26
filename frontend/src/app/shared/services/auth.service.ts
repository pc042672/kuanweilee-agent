import { Injectable, signal, computed, NgZone } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

declare const google: any;

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  role?: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private currentUserSignal = signal<User | null>(null);
  private _sessionReady: Promise<void>;

  readonly currentUser = this.currentUserSignal.asReadonly();
  readonly isAuthenticated = computed(() => this.currentUserSignal() !== null);
  readonly isAdmin = computed(() => ['admin', 'owner'].includes(this.currentUserSignal()?.role ?? ''));

  constructor(
    private http: HttpClient,
    private router: Router,
    private ngZone: NgZone
  ) {
    this._sessionReady = this.loadSession();
  }

  /** Resolves once the initial session check (JWT or DEV_MODE) completes. */
  get sessionReady(): Promise<void> {
    return this._sessionReady;
  }

  async initGoogleSignIn(buttonElement: HTMLElement): Promise<void> {
    if (typeof google === 'undefined') return;

    let clientId: string | null = null;
    try {
      const config = await firstValueFrom(
        this.http.get<{ google_client_id: string | null }>('/api/auth/config')
      );
      clientId = config.google_client_id;
    } catch {
      console.error('Failed to load auth config');
      return;
    }
    if (!clientId) return;  // OAuth not configured (dev mode)

    google.accounts.id.initialize({
      client_id: clientId,
      callback: (response: any) => {
        this.ngZone.run(() => this.handleGoogleCredential(response.credential));
      },
    });

    google.accounts.id.renderButton(buttonElement, {
      theme: 'outline',
      size: 'large',
      width: 360,
      text: 'signin_with',
    });
  }

  private async handleGoogleCredential(idToken: string): Promise<void> {
    try {
      const response = await firstValueFrom(
        this.http.post<{ token: string; user: User }>('/api/auth/login', { id_token: idToken })
      );
      localStorage.setItem('session_token', response.token);
      this.currentUserSignal.set(response.user);
      this.router.navigate(['/']);
    } catch {
      console.error('Google login failed');
    }
  }

  private async loadSession(): Promise<void> {
    const token = localStorage.getItem('session_token');

    try {
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      const user = await firstValueFrom(
        this.http.get<User>('/api/auth/me', { headers })
      );
      this.currentUserSignal.set(user);
    } catch {
      localStorage.removeItem('session_token');
    }
  }

  getToken(): string | null {
    return localStorage.getItem('session_token');
  }

  logout(): void {
    this.currentUserSignal.set(null);
    localStorage.removeItem('session_token');
    this.router.navigate(['/login']);
  }
}
