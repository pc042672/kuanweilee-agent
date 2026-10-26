import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputTextarea } from 'primeng/inputtextarea';
import { TableModule } from 'primeng/table';
import { DialogModule } from 'primeng/dialog';
import { DropdownModule } from 'primeng/dropdown';
import { Plan, PlanModule, PlanService } from '../../shared/services/plan.service';

type PlanDraft = Omit<Plan, 'id' | 'createdAt' | 'updatedAt' | 'chatSessionIds'>;

function emptyModule(): PlanModule {
  return {
    id: '',
    type: 'semantic',
    name: '',
    function: '',
    description: '',
    linkedSkills: [],
    inputSchema: [],
    outputSchema: []
  };
}

@Component({
  selector: 'app-plan-editor',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    ButtonModule,
    InputTextModule,
    InputTextarea,
    TableModule,
    DialogModule,
    DropdownModule
  ],
  template: `
    <div class="content-area">
      <div class="page-header">
        <div class="header-content">
          <div class="back-section">
            <button pButton icon="pi pi-arrow-left" class="p-button-text" routerLink="/plans" ></button>
            <div>
              <h1>{{ isNew() ? 'New Plan' : plan.name }}</h1>
              <p>{{ isNew() ? 'Create a new campaign plan' : 'Edit campaign plan' }}</p>
            </div>
          </div>
          <div class="header-actions">
            <button pButton label="Preview" icon="pi pi-eye" class="p-button-outlined" ></button>
            <button pButton label="Save" icon="pi pi-check" (click)="onSave()" [loading]="saving()" ></button>
          </div>
        </div>
      </div>

      <div class="plan-form glass-card">
        <h3>Plan Overview</h3>

        <div class="form-grid">
          <div class="form-field full-width">
            <label for="name">Plan Name *</label>
            <input pInputText id="name" [(ngModel)]="plan.name" placeholder="Enter plan name" />
          </div>

          <div class="form-field full-width">
            <label for="goal">Goal (目標) *</label>
            <textarea
              pInputTextarea
              id="goal"
              [(ngModel)]="plan.goal"
              placeholder="Describe the campaign goal and KPIs..."
              rows="3"
            ></textarea>
          </div>

          <div class="form-field full-width">
            <label for="situation">Current Situation (現況)</label>
            <textarea
              pInputTextarea
              id="situation"
              [(ngModel)]="plan.situation"
              placeholder="Describe the current situation or trigger conditions..."
              rows="3"
            ></textarea>
          </div>
        </div>
      </div>

      <div class="modules-section glass-card">
        <div class="section-header">
          <h3>Modules (模組)</h3>
          <button pButton label="Add Module" icon="pi pi-plus" class="p-button-outlined" (click)="openModuleDialog()" ></button>
        </div>

        <p-table [value]="plan.modules" [reorderableColumns]="true" (onRowReorder)="onRowReorder($event)">
          <ng-template pTemplate="header">
            <tr>
              <th style="width: 3rem"></th>
              <th>ID</th>
              <th>Module Name</th>
              <th>Function</th>
              <th style="width: 6rem">Actions</th>
            </tr>
          </ng-template>

          <ng-template pTemplate="body" let-module let-index="rowIndex">
            <tr [pReorderableRow]="index">
              <td>
                <i class="pi pi-bars" pReorderableRowHandle style="cursor: move; color: var(--surface-400);"></i>
              </td>
              <td>
                <span class="module-id-badge" [attr.data-type]="module.type">{{ module.id }}</span>
              </td>
              <td>{{ module.name }}</td>
              <td>
                <span class="function-text">{{ module.function }}</span>
              </td>
              <td>
                <div class="action-buttons">
                  <button pButton icon="pi pi-pencil" class="p-button-text p-button-rounded p-button-sm" (click)="editModule(module)" ></button>
                  <button pButton icon="pi pi-trash" class="p-button-text p-button-rounded p-button-sm p-button-danger" (click)="deleteModule(module)" ></button>
                </div>
              </td>
            </tr>
          </ng-template>

          <ng-template pTemplate="emptymessage">
            <tr>
              <td colspan="5" class="empty-modules">
                <div class="empty-state">
                  <i class="pi pi-box"></i>
                  <p>No modules added yet</p>
                  <button pButton label="Add your first module" icon="pi pi-plus" class="p-button-outlined" (click)="openModuleDialog()" ></button>
                </div>
              </td>
            </tr>
          </ng-template>
        </p-table>

        @if (plan.modules.length > 0) {
          <div class="module-flow-preview">
            <h4>Module Flow Preview</h4>
            <div class="flow-visual">
              @for (mod of plan.modules; track mod.id; let last = $last) {
                <div class="flow-node" [attr.data-type]="mod.type">
                  <div class="node-id">{{ mod.id }}</div>
                  <div class="node-name">{{ getModuleShortName(mod.type) }}</div>
                </div>
                @if (!last) {
                  <div class="flow-connector">
                    <i class="pi pi-arrow-right"></i>
                  </div>
                }
              }
            </div>
          </div>
        }
      </div>

      <!-- Module Editor Dialog -->
      <p-dialog
        header="{{ editingModule() ? 'Edit Module' : 'Add Module' }}"
        [(visible)]="moduleDialogVisible"
        [modal]="true"
        [style]="{ width: '600px' }"
        [draggable]="false"
      >
        <div class="module-form">
          <div class="form-row">
            <div class="form-field">
              <label>Module ID *</label>
              <input pInputText [(ngModel)]="currentModule.id" placeholder="e.g., A1, S1, E1" />
            </div>
            <div class="form-field">
              <label>Module Type</label>
              <p-dropdown
                [options]="moduleTypes"
                [(ngModel)]="currentModule.type"
                optionLabel="label"
                optionValue="value"
                placeholder="Select type"
              />
            </div>
          </div>

          <div class="form-field">
            <label>Module Name *</label>
            <input pInputText [(ngModel)]="currentModule.name" placeholder="Enter module name" />
          </div>

          <div class="form-field">
            <label>Function (功能)</label>
            <textarea pInputTextarea [(ngModel)]="currentModule.function" rows="2" placeholder="Describe the function..."></textarea>
          </div>

          <div class="form-field">
            <label>Description (說明)</label>
            <textarea pInputTextarea [(ngModel)]="currentModule.description" rows="4" placeholder="Detailed description..."></textarea>
          </div>
        </div>

        <ng-template pTemplate="footer">
          <button pButton label="Cancel" class="p-button-text" (click)="moduleDialogVisible = false" ></button>
          <button pButton label="Save" icon="pi pi-check" (click)="saveModule()" ></button>
        </ng-template>
      </p-dialog>
    </div>
  `,
  styles: [`
    .page-header {
      margin-bottom: var(--spacing-6);

      .header-content {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
      }

      .back-section {
        display: flex;
        align-items: center;
        gap: var(--spacing-3);
      }

      .header-actions {
        display: flex;
        gap: var(--spacing-3);
      }

      h1 {
        font-size: var(--font-size-2xl);
        font-weight: var(--font-weight-bold);
        color: var(--surface-900);
        margin: 0 0 var(--spacing-1) 0;
      }

      p {
        font-size: var(--font-size-sm);
        color: var(--surface-500);
        margin: 0;
      }
    }

    .plan-form, .modules-section {
      padding: var(--spacing-6);
      margin-bottom: var(--spacing-4);

      h3 {
        font-size: var(--font-size-lg);
        font-weight: var(--font-weight-semibold);
        color: var(--surface-800);
        margin: 0 0 var(--spacing-5) 0;
      }
    }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: var(--spacing-4);
    }

    .form-field {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-2);

      &.full-width {
        grid-column: 1 / -1;
      }

      label {
        font-size: var(--font-size-sm);
        font-weight: var(--font-weight-semibold);
        color: var(--surface-700);
      }

      input, textarea {
        width: 100%;
      }
    }

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: var(--spacing-4);

      h3 {
        margin: 0;
      }
    }

    .module-id-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 4px 12px;
      border-radius: 6px;
      font-size: var(--font-size-sm);
      font-weight: var(--font-weight-bold);
      background: var(--primary-100);
      color: var(--primary-700);

      &[data-type="semantic"] { background: #ede9fe; color: #7c3aed; }
      &[data-type="segmentation"] { background: #e0f2fe; color: #0284c7; }
      &[data-type="activation"] { background: #fef3c7; color: #d97706; }
      &[data-type="feedback"] { background: #dcfce7; color: #16a34a; }
      &[data-type="ontology"] { background: #fce7f3; color: #db2777; }
    }

    .function-text {
      font-size: var(--font-size-sm);
      color: var(--surface-600);
    }

    .action-buttons {
      display: flex;
      gap: var(--spacing-1);
    }

    .empty-state {
      text-align: center;
      padding: var(--spacing-8);
      color: var(--surface-500);

      i {
        font-size: 2.5rem;
        margin-bottom: var(--spacing-3);
      }

      p {
        margin-bottom: var(--spacing-3);
      }
    }

    .module-flow-preview {
      margin-top: var(--spacing-6);
      padding-top: var(--spacing-6);
      border-top: 1px solid var(--surface-200);

      h4 {
        font-size: var(--font-size-base);
        font-weight: var(--font-weight-semibold);
        color: var(--surface-700);
        margin: 0 0 var(--spacing-4) 0;
      }
    }

    .flow-visual {
      display: flex;
      align-items: center;
      gap: var(--spacing-3);
      flex-wrap: wrap;
    }

    .flow-node {
      padding: var(--spacing-3) var(--spacing-4);
      background: white;
      border: 2px solid var(--surface-200);
      border-radius: 12px;
      text-align: center;
      min-width: 80px;
      transition: all 0.2s ease;

      &:hover {
        border-color: var(--primary-300);
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.1);
      }

      &[data-type="semantic"] { border-color: #c4b5fd; }
      &[data-type="segmentation"] { border-color: #7dd3fc; }
      &[data-type="activation"] { border-color: #fcd34d; }
      &[data-type="feedback"] { border-color: #86efac; }
      &[data-type="ontology"] { border-color: #f9a8d4; }

      .node-id {
        font-size: var(--font-size-lg);
        font-weight: var(--font-weight-bold);
        color: var(--primary-700);
      }

      .node-name {
        font-size: var(--font-size-xs);
        color: var(--surface-500);
        margin-top: 2px;
      }
    }

    .flow-connector {
      color: var(--surface-400);
    }

    .module-form {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-4);

      .form-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--spacing-4);
      }
    }
  `]
})
export class PlanEditorComponent {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private planService = inject(PlanService);

  isNew = signal(true);
  saving = signal(false);
  moduleDialogVisible = false;
  editingModule = signal<PlanModule | null>(null);

  moduleTypes = [
    { label: 'A - Semantic Customer Understanding', value: 'semantic' },
    { label: 'S - Autonomous Segmentation', value: 'segmentation' },
    { label: 'E - Context-Aware Generative Activation', value: 'activation' },
    { label: 'W - Feedback-Driven Optimization', value: 'feedback' },
    { label: 'P - Ontology-Guided Context Optimization', value: 'ontology' }
  ];

  private planId: string | null = null;

  // Plain draft objects for ngModel form bindings — copied into PlanService on save.
  plan: PlanDraft = {
    name: '',
    goal: '',
    situation: '',
    status: 'draft',
    modules: []
  };

  currentModule: PlanModule = emptyModule();

  constructor() {
    this.planId = this.route.snapshot.paramMap.get('id');
    if (this.planId) {
      const existing = this.planService.getPlan(this.planId)();
      if (existing) {
        this.isNew.set(false);
        this.plan = {
          name: existing.name,
          goal: existing.goal,
          situation: existing.situation,
          status: existing.status,
          modules: existing.modules.map(m => ({ ...m }))
        };
      } else {
        this.planId = null;
      }
    }
  }

  getModuleShortName(type: string): string {
    const names: { [key: string]: string } = {
      semantic: 'Semantic',
      segmentation: 'Segment',
      activation: 'Generate',
      feedback: 'Feedback',
      ontology: 'Ontology'
    };
    return names[type] || type;
  }

  openModuleDialog(): void {
    this.editingModule.set(null);
    this.currentModule = emptyModule();
    this.moduleDialogVisible = true;
  }

  editModule(module: PlanModule): void {
    this.editingModule.set(module);
    this.currentModule = { ...module };
    this.moduleDialogVisible = true;
  }

  saveModule(): void {
    const current = this.currentModule;
    const existing = this.editingModule();

    const modules = [...this.plan.modules];
    if (existing) {
      const index = modules.findIndex(m => m.id === existing.id);
      if (index >= 0) {
        modules[index] = current;
      }
    } else {
      modules.push(current);
    }
    this.plan = { ...this.plan, modules };

    this.moduleDialogVisible = false;
  }

  deleteModule(module: PlanModule): void {
    this.plan = {
      ...this.plan,
      modules: this.plan.modules.filter(m => m.id !== module.id)
    };
  }

  onRowReorder(event: any): void {
    // Modules are automatically reordered by PrimeNG
  }

  onSave(): void {
    this.saving.set(true);
    try {
      if (this.planId) {
        this.planService.updatePlan(this.planId, { ...this.plan });
      } else {
        this.planService.createPlan({ ...this.plan });
      }
      this.router.navigate(['/plans']);
    } finally {
      this.saving.set(false);
    }
  }
}
