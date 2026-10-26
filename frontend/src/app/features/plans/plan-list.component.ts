import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { TableModule } from 'primeng/table';
import { InputTextModule } from 'primeng/inputtext';
import { DropdownModule } from 'primeng/dropdown';
import { TagModule } from 'primeng/tag';
import { Plan, PlanService } from '../../shared/services/plan.service';

@Component({
  selector: 'app-plan-list',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    ButtonModule,
    TableModule,
    InputTextModule,
    DropdownModule,
    TagModule
  ],
  template: `
    <div class="content-area">
      <div class="page-header">
        <div class="header-content">
          <div>
            <h1>Campaign Plans</h1>
            <p>AI-driven marketing automation workflows</p>
          </div>
          <button pButton label="New Plan" icon="pi pi-plus" routerLink="/plans/new"></button>
        </div>
      </div>

      <div class="search-bar glass-surface">
        <span class="p-input-icon-left">
          <i class="pi pi-search"></i>
          <input pInputText placeholder="Search plans..." [(ngModel)]="searchQuery" />
        </span>
        <p-dropdown
          [options]="statusOptions"
          [(ngModel)]="selectedStatus"
          placeholder="Status"
          [showClear]="true"
        />
      </div>

      <div class="plans-table glass-card">
        <p-table
          [value]="filteredPlans()"
          [expandedRowKeys]="expandedRows"
          dataKey="id"
          [rowHover]="true"
        >
          <ng-template pTemplate="header">
            <tr>
              <th style="width: 3rem"></th>
              <th>Plan Name</th>
              <th>Goal</th>
              <th>Modules</th>
              <th>Status</th>
              <th style="width: 8rem">Actions</th>
            </tr>
          </ng-template>

          <ng-template pTemplate="body" let-plan let-expanded="expanded">
            <tr>
              <td>
                <button
                  pButton
                  [icon]="expanded ? 'pi pi-chevron-down' : 'pi pi-chevron-right'"
                  [pRowToggler]="plan"
                  class="p-button-text p-button-rounded p-button-sm"
                ></button>
              </td>
              <td>
                <div class="plan-name">{{ plan.name }}</div>
              </td>
              <td>
                <div class="plan-goal">{{ plan.goal }}</div>
              </td>
              <td>
                <div class="module-flow">
                  @for (mod of plan.modules; track mod.id; let last = $last) {
                    <span class="module-badge" [attr.data-type]="mod.type">{{ mod.id }}</span>
                    @if (!last) {
                      <i class="pi pi-arrow-right module-arrow"></i>
                    }
                  }
                </div>
              </td>
              <td>
                <p-tag
                  [value]="plan.status"
                  [severity]="getStatusSeverity(plan.status)"
                />
              </td>
              <td>
                <div class="action-buttons">
                  <button
                    pButton
                    icon="pi pi-pencil"
                    class="p-button-text p-button-rounded p-button-sm"
                    [routerLink]="['/plans', plan.id]"
                  ></button>
                  <button
                    pButton
                    icon="pi pi-trash"
                    class="p-button-text p-button-rounded p-button-sm p-button-danger"
                    (click)="onDelete(plan)"
                  ></button>
                </div>
              </td>
            </tr>
          </ng-template>

          <ng-template pTemplate="rowexpansion" let-plan>
            <tr>
              <td colspan="6">
                <div class="expanded-content">
                  <div class="expanded-section">
                    <strong>Goal:</strong>
                    <p>{{ plan.goal }}</p>
                  </div>
                  <div class="expanded-section">
                    <strong>Current Situation:</strong>
                    <p>{{ plan.situation }}</p>
                  </div>
                  <div class="expanded-section">
                    <strong>Module Flow:</strong>
                    <div class="module-flow-visual">
                      @for (mod of plan.modules; track mod.id; let last = $last) {
                        <div class="module-card" [attr.data-type]="mod.type">
                          <div class="module-id">{{ mod.id }}</div>
                          <div class="module-name">{{ mod.name }}</div>
                        </div>
                        @if (!last) {
                          <div class="flow-arrow">
                            <i class="pi pi-arrow-right"></i>
                          </div>
                        }
                      }
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </ng-template>

          <ng-template pTemplate="emptymessage">
            <tr>
              <td colspan="6" class="empty-message">
                <div class="empty-state">
                  <i class="pi pi-inbox"></i>
                  <p>No plans found</p>
                  <button pButton label="Create your first plan" icon="pi pi-plus" routerLink="/plans/new"></button>
                </div>
              </td>
            </tr>
          </ng-template>
        </p-table>
      </div>
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

    .search-bar {
      display: flex;
      gap: var(--spacing-4);
      padding: var(--spacing-4);
      border-radius: 12px;
      margin-bottom: var(--spacing-4);

      .p-input-icon-left {
        flex: 1;

        input {
          width: 100%;
        }
      }
    }

    .plans-table {
      padding: var(--spacing-4);
      overflow: hidden;

      :host ::ng-deep .p-datatable {
        .p-datatable-thead > tr > th {
          background: transparent;
          border-bottom: 1px solid var(--surface-200);
          font-weight: var(--font-weight-semibold);
          color: var(--surface-600);
          font-size: var(--font-size-sm);
        }

        .p-datatable-tbody > tr {
          transition: background 0.2s ease;

          &:hover {
            background: var(--glass-overlay);
          }

          > td {
            border-bottom: 1px solid var(--surface-100);
            padding: var(--spacing-4);
          }
        }
      }
    }

    .plan-name {
      font-weight: var(--font-weight-medium);
      color: var(--surface-800);
    }

    .plan-goal {
      font-size: var(--font-size-sm);
      color: var(--surface-600);
      max-width: 300px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .module-flow {
      display: flex;
      align-items: center;
      gap: var(--spacing-2);
    }

    .module-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: var(--font-size-xs);
      font-weight: var(--font-weight-semibold);
      background: var(--primary-100);
      color: var(--primary-700);

      &[data-type="semantic"] { background: #ede9fe; color: #7c3aed; }
      &[data-type="segmentation"] { background: #e0f2fe; color: #0284c7; }
      &[data-type="activation"] { background: #fef3c7; color: #d97706; }
      &[data-type="feedback"] { background: #dcfce7; color: #16a34a; }
      &[data-type="ontology"] { background: #fce7f3; color: #db2777; }
    }

    .module-arrow {
      color: var(--surface-400);
      font-size: 0.75rem;
    }

    .action-buttons {
      display: flex;
      gap: var(--spacing-1);
    }

    .expanded-content {
      padding: var(--spacing-4);
      background: var(--surface-50);
      border-radius: 8px;
      margin: var(--spacing-2) 0;
    }

    .expanded-section {
      margin-bottom: var(--spacing-4);

      &:last-child {
        margin-bottom: 0;
      }

      strong {
        display: block;
        font-size: var(--font-size-sm);
        color: var(--surface-600);
        margin-bottom: var(--spacing-2);
      }

      p {
        margin: 0;
        color: var(--surface-800);
      }
    }

    .module-flow-visual {
      display: flex;
      align-items: center;
      gap: var(--spacing-3);
      flex-wrap: wrap;
    }

    .module-card {
      padding: var(--spacing-3);
      background: white;
      border: 1px solid var(--surface-200);
      border-radius: 8px;
      text-align: center;
      min-width: 100px;

      .module-id {
        font-size: var(--font-size-lg);
        font-weight: var(--font-weight-bold);
        color: var(--primary-700);
      }

      .module-name {
        font-size: var(--font-size-xs);
        color: var(--surface-600);
        margin-top: var(--spacing-1);
      }
    }

    .flow-arrow {
      color: var(--surface-400);
    }

    .empty-state {
      text-align: center;
      padding: var(--spacing-12);
      color: var(--surface-500);

      i {
        font-size: 3rem;
        margin-bottom: var(--spacing-4);
      }

      p {
        margin-bottom: var(--spacing-4);
      }
    }
  `]
})
export class PlanListComponent {
  private planService = inject(PlanService);

  searchQuery = signal('');
  selectedStatus = signal<string | null>(null);
  expandedRows: { [key: string]: boolean } = {};

  statusOptions = [
    { label: 'Active', value: 'active' },
    { label: 'Draft', value: 'draft' },
    { label: 'Disabled', value: 'disabled' }
  ];

  plans = this.planService.getPlans();

  filteredPlans = computed(() => {
    const query = this.searchQuery().trim().toLowerCase();
    const status = this.selectedStatus();
    return this.plans().filter(p => {
      if (status && p.status !== status) return false;
      if (!query) return true;
      return p.name.toLowerCase().includes(query) || p.goal.toLowerCase().includes(query);
    });
  });

  getStatusSeverity(status: string): 'success' | 'warn' | 'secondary' {
    switch (status) {
      case 'active': return 'success';
      case 'draft': return 'warn';
      default: return 'secondary';
    }
  }

  onDelete(plan: Plan): void {
    if (confirm(`Delete plan "${plan.name}"?`)) {
      this.planService.deletePlan(plan.id);
    }
  }
}
