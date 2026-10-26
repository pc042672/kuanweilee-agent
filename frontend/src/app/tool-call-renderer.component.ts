import { Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TagModule } from 'primeng/tag';
import { ToolRenderer, AngularToolCall } from '@copilotkitnext/angular';

@Component({
  selector: 'app-tool-call-renderer',
  standalone: true,
  imports: [CommonModule, CardModule, ProgressSpinnerModule, TagModule],
  template: `
    <div class="tool-call-container">
      <div class="tool-header">
        <p-tag [value]="statusLabel()" [severity]="severity()" icon="pi pi-wrench" />
        <span class="tool-name">{{ toolName() }}</span>
        @if (isInProgress()) {
          <p-progressSpinner
            styleClass="tool-spinner"
            [style]="{ width: '16px', height: '16px' }"
            strokeWidth="4"
          />
        }
      </div>

      @if (hasArgs()) {
        <div class="tool-args">
          <span class="args-label">Arguments:</span>
          <pre class="args-json">{{ argsJson() }}</pre>
        </div>
      }

      @if (hasResult()) {
        <div class="tool-result">
          <span class="result-label">Result:</span>
          <pre class="result-json">{{ formattedResult() }}</pre>
        </div>
      }
    </div>
  `,
  styles: [`
    .tool-call-container {
      background: var(--surface-100);
      border: 1px solid var(--surface-200);
      border-radius: var(--border-radius-md);
      padding: var(--spacing-3);
      margin: var(--spacing-2) 0;
      font-size: var(--font-size-sm);
    }

    .tool-header {
      display: flex;
      align-items: center;
      gap: var(--spacing-2);
      margin-bottom: var(--spacing-2);
    }

    .tool-name {
      font-weight: var(--font-weight-semibold);
      color: var(--surface-800);
    }

    :host ::ng-deep .tool-spinner .p-progress-spinner-circle {
      animation: spin 1s linear infinite;
    }

    .tool-args, .tool-result {
      margin-top: var(--spacing-2);
    }

    .args-label, .result-label {
      font-size: var(--font-size-xs);
      color: var(--surface-500);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .args-json, .result-json {
      background: var(--surface-0);
      border: 1px solid var(--surface-200);
      border-radius: var(--border-radius-sm);
      padding: var(--spacing-2);
      margin-top: var(--spacing-1);
      overflow-x: auto;
      font-family: monospace;
      font-size: 0.8rem;
      max-height: 200px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .result-json {
      background: var(--p-green-50);
      border-color: var(--p-green-200);
    }
  `]
})
export class ToolCallRendererComponent implements ToolRenderer<Record<string, unknown>> {
  // Required by ToolRenderer interface
  toolCall = signal<AngularToolCall<Record<string, unknown>>>({
    args: {},
    status: 'in-progress',
    result: undefined
  });

  // Additional signal for tool name (set externally)
  toolName = signal<string>('Unknown Tool');

  // Computed values for the template
  isInProgress = computed(() => this.toolCall().status === 'in-progress' || this.toolCall().status === 'executing');

  hasArgs = computed(() => {
    const args = this.toolCall().args;
    return args && Object.keys(args).length > 0;
  });

  hasResult = computed(() => {
    const tc = this.toolCall();
    return tc.status === 'complete' && tc.result !== undefined;
  });

  argsJson = computed(() => JSON.stringify(this.toolCall().args, null, 2));

  formattedResult = computed(() => {
    const tc = this.toolCall();
    if (tc.status !== 'complete' || !tc.result) return '';
    try {
      const parsed = JSON.parse(tc.result);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return tc.result;
    }
  });

  statusLabel = computed(() => {
    switch (this.toolCall().status) {
      case 'in-progress': return 'Running';
      case 'executing': return 'Executing';
      case 'complete': return 'Complete';
      default: return 'Tool';
    }
  });

  severity = computed((): 'info' | 'success' | 'danger' => {
    switch (this.toolCall().status) {
      case 'in-progress':
      case 'executing':
        return 'info';
      case 'complete':
        return 'success';
      default:
        return 'info';
    }
  });
}
