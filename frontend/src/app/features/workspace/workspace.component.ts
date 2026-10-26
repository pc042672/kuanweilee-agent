import { Component, computed, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';
import { ChatPanelComponent } from './chat-panel.component';
import { SaveToPlanDialogComponent, SaveToPlanData, SaveToPlanResult } from './save-to-plan-dialog.component';
import { ChatSessionService } from '../../shared/services/chat-session.service';
import { PlanService } from '../../shared/services/plan.service';

@Component({
  selector: 'app-workspace',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonModule,
    TooltipModule,
    ChatPanelComponent,
    SaveToPlanDialogComponent
  ],
  template: `
    <div class="workspace-container">
      <!-- Chat Panel -->
      <div class="chat-area">
        <app-chat-panel
          [session]="activeSession()"
          (saveToPlan)="onSaveToPlan($event)"
        />
      </div>
    </div>

    <!-- Save to Plan Dialog -->
    <app-save-to-plan-dialog
      [(visible)]="saveToPlanDialogVisible"
      [data]="saveToPlanData"
      (saved)="onPlanSaved($event)"
      (cancelled)="onPlanCancelled()"
    />
  `,
  styles: [`
    .workspace-container {
      display: flex;
      flex-direction: column;
      height: 100vh;
      background: linear-gradient(180deg, #fafaff 0%, #fcfcff 50%, #f9f8ff 100%);
    }

    .chat-area {
      flex: 1;
      overflow: hidden;
    }
  `]
})
export class WorkspaceComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private destroyRef = inject(DestroyRef);
  private chatSessionService = inject(ChatSessionService);
  private planService = inject(PlanService);

  selectedPlanId: string | null = null;

  // Save to Plan dialog state
  saveToPlanDialogVisible = false;
  saveToPlanData: SaveToPlanData | null = null;

  sessions = this.chatSessionService.getSessions();
  activeSessionId = this.chatSessionService.getActiveSessionId();

  activeSession = computed(() => {
    const id = this.activeSessionId();
    if (!id) return null;
    return this.sessions().find(s => s.id === id) || null;
  });

  plans = this.planService.getPlans();

  planOptions = computed(() => {
    return this.plans().map(p => ({
      label: p.name,
      value: p.id
    }));
  });

  ngOnInit(): void {
    // Check for session ID in route
    this.route.params.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const sessionId = params['sessionId'];
      if (sessionId) {
        this.chatSessionService.setActiveSession(sessionId);
      }
    });
  }

  onSaveToPlan(data: { goal: string; sql?: string }): void {
    const sessionId = this.activeSessionId();
    this.saveToPlanData = {
      goal: data.goal,
      sql: data.sql,
      sessionId: sessionId || undefined
    };
    this.saveToPlanDialogVisible = true;
  }

  onPlanSaved(result: SaveToPlanResult): void {
    this.saveToPlanData = null;
  }

  onPlanCancelled(): void {
    this.saveToPlanData = null;
  }

  onPlanSelect(planId: string | null): void {
    this.selectedPlanId = planId;
  }
}
