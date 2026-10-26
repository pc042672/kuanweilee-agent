import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AuthService } from './auth.service';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolCalls?: any[];
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  planId?: string;
  messages: Message[];
  starred?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ChatSessionService {
  private readonly STORAGE_KEY = 'aicdp_chat_sessions';
  private readonly ACTIVE_KEY = 'aicdp_active_session';

  private http = inject(HttpClient);
  private sessions = signal<ChatSession[]>([]);
  private activeSessionId = signal<string | null>(null);

  /** True when the backend persists sessions (DATABASE_URL set server-side). */
  readonly persistent = signal(false);

  private auth = inject(AuthService);

  constructor() {
    this.loadFromStorage();
    // Sync after auth resolves so the list call carries the session token.
    this.auth.sessionReady.then(() => this.syncFromBackend());
  }

  /** Merge backend session list into local state (backend owns existence/order;
   *  localStorage contributes cached titles/messages). Falls back silently to
   *  localStorage-only when the backend has no persistent sessions. */
  private async syncFromBackend(): Promise<void> {
    try {
      const caps = await firstValueFrom(
        this.http.get<{ persistent_sessions?: boolean }>('/api/chat/capabilities')
      );
      if (!caps?.persistent_sessions) return;
      this.persistent.set(true);

      const res = await firstValueFrom(this.http.get<{
        sessions: { id: string; last_update_time: number | null }[];
      }>('/api/chat/sessions'));

      const local = new Map(this.sessions().map(s => [s.id, s]));
      const merged: ChatSession[] = res.sessions.map(remote => {
        const cached = local.get(remote.id);
        const updatedAt = remote.last_update_time
          ? new Date(remote.last_update_time * 1000) : new Date();
        return cached
          ? { ...cached, updatedAt }
          : {
              id: remote.id, title: 'Chat', createdAt: updatedAt,
              updatedAt, messages: [],
            };
      });
      // Keep local-only sessions (pre-persistence history / not yet sent)
      for (const s of this.sessions()) {
        if (!merged.some(m => m.id === s.id)) merged.push(s);
      }
      merged.sort((a, b) => +new Date(b.updatedAt) - +new Date(a.updatedAt));
      this.sessions.set(merged);
      this.saveToStorage();
    } catch (e) {
      console.warn('Backend session sync unavailable, using localStorage:', e);
    }
  }

  /** Fetch a session's messages from the backend (persistent mode). Always
   *  refetches — live messages land in the agent store, not here, so a cache
   *  would go stale after any chat in the session. */
  async loadMessages(sessionId: string): Promise<Message[]> {
    const session = this.sessions().find(s => s.id === sessionId);
    if (!this.persistent() || !session) return session?.messages ?? [];
    try {
      const res = await firstValueFrom(this.http.get<{
        messages: { role: string; text: string; timestamp: number | null }[];
      }>(`/api/chat/sessions/${encodeURIComponent(sessionId)}/messages`));
      const messages: Message[] = res.messages.map((m, i) => ({
        id: `${sessionId}-${i}`,
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.text,
        timestamp: m.timestamp ? new Date(m.timestamp * 1000) : new Date(),
      }));
      const firstUser = messages.find(m => m.role === 'user');
      this.sessions.update(list => list.map(s => s.id === sessionId ? {
        ...s,
        messages,
        title: s.title === 'Chat' && firstUser
          ? firstUser.content.slice(0, 50) + (firstUser.content.length > 50 ? '...' : '')
          : s.title,
      } : s));
      this.saveToStorage();
      return messages;
    } catch (e) {
      console.warn('Failed to load messages from backend:', e);
      return session.messages;
    }
  }

  getSessions() {
    return this.sessions.asReadonly();
  }

  getActiveSessionId() {
    return this.activeSessionId.asReadonly();
  }

  getSessionsByDate() {
    return computed(() => {
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
      const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

      const all = this.sessions();
      return {
        today: all.filter(s => new Date(s.updatedAt) >= today),
        yesterday: all.filter(s => {
          const d = new Date(s.updatedAt);
          return d >= yesterday && d < today;
        }),
        thisWeek: all.filter(s => {
          const d = new Date(s.updatedAt);
          return d >= weekAgo && d < yesterday;
        }),
        older: all.filter(s => new Date(s.updatedAt) < weekAgo)
      };
    });
  }

  createSession(planId?: string): ChatSession {
    const session: ChatSession = {
      id: this.generateId(),
      title: 'New Chat',
      createdAt: new Date(),
      updatedAt: new Date(),
      planId,
      messages: []
    };

    this.sessions.update(sessions => [session, ...sessions]);
    this.activeSessionId.set(session.id);
    this.saveToStorage();

    return session;
  }

  setActiveSession(sessionId: string): void {
    if (this.sessions().some(s => s.id === sessionId)) {
      this.activeSessionId.set(sessionId);
      localStorage.setItem(this.ACTIVE_KEY, sessionId);
    }
  }

  updateSession(id: string, updates: Partial<ChatSession>): void {
    this.sessions.update(sessions =>
      sessions.map(s =>
        s.id === id
          ? { ...s, ...updates, updatedAt: new Date() }
          : s
      )
    );
    this.saveToStorage();
  }

  addMessage(sessionId: string, message: Omit<Message, 'id' | 'timestamp'>): void {
    const newMessage: Message = {
      ...message,
      id: this.generateId(),
      timestamp: new Date()
    };

    this.sessions.update(sessions =>
      sessions.map(s => {
        if (s.id === sessionId) {
          // Update title from first user message if still "New Chat"
          let title = s.title;
          if (title === 'New Chat' && message.role === 'user') {
            title = message.content.slice(0, 50) + (message.content.length > 50 ? '...' : '');
          }
          return {
            ...s,
            title,
            messages: [...s.messages, newMessage],
            updatedAt: new Date()
          };
        }
        return s;
      })
    );
    this.saveToStorage();
  }

  deleteSession(id: string): void {
    this.sessions.update(sessions => sessions.filter(s => s.id !== id));
    if (this.activeSessionId() === id) {
      const remaining = this.sessions();
      this.activeSessionId.set(remaining.length > 0 ? remaining[0].id : null);
    }
    this.saveToStorage();
    if (this.persistent()) {
      this.http.delete(`/api/chat/sessions/${encodeURIComponent(id)}`)
        .subscribe({ error: e => console.warn('Backend session delete failed:', e) });
    }
  }

  linkToPlan(sessionId: string, planId: string): void {
    this.updateSession(sessionId, { planId });
  }

  unlinkFromPlan(sessionId: string): void {
    this.updateSession(sessionId, { planId: undefined });
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      if (stored) {
        const sessions = JSON.parse(stored) as ChatSession[];
        // Convert date strings back to Date objects
        sessions.forEach(s => {
          s.createdAt = new Date(s.createdAt);
          s.updatedAt = new Date(s.updatedAt);
          s.messages.forEach(m => {
            m.timestamp = new Date(m.timestamp);
          });
        });
        this.sessions.set(sessions);
      }

      const activeId = localStorage.getItem(this.ACTIVE_KEY);
      if (activeId && this.sessions().some(s => s.id === activeId)) {
        this.activeSessionId.set(activeId);
      }
    } catch (e) {
      console.error('Failed to load chat sessions from storage:', e);
    }
  }

  private saveToStorage(): void {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.sessions()));
      const activeId = this.activeSessionId();
      if (activeId) {
        localStorage.setItem(this.ACTIVE_KEY, activeId);
      }
    } catch (e) {
      console.error('Failed to save chat sessions to storage:', e);
    }
  }

  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}
