import { Component, Input, Output, EventEmitter, signal, computed, inject, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputText } from 'primeng/inputtext';
import { InputTextarea } from 'primeng/inputtextarea';
import { DropdownModule } from 'primeng/dropdown';
import { RadioButtonModule } from 'primeng/radiobutton';
import { PlanService, Plan } from '../../shared/services/plan.service';
import { ChatSessionService } from '../../shared/services/chat-session.service';

export interface SaveToPlanData {
  goal: string;
  sql?: string;
  sessionId?: string;
}

export interface SaveToPlanResult {
  mode: 'new' | 'existing';
  planId: string;
  planName?: string;
}

@Component({
  selector: 'app-save-to-plan-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonModule,
    DialogModule,
    InputText,
    InputTextarea,
    DropdownModule,
    RadioButtonModule
  ],
  template: `
    <p-dialog
      header="Save to Plan"
      [(visible)]="visible"
      [modal]="true"
      [style]="{ width: '520px' }"
      [closable]="true"
      (onHide)="onCancel()"
    >
      <div class="dialog-content">
        <!-- Option: Create New Plan -->
        <div class="option-section">
          <div class="option-header">
            <p-radioButton
              name="saveOption"
              value="new"
              [(ngModel)]="selectedOption"
              inputId="optionNew"
            />
            <label for="optionNew" class="option-label">Create New Plan</label>
          </div>

          @if (selectedOption === 'new') {
            <div class="option-form">
              <div class="form-field">
                <label for="planName">Plan Name</label>
                <input
                  pInputText
                  id="planName"
                  [(ngModel)]="newPlanName"
                  [placeholder]="suggestedName()"
                  class="w-full"
                />
              </div>

              <div class="form-field">
                <label for="planGoal">Goal</label>
                <textarea
                  pInputTextarea
                  id="planGoal"
                  [(ngModel)]="newPlanGoal"
                  [rows]="3"
                  [placeholder]="suggestedGoal()"
                  class="w-full"
                ></textarea>
              </div>

              @if (data && data.sql) {
                <div class="sql-preview">
                  <span class="preview-label">Generated SQL will be linked:</span>
                  <code>{{ truncateSql(data.sql) }}</code>
                </div>
              }
            </div>
          }
        </div>

        <!-- Option: Link to Existing Plan -->
        <div class="option-section">
          <div class="option-header">
            <p-radioButton
              name="saveOption"
              value="existing"
              [(ngModel)]="selectedOption"
              inputId="optionExisting"
            />
            <label for="optionExisting" class="option-label">Link to Existing Plan</label>
          </div>

          @if (selectedOption === 'existing') {
            <div class="option-form">
              <div class="form-field">
                <label for="existingPlan">Select Plan</label>
                <p-dropdown
                  id="existingPlan"
                  [options]="planOptions()"
                  [(ngModel)]="selectedPlanId"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="Choose a plan..."
                  styleClass="w-full"
                >
                  <ng-template let-plan pTemplate="item">
                    <div class="plan-dropdown-item">
                      <span class="plan-name">{{ plan.label }}</span>
                      <span class="plan-status" [class]="plan.status">{{ plan.status }}</span>
                    </div>
                  </ng-template>
                </p-dropdown>
              </div>

              @if (selectedPlanId && getSelectedPlan(); as plan) {
                <div class="plan-preview">
                  <div class="preview-row">
                    <span class="preview-label">Goal:</span>
                    <span>{{ plan.goal || 'No goal defined' }}</span>
                  </div>
                  <div class="preview-row">
                    <span class="preview-label">Linked Chats:</span>
                    <span>{{ plan.chatSessionIds.length }} conversation(s)</span>
                  </div>
                </div>
              }
            </div>
          }
        </div>
      </div>

      <ng-template pTemplate="footer">
        <div class="dialog-footer">
          <button
            pButton
            label="Cancel"
            class="p-button-text"
            (click)="onCancel()"
          ></button>
          <button
            pButton
            label="Save"
            icon="pi pi-check"
            [disabled]="!canSave()"
            [loading]="saving()"
            (click)="onSave()"
          ></button>
        </div>
      </ng-template>
    </p-dialog>
  `,
  styles: [`
    .dialog-content {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-4);
    }

    .option-section {
      padding: var(--spacing-4);
      border: 1px solid var(--surface-200);
      border-radius: 12px;
      transition: all 0.2s ease;

      &:has(input[type="radio"]:checked) {
        border-color: var(--primary-300);
        background: rgba(124, 58, 237, 0.02);
      }
    }

    .option-header {
      display: flex;
      align-items: center;
      gap: var(--spacing-3);
    }

    .option-label {
      font-weight: var(--font-weight-semibold);
      color: var(--surface-700);
      cursor: pointer;
    }

    .option-form {
      margin-top: var(--spacing-4);
      padding-left: calc(20px + var(--spacing-3));
      display: flex;
      flex-direction: column;
      gap: var(--spacing-3);
    }

    .form-field {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-2);

      label {
        font-size: var(--font-size-sm);
        font-weight: var(--font-weight-medium);
        color: var(--surface-600);
      }

      input, textarea {
        width: 100%;
      }
    }

    .sql-preview {
      background: var(--surface-100);
      border-radius: 8px;
      padding: var(--spacing-3);

      .preview-label {
        display: block;
        font-size: var(--font-size-xs);
        color: var(--surface-500);
        margin-bottom: var(--spacing-2);
      }

      code {
        display: block;
        font-size: var(--font-size-xs);
        color: var(--primary-700);
        white-space: pre-wrap;
        word-break: break-all;
      }
    }

    .plan-dropdown-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;

      .plan-name {
        font-weight: var(--font-weight-medium);
      }

      .plan-status {
        font-size: var(--font-size-xs);
        padding: 2px 8px;
        border-radius: 4px;

        &.active {
          background: rgba(16, 185, 129, 0.1);
          color: var(--success-color);
        }

        &.draft {
          background: rgba(245, 158, 11, 0.1);
          color: var(--warning-color);
        }

        &.disabled {
          background: var(--surface-100);
          color: var(--surface-500);
        }
      }
    }

    .plan-preview {
      background: var(--surface-50);
      border-radius: 8px;
      padding: var(--spacing-3);
      display: flex;
      flex-direction: column;
      gap: var(--spacing-2);
    }

    .preview-row {
      display: flex;
      gap: var(--spacing-2);
      font-size: var(--font-size-sm);

      .preview-label {
        color: var(--surface-500);
        min-width: 80px;
      }
    }

    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      gap: var(--spacing-2);
    }

    .w-full {
      width: 100%;
    }
  `]
})
export class SaveToPlanDialogComponent implements OnChanges {
  @Input() visible = false;
  @Input() data: SaveToPlanData | null = null;

  @Output() visibleChange = new EventEmitter<boolean>();
  @Output() saved = new EventEmitter<SaveToPlanResult>();
  @Output() cancelled = new EventEmitter<void>();

  private planService = inject(PlanService);
  private chatSessionService = inject(ChatSessionService);

  selectedOption: 'new' | 'existing' = 'new';
  newPlanName = '';
  newPlanGoal = '';
  selectedPlanId: string | null = null;
  saving = signal(false);

  plans = this.planService.getPlans();

  planOptions = computed(() => {
    return this.plans().map(p => ({
      label: p.name,
      value: p.id,
      status: p.status
    }));
  });

  suggestedName = computed(() => {
    if (!this.data?.goal) return 'New Plan';
    // Generate a name from the goal
    const words = this.data.goal.split(' ').slice(0, 4);
    return words.map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
  });

  suggestedGoal = computed(() => {
    return this.data?.goal || '';
  });

  canSave = computed(() => {
    if (this.selectedOption === 'new') {
      const name = this.newPlanName.trim() || this.suggestedName();
      return name.length > 0;
    } else {
      return this.selectedPlanId !== null;
    }
  });

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['visible'] && this.visible) {
      // Reset form when dialog opens
      this.selectedOption = 'new';
      this.newPlanName = '';
      this.newPlanGoal = '';
      this.selectedPlanId = null;
    }
  }

  getSelectedPlan(): Plan | null {
    if (!this.selectedPlanId) return null;
    return this.plans().find(p => p.id === this.selectedPlanId) || null;
  }

  truncateSql(sql: string): string {
    if (sql.length <= 100) return sql;
    return sql.substring(0, 100) + '...';
  }

  onSave(): void {
    if (!this.canSave()) return;

    this.saving.set(true);

    try {
      if (this.selectedOption === 'new') {
        // Create new plan
        const name = this.newPlanName.trim() || this.suggestedName();
        const goal = this.newPlanGoal.trim() || this.suggestedGoal();

        const plan = this.planService.createPlan({
          name,
          goal,
          status: 'draft'
        });

        // Link current chat session if available
        if (this.data?.sessionId) {
          this.planService.linkChatSession(plan.id, this.data.sessionId);
          this.chatSessionService.linkToPlan(this.data.sessionId, plan.id);
        }

        this.saved.emit({
          mode: 'new',
          planId: plan.id,
          planName: plan.name
        });
      } else {
        // Link to existing plan
        if (this.selectedPlanId && this.data?.sessionId) {
          this.planService.linkChatSession(this.selectedPlanId, this.data.sessionId);
          this.chatSessionService.linkToPlan(this.data.sessionId, this.selectedPlanId);
        }

        const plan = this.getSelectedPlan();
        this.saved.emit({
          mode: 'existing',
          planId: this.selectedPlanId!,
          planName: plan?.name
        });
      }

      this.closeDialog();
    } catch (error) {
      console.error('Failed to save to plan:', error);
    } finally {
      this.saving.set(false);
    }
  }

  onCancel(): void {
    this.cancelled.emit();
    this.closeDialog();
  }

  private closeDialog(): void {
    this.visible = false;
    this.visibleChange.emit(false);
  }
}
