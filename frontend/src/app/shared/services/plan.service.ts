import { Injectable, signal, computed } from '@angular/core';

export interface PlanModule {
  id: string;
  type: 'semantic' | 'segmentation' | 'activation' | 'feedback' | 'ontology';
  name: string;
  function: string;
  description: string;
  linkedSkills: string[];
  inputSchema: string[];
  outputSchema: string[];
}

export interface Plan {
  id: string;
  name: string;
  goal: string;
  situation: string;
  status: 'active' | 'draft' | 'disabled';
  modules: PlanModule[];
  chatSessionIds: string[];
  createdAt: Date;
  updatedAt: Date;
}

@Injectable({ providedIn: 'root' })
export class PlanService {
  private readonly STORAGE_KEY = 'aicdp_plans';

  private plans = signal<Plan[]>([]);

  constructor() {
    this.loadFromStorage();
  }

  getPlans() {
    return this.plans.asReadonly();
  }

  getPlan(id: string) {
    return computed(() => this.plans().find(p => p.id === id) || null);
  }

  createPlan(data: Partial<Plan>): Plan {
    const plan: Plan = {
      id: this.generateId(),
      name: data.name || 'New Plan',
      goal: data.goal || '',
      situation: data.situation || '',
      status: data.status || 'draft',
      modules: data.modules || [],
      chatSessionIds: data.chatSessionIds || [],
      createdAt: new Date(),
      updatedAt: new Date()
    };

    this.plans.update(plans => [plan, ...plans]);
    this.saveToStorage();

    return plan;
  }

  updatePlan(id: string, updates: Partial<Plan>): void {
    this.plans.update(plans =>
      plans.map(p =>
        p.id === id
          ? { ...p, ...updates, updatedAt: new Date() }
          : p
      )
    );
    this.saveToStorage();
  }

  deletePlan(id: string): void {
    this.plans.update(plans => plans.filter(p => p.id !== id));
    this.saveToStorage();
  }

  linkChatSession(planId: string, sessionId: string): void {
    this.plans.update(plans =>
      plans.map(p => {
        if (p.id === planId && !p.chatSessionIds.includes(sessionId)) {
          return {
            ...p,
            chatSessionIds: [...p.chatSessionIds, sessionId],
            updatedAt: new Date()
          };
        }
        return p;
      })
    );
    this.saveToStorage();
  }

  unlinkChatSession(planId: string, sessionId: string): void {
    this.plans.update(plans =>
      plans.map(p => {
        if (p.id === planId) {
          return {
            ...p,
            chatSessionIds: p.chatSessionIds.filter(id => id !== sessionId),
            updatedAt: new Date()
          };
        }
        return p;
      })
    );
    this.saveToStorage();
  }

  getLinkedChats(planId: string) {
    return computed(() => {
      const plan = this.plans().find(p => p.id === planId);
      return plan?.chatSessionIds || [];
    });
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      if (stored) {
        const plans = JSON.parse(stored) as Plan[];
        // Convert date strings back to Date objects
        plans.forEach(p => {
          p.createdAt = new Date(p.createdAt);
          p.updatedAt = new Date(p.updatedAt);
        });
        this.plans.set(plans);
      } else {
        // Initialize with sample plans
        this.initializeSampleData();
      }
    } catch (e) {
      console.error('Failed to load plans from storage:', e);
      this.initializeSampleData();
    }
  }

  private saveToStorage(): void {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.plans()));
    } catch (e) {
      console.error('Failed to save plans to storage:', e);
    }
  }

  private initializeSampleData(): void {
    const samplePlans: Plan[] = [
      {
        id: 'sample-1',
        name: 'VIP Customer Analysis',
        goal: 'Identify high-value customers with 5+ purchases for targeted campaigns',
        situation: 'Need to segment VIP users for Q1 marketing initiative',
        status: 'active',
        modules: [],
        chatSessionIds: [],
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        id: 'sample-2',
        name: 'Cart Abandonment Study',
        goal: 'Find users who abandoned carts and understand patterns',
        situation: 'High cart abandonment rate affecting conversion',
        status: 'draft',
        modules: [],
        chatSessionIds: [],
        createdAt: new Date(),
        updatedAt: new Date()
      }
    ];
    this.plans.set(samplePlans);
    this.saveToStorage();
  }

  private generateId(): string {
    return `plan-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}
