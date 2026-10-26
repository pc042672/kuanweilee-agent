import { Component, Input, Output, EventEmitter, signal, computed, inject, ChangeDetectorRef, effect, ViewChild, ElementRef, AfterViewChecked, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule, JsonPipe, UpperCasePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { injectAgentStore } from '@copilotkitnext/angular';
import { randomUUID } from '@copilotkitnext/shared';
import { Message } from '@ag-ui/client';
import { ButtonModule } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { TableModule } from 'primeng/table';
import { Tooltip } from 'primeng/tooltip';
import { ChatSession, ChatSessionService } from '../../shared/services/chat-session.service';
import { AuthService } from '../../shared/services/auth.service';
import {
  ExecutionPlan,
  ExecutionResult,
  Verification,
  CampaignSummary,
  ParsedContent,
  ContentBlock,
  ToolCall,
  WorkflowState,
  parseMessageContent
} from '../../models/chat.models';

@Component({
  selector: 'app-chat-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    JsonPipe,
    UpperCasePipe,
    ButtonModule,
    Tag,
    TableModule,
    Tooltip
  ],
  template: `
    <div class="chat-panel">
      <!-- Messages Area -->
      <div class="messages-area" #messagesContainer>
        @if (messages().length === 0 && !isRunning()) {
          <!-- Welcome Screen -->
          <div class="welcome-screen">
            <div class="welcome-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="currentColor"/>
              </svg>
            </div>
            <h1 class="welcome-title">{{ getGreeting() }}, {{ userName() }}</h1>
            <p class="welcome-subtitle">How can I help you analyze your data today?</p>

            <!-- Quick Actions -->
            <div class="quick-actions">
              <button class="quick-action" (click)="setInput('Show me VIP customers')">
                <i class="pi pi-users"></i>
                <span>VIP Customers</span>
              </button>
              <button class="quick-action" (click)="setInput('Find abandoned cart users')">
                <i class="pi pi-shopping-cart"></i>
                <span>Abandoned Carts</span>
              </button>
              <button class="quick-action" (click)="setInput('Show recent orders')">
                <i class="pi pi-list"></i>
                <span>Recent Orders</span>
              </button>
              <button class="quick-action" (click)="setInput('Customer segments overview')">
                <i class="pi pi-chart-pie"></i>
                <span>Segments</span>
              </button>

            </div>
          </div>
        } @else {
          <!-- Chat Messages -->
          @for (message of filteredMessages(); track message.id) {
            @if (message.role === 'user' || (message.role === 'assistant' && getDisplayItems(message).length > 0)) {
            <div class="message" [class]="message.role">
              @if (message.role === 'user') {
                <!-- User Message -->
                <div class="message-row user-row">
                  <div class="message-bubble user-bubble">
                    <div class="message-content">{{ getMessageContent(message) }}</div>
                  </div>
                </div>
              }

              @if (message.role === 'assistant' && getDisplayItems(message).length > 0) {
                <!-- Assistant Message with interleaved thinking process -->
                <div class="message-row assistant-row">
                  <div class="message-content-wrapper">
                    <!-- Render display items (tool calls grouped with content) -->
                    @let displayItems = getDisplayItems(message);
                    @for (item of displayItems; track $index) {
                      @if (item.type === 'thinking') {
                        <!-- Thinking Process Box -->
                        <div class="thinking-process-standalone">
                          <div class="thinking-process-section" [class.expanded]="isThinkingProcessExpanded(message.id, $index, displayItems)">
                            <button class="thinking-process-header" (click)="toggleThinkingProcess(message.id + '-think-' + $index)">
                              <span class="thinking-label">
                                <i class="pi pi-sparkles"></i>
                                Thinking process
                              </span>
                              <i class="pi" [class.pi-chevron-down]="!isThinkingProcessExpanded(message.id, $index, displayItems)" [class.pi-chevron-up]="isThinkingProcessExpanded(message.id, $index, displayItems)"></i>
                            </button>
                            @if (isThinkingProcessExpanded(message.id, $index, displayItems)) {
                              <div class="thinking-process-body">
                                @for (toolCall of item.toolCalls; track toolCall.id || $index) {
                                  <div class="thinking-step completed">
                                    <span class="step-text">{{ getThinkingStepText(toolCall) }}</span>
                                    <i class="pi pi-check step-icon"></i>
                                  </div>
                                }
                              </div>
                            }
                          </div>
                        </div>
                      } @else {
                        <!-- Content Block -->
                        @let block = item.block;
                        @switch (block.type) {
                          @case ('iteration') {
                            <div class="iteration-indicator">
                              <span>{{ cleanIterationText(block.content) }}</span>
                            </div>
                          }
                          @case ('thinking') {
                            <div class="thinking-block" [class.expanded]="thinkingExpanded[message.id + $index]">
                              <button class="thinking-toggle" (click)="toggleThinking(message.id + $index)">
                                <i class="pi pi-lightbulb"></i>
                                <span>{{ getTruncatedText(block.content, 80) }}</span>
                                <i class="pi" [class.pi-chevron-down]="!thinkingExpanded[message.id + $index]" [class.pi-chevron-up]="thinkingExpanded[message.id + $index]"></i>
                              </button>
                              @if (thinkingExpanded[message.id + $index]) {
                                <div class="thinking-content">{{ block.content }}</div>
                              }
                            </div>
                          }
                          @case ('plan') {
                            @if (block.data) {
                              @let plan = $any(block.data);
                              @let blockId = message.id + '-plan-' + $index;
                              <div class="collapsible-card" [class.expanded]="isBlockExpanded(blockId)">
                                <button class="collapsible-header" (click)="toggleBlock(blockId)">
                                  <span class="collapsible-summary">{{ plan.goal || 'Execution Plan' }}</span>
                                  <i class="pi" [class.pi-chevron-down]="!isBlockExpanded(blockId)" [class.pi-chevron-up]="isBlockExpanded(blockId)"></i>
                                </button>
                                @if (isBlockExpanded(blockId)) {
                                  <div class="collapsible-body">
                                    @if (plan.analysis) {
                                      <p class="plan-analysis">{{ plan.analysis }}</p>
                                    }
                                    @if (plan.tables_needed?.length) {
                                      <div class="plan-section">
                                        <span class="section-label">Tables</span>
                                        <div class="chips-row">
                                          @for (table of plan.tables_needed; track table.name) {
                                            <span class="chip">{{ table.name }}</span>
                                          }
                                        </div>
                                      </div>
                                    }
                                    @if (plan.execution_method) {
                                      <div class="plan-section">
                                        <span class="section-label">Method</span>
                                        <span class="method-badge">{{ plan.execution_method | uppercase }}</span>
                                      </div>
                                    }
                                  </div>
                                }
                              </div>
                            }
                          }
                          @case ('sql_result') {
                            @if (block.data) {
                              @let result = $any(block.data);
                              @let blockId = message.id + '-result-' + $index;
                              <div class="collapsible-card result-type" [class.expanded]="isBlockExpanded(blockId)" [class.success]="result.status === 'success'" [class.error]="result.status === 'error'">
                                <button class="collapsible-header" (click)="toggleBlock(blockId)">
                                  <span class="collapsible-summary">{{ result.explanation || getResultTitle(result.status) }}</span>
                                  <i class="pi" [class.pi-chevron-down]="!isBlockExpanded(blockId)" [class.pi-chevron-up]="isBlockExpanded(blockId)"></i>
                                </button>
                                @if (isBlockExpanded(blockId)) {
                                  <div class="collapsible-body">
                                    <!-- Steps Progress -->
                                    @if (result.sql) {
                                      <div class="steps-indicator">
                                        <i class="pi pi-chevron-up"></i>
                                        <span class="steps-count">{{ result.preview?.row_count || 0 }} rows</span>
                                        <div class="steps-progress">
                                          <div class="progress-bar" [style.width.%]="100"></div>
                                        </div>
                                      </div>
                                    }
                                    <!-- File/SQL indicator -->
                                    <div class="step-item">
                                      <i class="pi pi-file"></i>
                                      <span>Generated SQL query</span>
                                    </div>
                                    <!-- Summary -->
                                    @if (result.validation?.dry_run) {
                                      <div class="step-summary">
                                        <span class="bullet">•</span>
                                        <span>{{ result.validation.dry_run === 'passed' ? 'Query validated successfully' : 'Validation failed' }}</span>
                                      </div>
                                    }
                                    <!-- SQL Code -->
                                    @if (result.sql) {
                                      <div class="sql-code-block compact">
                                        <div class="sql-code-header">
                                          <div class="sql-code-label">
                                            <i class="pi pi-database"></i>
                                            <span>SQL</span>
                                          </div>
                                          <button class="copy-sql-btn" (click)="copyToClipboard(result.sql); $event.stopPropagation()">
                                            <i class="pi pi-copy"></i>
                                          </button>
                                        </div>
                                        <pre class="sql-code-content"><code [innerHTML]="formatSql(result.sql)"></code></pre>
                                      </div>
                                    }
                                    <!-- Preview Table -->
                                    @if (result.preview?.sample?.length) {
                                      <div class="preview-section compact">
                                        <div class="preview-header">
                                          <i class="pi pi-table"></i>
                                          <span>Preview</span>
                                          <span class="row-count">({{ result.preview.row_count }} rows)</span>
                                        </div>
                                        <div class="preview-table-wrapper">
                                          <p-table
                                            [value]="result.preview.sample"
                                            [scrollable]="true"
                                            scrollHeight="150px"
                                            styleClass="p-datatable-sm p-datatable-striped"
                                          >
                                            <ng-template pTemplate="header">
                                              <tr>
                                                @for (col of getTableColumns(result.preview.sample); track col) {
                                                  <th>{{ col }}</th>
                                                }
                                              </tr>
                                            </ng-template>
                                            <ng-template pTemplate="body" let-row>
                                              <tr>
                                                @for (col of getTableColumns(result.preview.sample); track col) {
                                                  <td>{{ row[col] }}</td>
                                                }
                                              </tr>
                                            </ng-template>
                                          </p-table>
                                        </div>
                                      </div>
                                    }
                                    <!-- Actions -->
                                    @if (result.status === 'success' && result.sql) {
                                      <div class="result-actions">
                                        <button pButton icon="pi pi-bookmark" label="Save" class="p-button-text p-button-sm" (click)="onSaveToPlanFromBlock(result); $event.stopPropagation()"></button>
                                        <button pButton icon="pi pi-copy" label="Copy" class="p-button-text p-button-sm" (click)="copyToClipboard(result.sql); $event.stopPropagation()"></button>
                                      </div>
                                    }
                                  </div>
                                }
                              </div>
                            }
                          }
                          @case ('sql_code') {
                            <div class="sql-code-block">
                              <div class="sql-code-header">
                                <div class="sql-code-label">
                                  <i class="pi pi-database"></i>
                                  <span>SQL Query</span>
                                </div>
                                <button
                                  class="copy-sql-btn"
                                  (click)="copyToClipboard(block.content)"
                                  pTooltip="Copy SQL"
                                >
                                  <i class="pi pi-copy"></i>
                                </button>
                              </div>
                              <pre class="sql-code-content"><code [innerHTML]="formatSql(block.content)"></code></pre>
                            </div>
                          }
                          @case ('verification') {
                            @if (block.data) {
                              @let verification = $any(block.data);
                              @let blockId = message.id + '-verify-' + $index;
                              <div class="collapsible-card verification-type" [class.expanded]="isBlockExpanded(blockId)" [class.success]="verification.sufficient" [class.warning]="!verification.sufficient">
                                <button class="collapsible-header" (click)="toggleBlock(blockId)">
                                  <span class="collapsible-summary">{{ verification.sufficient ? 'Verification passed' : 'Needs refinement' }}</span>
                                  <i class="pi" [class.pi-chevron-down]="!isBlockExpanded(blockId)" [class.pi-chevron-up]="isBlockExpanded(blockId)"></i>
                                </button>
                                @if (isBlockExpanded(blockId)) {
                                  <div class="collapsible-body">
                                    @if (verification.feedback) {
                                      <div class="step-summary">
                                        <span class="bullet">•</span>
                                        <span>{{ verification.feedback }}</span>
                                      </div>
                                    }
                                    @if (verification.action && verification.action !== 'complete') {
                                      <div class="step-item">
                                        <i class="pi pi-arrow-right"></i>
                                        <span>Next: {{ verification.action }}</span>
                                      </div>
                                    }
                                  </div>
                                }
                              </div>
                            }
                          }
                          @case ('campaign_summary') {
                            @if (block.data) {
                              @let campaign = $any(block.data);
                              @let blockId = message.id + '-campaign-' + $index;
                              <div class="campaign-summary-card" [class.expanded]="isBlockExpanded(blockId)">
                                <!-- Campaign Header -->
                                <button class="campaign-header" (click)="toggleBlock(blockId)">
                                  <div class="campaign-title-row">
                                    <i class="pi pi-megaphone campaign-icon"></i>
                                    <span class="campaign-title">{{ campaign.campaign_title || 'Campaign Summary' }}</span>
                                  </div>
                                  @if (campaign.target_audience?.count) {
                                    <span class="audience-count-badge">{{ campaign.target_audience.count }} users</span>
                                  }
                                  <i class="pi" [class.pi-chevron-down]="!isBlockExpanded(blockId)" [class.pi-chevron-up]="isBlockExpanded(blockId)"></i>
                                </button>

                                @if (isBlockExpanded(blockId)) {
                                  <div class="campaign-body">
                                    <!-- Target Audience -->
                                    @if (campaign.target_audience) {
                                      <div class="campaign-section">
                                        <div class="campaign-section-header">
                                          <i class="pi pi-users"></i>
                                          <span>Target Audience</span>
                                        </div>
                                        <div class="audience-card">
                                          @if (campaign.target_audience.segment_name) {
                                            <span class="audience-segment">{{ campaign.target_audience.segment_name }}</span>
                                          }
                                          @if (campaign.target_audience.description) {
                                            <p class="audience-desc">{{ campaign.target_audience.description }}</p>
                                          }
                                        </div>
                                      </div>
                                    }

                                    <!-- Audience Insights -->
                                    @if (campaign.audience_insights?.length) {
                                      <div class="campaign-section">
                                        <div class="campaign-section-header">
                                          <i class="pi pi-chart-bar"></i>
                                          <span>Audience Insights</span>
                                        </div>
                                        <div class="insights-grid">
                                          @for (insight of campaign.audience_insights; track $index) {
                                            <div class="insight-card">
                                              <span class="insight-type-badge" [attr.data-type]="insight.insight_type">{{ insight.insight_type }}</span>
                                              <p class="insight-desc">{{ insight.description }}</p>
                                              @if (insight.data_point) {
                                                <p class="insight-data">{{ insight.data_point }}</p>
                                              }
                                            </div>
                                          }
                                        </div>
                                      </div>
                                    }

                                    <!-- Marketing Recommendations -->
                                    @if (campaign.marketing_recommendations?.length) {
                                      <div class="campaign-section">
                                        <div class="campaign-section-header">
                                          <i class="pi pi-star"></i>
                                          <span>Marketing Recommendations</span>
                                        </div>
                                        <div class="recommendations-list">
                                          @for (rec of campaign.marketing_recommendations; track $index) {
                                            <div class="recommendation-card">
                                              <div class="rec-header">
                                                <span class="rec-strategy">{{ rec.strategy }}</span>
                                              </div>
                                              <p class="rec-desc">{{ rec.description }}</p>
                                              @if (rec.tactics?.length) {
                                                <div class="rec-tactics">
                                                  @for (tactic of rec.tactics; track $index) {
                                                    <span class="tactic-chip">{{ tactic }}</span>
                                                  }
                                                </div>
                                              }
                                              @if (rec.expected_outcome) {
                                                <p class="rec-outcome"><strong>Expected:</strong> {{ rec.expected_outcome }}</p>
                                              }
                                            </div>
                                          }
                                        </div>
                                      </div>
                                    }

                                    <!-- Activation Suggestions -->
                                    @if (campaign.activation_suggestions) {
                                      @let activation = campaign.activation_suggestions;
                                      <div class="campaign-section">
                                        <div class="campaign-section-header">
                                          <i class="pi pi-send"></i>
                                          <span>Activation</span>
                                        </div>
                                        <div class="activation-grid">
                                          @if (activation.primary_channel) {
                                            <div class="activation-item">
                                              <span class="activation-label">Channel</span>
                                              <span class="activation-value channel-badge">{{ activation.primary_channel }}</span>
                                            </div>
                                          }
                                          @if (activation.best_timing) {
                                            <div class="activation-item">
                                              <span class="activation-label">Timing</span>
                                              <span class="activation-value">{{ activation.best_timing }}</span>
                                            </div>
                                          }
                                          @if (activation.tone) {
                                            <div class="activation-item">
                                              <span class="activation-label">Tone</span>
                                              <span class="activation-value">{{ activation.tone }}</span>
                                            </div>
                                          }
                                          @if (activation.cta_text) {
                                            <div class="activation-item">
                                              <span class="activation-label">CTA</span>
                                              <span class="activation-value cta-badge">{{ activation.cta_text }}</span>
                                            </div>
                                          }
                                        </div>
                                        @if (activation.subject_lines?.length) {
                                          <div class="subject-lines">
                                            <span class="activation-label">Subject Lines</span>
                                            @for (line of activation.subject_lines; track $index) {
                                              <div class="subject-line-item">
                                                <i class="pi pi-envelope"></i>
                                                <span>{{ line }}</span>
                                              </div>
                                            }
                                          </div>
                                        }
                                      </div>
                                    }

                                    <!-- Next Steps -->
                                    @if (campaign.next_steps?.length) {
                                      <div class="campaign-section">
                                        <div class="campaign-section-header">
                                          <i class="pi pi-list-check"></i>
                                          <span>Next Steps</span>
                                        </div>
                                        <div class="next-steps-list">
                                          @for (step of campaign.next_steps; track $index) {
                                            <div class="next-step-item">
                                              <span class="step-number">{{ $index + 1 }}</span>
                                              <span>{{ step }}</span>
                                            </div>
                                          }
                                        </div>
                                      </div>
                                    }
                                  </div>
                                }
                              </div>
                            }
                          }
                          @case ('completion') {
                            <div class="completion-message">
                              <i class="pi pi-check-circle"></i>
                              <span>{{ block.content }}</span>
                            </div>
                          }
                          @case ('text') {
                            <div class="assistant-text" [innerHTML]="formatText(block.content)"></div>
                          }
                          @default {
                            <div class="assistant-text" [innerHTML]="formatText(block.content)"></div>
                          }
                        }
                      }
                    }

                  </div>
                </div>
              }
            </div>
            }
          }

          @if (isRunning()) {
            <div class="message assistant">
              <div class="message-row assistant-row">
                <div class="thinking-indicator">
                  <div class="thinking-spinner"></div>
                  <span>Analyzing your request...</span>
                </div>
              </div>
            </div>
          }
        }
      </div>

      <!-- Input Area -->
      <div class="input-area">
        <div class="input-container">
          <div class="input-box">
            <button class="input-action-btn" pTooltip="Attach file">
              <i class="pi pi-plus"></i>
            </button>
            <input
              type="text"
              [(ngModel)]="userInput"
              [placeholder]="messages().length === 0 ? 'Type / for commands' : 'Reply...'"
              (keydown.enter)="sendMessage()"
              [disabled]="isRunning()"
              class="chat-input"
            />
            <button class="input-action-btn" pTooltip="Insert template">
              <i class="pi pi-clock"></i>
            </button>
            <div class="model-selector">
              <span>SQL Agent</span>
              <i class="pi pi-chevron-down"></i>
            </div>
            <button
              class="send-btn"
              (click)="sendMessage()"
              [disabled]="isRunning() || !userInput.trim()"
            >
              <i class="pi pi-arrow-up"></i>
            </button>
          </div>
        </div>
        <p class="disclaimer">AI can make mistakes. Please verify important information.</p>
      </div>
    </div>
  `,
  styles: [`
    .chat-panel {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: linear-gradient(180deg, #fafaff 0%, #fcfcff 50%, #f9f8ff 100%);
    }

    /* Welcome Screen */
    .welcome-screen {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: var(--spacing-6);
      text-align: center;
    }

    .welcome-icon {
      width: 56px;
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, var(--primary-700, #7c3aed), var(--primary-500, #a78bfa));
      border-radius: 16px;
      color: white;
      margin-bottom: var(--spacing-4);
      box-shadow: 0 8px 24px rgba(124, 58, 237, 0.25);
    }

    .welcome-title {
      font-size: 2rem;
      font-weight: var(--font-weight-semibold);
      background: linear-gradient(135deg, var(--primary-700, #7c3aed), var(--primary-500, #a78bfa));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin: 0 0 var(--spacing-2) 0;
    }

    .welcome-subtitle {
      font-size: var(--font-size-base);
      color: var(--text-color-secondary, #71717a);
      margin: 0 0 var(--spacing-5) 0;
    }

    .quick-actions {
      display: flex;
      gap: var(--spacing-3);
      flex-wrap: wrap;
      justify-content: center;
    }

    .quick-action {
      display: flex;
      align-items: center;
      gap: var(--spacing-2);
      padding: 12px 20px;
      background: rgba(255, 255, 255, 0.8);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(124, 58, 237, 0.15);
      border-radius: 24px;
      font-size: var(--font-size-sm);
      color: var(--text-color, #3f3f46);
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        background: rgba(124, 58, 237, 0.08);
        border-color: rgba(124, 58, 237, 0.3);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.15);
      }

      i {
        font-size: 1rem;
        color: var(--primary-700, #7c3aed);
      }
    }

    /* Messages Area */
    .messages-area {
      flex: 1;
      overflow-y: auto;
      padding: var(--spacing-6);
      display: flex;
      flex-direction: column;
      gap: var(--spacing-5);
      max-width: 800px;
      margin: 0 auto;
      width: 100%;
      scrollbar-width: none; /* Firefox */
      -ms-overflow-style: none; /* IE/Edge */

      &::-webkit-scrollbar {
        display: none; /* Chrome/Safari/Opera */
      }
    }

    .message-row {
      display: flex;
      width: 100%;

      &.user-row {
        justify-content: flex-end;
      }

      &.assistant-row {
        justify-content: flex-start;
      }
    }

    /* User Message */
    .user-bubble {
      padding: var(--spacing-3) var(--spacing-4);
      background: linear-gradient(135deg, var(--primary-700, #7c3aed), var(--primary-500, #a78bfa));
      border-radius: 18px;
      color: white;
      box-shadow: 0 4px 12px rgba(124, 58, 237, 0.2);

      .message-content {
        font-size: var(--font-size-sm);
        line-height: 1.5;
      }
    }

    /* Assistant Message */
    .message-content-wrapper {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-3);
      max-width: 100%;
    }

    .thinking-section {
      .thinking-toggle {
        display: flex;
        align-items: center;
        gap: var(--spacing-2);
        padding: var(--spacing-2) var(--spacing-3);
        background: rgba(124, 58, 237, 0.08);
        border: none;
        border-radius: 8px;
        font-size: var(--font-size-xs);
        color: var(--primary-700, #7c3aed);
        cursor: pointer;

        &:hover {
          background: rgba(124, 58, 237, 0.12);
        }

        i {
          font-size: 0.75rem;
        }
      }
    }

    .assistant-text {
      font-size: 14px;
      line-height: 1.6;
      color: #444;
      padding: 14px 16px;
      background: #f8f8f6;
      border-radius: 10px;
    }

    :host ::ng-deep .assistant-text {
      strong {
        font-weight: 600;
      }

      code {
        background: rgba(0, 0, 0, 0.06);
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #333;
      }
    }

    .message-actions {
      display: flex;
      gap: var(--spacing-1);
      margin-top: var(--spacing-2);
      opacity: 0;
      transition: opacity 0.2s ease;
    }

    .message-content-wrapper:hover .message-actions {
      opacity: 1;
    }

    .action-btn {
      width: 28px;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      border-radius: 6px;
      color: var(--text-color-secondary, #a1a1aa);
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        background: rgba(0, 0, 0, 0.05);
        color: var(--text-color, #3f3f46);
      }

      i {
        font-size: 0.75rem;
      }
    }

    /* Plan & Result Cards */
    .plan-card, .result-card {
      padding: var(--spacing-4);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--surface-200, #e4e4e7);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
    }

    .plan-card {
      border-left: 3px solid var(--primary-700, #7c3aed);

      .plan-header {
        display: flex;
        align-items: center;
        gap: var(--spacing-2);
        color: var(--primary-700, #7c3aed);
        font-weight: var(--font-weight-semibold);
        font-size: var(--font-size-sm);
        margin-bottom: var(--spacing-3);
      }

      .plan-item {
        display: flex;
        gap: var(--spacing-2);
        margin-bottom: var(--spacing-2);
        font-size: var(--font-size-sm);

        .label {
          color: var(--text-color-secondary, #71717a);
          min-width: 60px;
        }
      }
    }

    .result-card {
      &.success { border-left: 3px solid var(--success-color, #10b981); }
      &.error { border-left: 3px solid var(--error-color, #ef4444); }
      &.needs_input { border-left: 3px solid var(--warning-color, #f59e0b); }

      .result-header {
        display: flex;
        align-items: center;
        gap: var(--spacing-2);
        font-weight: var(--font-weight-semibold);
        font-size: var(--font-size-sm);
        margin-bottom: var(--spacing-3);
      }

      &.success .result-header { color: var(--success-color, #10b981); }
      &.error .result-header { color: var(--error-color, #ef4444); }
      &.needs_input .result-header { color: var(--warning-color, #f59e0b); }
    }

    .sql-block {
      position: relative;
      background: #1e1e1e;
      border-radius: 8px;
      padding: var(--spacing-3);
      margin-bottom: var(--spacing-3);

      pre {
        margin: 0;
        overflow-x: auto;

        code {
          color: #a5d6ff;
          font-family: 'JetBrains Mono', monospace;
          font-size: var(--font-size-xs);
        }
      }

      .copy-btn {
        position: absolute;
        top: var(--spacing-2);
        right: var(--spacing-2);
        color: white;
        opacity: 0.6;

        &:hover { opacity: 1; }
      }
    }

    .explanation {
      font-size: var(--font-size-sm);
      color: var(--text-color-secondary, #71717a);
      margin: 0;
    }

    .result-actions {
      margin-top: var(--spacing-3);
      padding-top: var(--spacing-3);
      border-top: 1px solid var(--surface-200, #e4e4e7);
      display: flex;
      gap: var(--spacing-2);
    }

    /* Thinking Process Standalone */
    .thinking-process-standalone {
      margin-bottom: var(--spacing-3);
      max-width: 320px;
    }

    /* Thinking Process Section */
    .thinking-process-section {
      background: rgba(124, 58, 237, 0.03);
      border: 1px dashed rgba(124, 58, 237, 0.2);
      border-radius: 12px;
      margin-bottom: var(--spacing-3);
      overflow: hidden;

      .thinking-process-header {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 14px;
        background: transparent;
        border: none;
        cursor: pointer;
        transition: background 0.2s ease;

        &:hover {
          background: rgba(124, 58, 237, 0.04);
        }

        .thinking-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          font-weight: 500;
          color: var(--primary-700, #7c3aed);

          i {
            font-size: 14px;
          }
        }

        .pi-chevron-down, .pi-chevron-up {
          font-size: 12px;
          color: var(--text-color-secondary, #71717a);
        }
      }

      .thinking-process-body {
        padding: 0 14px 14px 14px;
        display: flex;
        flex-direction: column;
        gap: 6px;

        .thinking-step {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 6px 10px;
          background: rgba(255, 255, 255, 0.6);
          border-radius: 6px;
          font-size: 12px;
          color: var(--text-color-secondary, #71717a);

          &.completed {
            color: var(--text-color, #3f3f46);

            .step-icon {
              color: var(--success-color, #10b981);
            }
          }

          &.pending {
            .step-text {
              opacity: 0.7;
            }
          }

          .step-icon {
            font-size: 11px;
          }
        }
      }

      /* Execution phase variant (green/teal color) */
      &.execution-phase {
        background: rgba(16, 185, 129, 0.03);
        border-color: rgba(16, 185, 129, 0.2);

        .thinking-process-header {
          &:hover {
            background: rgba(16, 185, 129, 0.04);
          }

          .thinking-label {
            color: var(--success-color, #10b981);
          }
        }
      }
    }

    /* Iteration Indicator */
    .iteration-indicator {
      display: inline-flex;
      align-items: center;
      padding: 6px 12px;
      background: rgba(124, 58, 237, 0.06);
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
      color: #7c3aed;
    }

    /* Thinking Block */
    .thinking-block {
      .thinking-toggle {
        display: flex;
        align-items: center;
        gap: var(--spacing-2);
        padding: var(--spacing-2) var(--spacing-3);
        background: rgba(251, 191, 36, 0.1);
        border: none;
        border-radius: 8px;
        font-size: var(--font-size-xs);
        color: var(--warning-color, #f59e0b);
        cursor: pointer;
        text-align: left;
        width: 100%;
        transition: all 0.2s ease;

        &:hover {
          background: rgba(251, 191, 36, 0.15);
        }

        span {
          flex: 1;
        }

        i:first-child {
          font-size: 0.875rem;
        }

        i:last-child {
          font-size: 0.625rem;
        }
      }

      .thinking-content {
        padding: var(--spacing-3);
        margin-top: var(--spacing-1);
        background: rgba(251, 191, 36, 0.05);
        border-radius: 8px;
        font-size: var(--font-size-sm);
        color: var(--text-color, #3f3f46);
        line-height: 1.5;
      }
    }

    /* Verification Card */
    .verification-card {
      padding: var(--spacing-3);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.9);
      border: 1px solid var(--surface-200, #e4e4e7);

      &.success {
        border-left: 3px solid var(--success-color, #10b981);
        background: rgba(16, 185, 129, 0.05);

        .verification-header {
          color: var(--success-color, #10b981);
        }
      }

      &.needs-work {
        border-left: 3px solid var(--warning-color, #f59e0b);
        background: rgba(245, 158, 11, 0.05);

        .verification-header {
          color: var(--warning-color, #f59e0b);
        }
      }

      .verification-header {
        display: flex;
        align-items: center;
        gap: var(--spacing-2);
        font-size: var(--font-size-sm);
        font-weight: var(--font-weight-semibold);
        margin-bottom: var(--spacing-2);

        i {
          font-size: 1rem;
        }
      }

      .verification-feedback {
        font-size: var(--font-size-sm);
        color: var(--text-color, #3f3f46);
        margin: 0;
        line-height: 1.5;
      }

      .verification-action {
        display: flex;
        align-items: center;
        gap: var(--spacing-2);
        margin-top: var(--spacing-2);

        .action-label {
          font-size: var(--font-size-xs);
          color: var(--text-color-secondary, #71717a);
        }
      }
    }

    /* Completion Message */
    /* Campaign Summary Card */
    .campaign-summary-card {
      background: var(--surface-0, #ffffff);
      border: 1px solid var(--surface-200, #e4e4e7);
      border-radius: 12px;
      overflow: hidden;
      border-left: 3px solid var(--primary-700, #7c3aed);
    }

    .campaign-header {
      width: 100%;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px 20px;
      background: linear-gradient(135deg, rgba(124, 58, 237, 0.06), rgba(124, 58, 237, 0.02));
      border: none;
      cursor: pointer;
      transition: background 0.2s ease;

      &:hover {
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.1), rgba(124, 58, 237, 0.04));
      }

      .campaign-title-row {
        display: flex;
        align-items: center;
        gap: 10px;
        flex: 1;
        min-width: 0;
      }

      .campaign-icon {
        font-size: 18px;
        color: var(--primary-700, #7c3aed);
      }

      .campaign-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-color, #3f3f46);
        text-align: left;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .audience-count-badge {
        padding: 4px 12px;
        background: var(--primary-100, #ede9fe);
        color: var(--primary-700, #7c3aed);
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        white-space: nowrap;
      }

      > .pi-chevron-down, > .pi-chevron-up {
        color: var(--text-color-secondary, #71717a);
        font-size: 12px;
      }
    }

    .campaign-body {
      padding: 4px 20px 20px;
    }

    .campaign-section {
      padding-top: 16px;

      & + .campaign-section {
        border-top: 1px solid var(--surface-100, #f4f4f5);
        margin-top: 4px;
      }
    }

    .campaign-section-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 600;
      color: var(--text-color, #3f3f46);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 12px;

      i {
        font-size: 14px;
        color: var(--primary-700, #7c3aed);
      }
    }

    .audience-card {
      background: var(--surface-50, #fafafa);
      border-radius: 8px;
      padding: 12px 16px;
    }

    .audience-segment {
      display: inline-block;
      padding: 3px 10px;
      background: var(--primary-100, #ede9fe);
      color: var(--primary-700, #7c3aed);
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 8px;
    }

    .audience-desc {
      font-size: 13px;
      color: var(--text-color-secondary, #71717a);
      line-height: 1.5;
      margin: 0;
    }

    .insights-grid {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .insight-card {
      background: var(--surface-50, #fafafa);
      border-radius: 8px;
      padding: 12px 16px;
    }

    .insight-type-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      margin-bottom: 6px;
      background: var(--surface-200, #e4e4e7);
      color: var(--text-color-secondary, #71717a);

      &[data-type="value"] {
        background: #d1fae5;
        color: #065f46;
      }
      &[data-type="behavior"] {
        background: #dbeafe;
        color: #1d4ed8;
      }
      &[data-type="preference"] {
        background: #fef3c7;
        color: #92400e;
      }
    }

    .insight-desc {
      font-size: 13px;
      color: var(--text-color, #3f3f46);
      line-height: 1.5;
      margin: 0 0 4px 0;
    }

    .insight-data {
      font-size: 12px;
      color: var(--text-color-secondary, #71717a);
      margin: 0;
      font-style: italic;
    }

    .recommendations-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .recommendation-card {
      background: var(--surface-50, #fafafa);
      border-radius: 8px;
      padding: 12px 16px;
    }

    .rec-header {
      margin-bottom: 6px;
    }

    .rec-strategy {
      font-size: 14px;
      font-weight: 600;
      color: var(--primary-700, #7c3aed);
    }

    .rec-desc {
      font-size: 13px;
      color: var(--text-color, #3f3f46);
      line-height: 1.5;
      margin: 0 0 8px 0;
    }

    .rec-tactics {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 8px;
    }

    .tactic-chip {
      display: inline-block;
      padding: 3px 10px;
      background: var(--surface-100, #f4f4f5);
      border-radius: 6px;
      font-size: 12px;
      color: var(--text-color, #3f3f46);
    }

    .rec-outcome {
      font-size: 12px;
      color: var(--text-color-secondary, #71717a);
      margin: 0;

      strong {
        color: #10b981;
      }
    }

    .activation-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 12px;
    }

    .activation-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .activation-label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      color: var(--text-color-secondary, #71717a);
    }

    .activation-value {
      font-size: 13px;
      color: var(--text-color, #3f3f46);
      font-weight: 500;

      &.channel-badge {
        display: inline-block;
        padding: 3px 10px;
        background: var(--primary-100, #ede9fe);
        color: var(--primary-700, #7c3aed);
        border-radius: 6px;
        width: fit-content;
        font-weight: 600;
      }

      &.cta-badge {
        display: inline-block;
        padding: 3px 10px;
        background: #d1fae5;
        color: #065f46;
        border-radius: 6px;
        width: fit-content;
        font-weight: 600;
      }
    }

    .subject-lines {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .subject-line-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      background: var(--surface-50, #fafafa);
      border-radius: 6px;
      font-size: 13px;
      color: var(--text-color, #3f3f46);

      i {
        font-size: 12px;
        color: var(--primary-700, #7c3aed);
      }
    }

    .next-steps-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .next-step-item {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      font-size: 13px;
      color: var(--text-color, #3f3f46);
      line-height: 1.5;

      .step-number {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        min-width: 22px;
        background: var(--primary-100, #ede9fe);
        color: var(--primary-700, #7c3aed);
        border-radius: 50%;
        font-size: 11px;
        font-weight: 700;
      }
    }

    .completion-message {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 12px 18px;
      background: linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(16, 185, 129, 0.03));
      border-radius: 10px;
      font-size: 14px;
      font-weight: 500;
      color: #10b981;

      i {
        font-size: 18px;
      }
    }

    /* Preview Section */
    .preview-section {
      margin-top: var(--spacing-3);
      border-top: 1px solid var(--surface-200, #e4e4e7);
      padding-top: var(--spacing-3);

      .preview-header {
        display: flex;
        align-items: center;
        gap: var(--spacing-2);
        font-size: var(--font-size-sm);
        font-weight: var(--font-weight-medium);
        color: var(--text-color, #3f3f46);
        margin-bottom: var(--spacing-2);

        i {
          color: var(--primary-700, #7c3aed);
        }

        .row-count {
          font-weight: normal;
          color: var(--text-color-secondary, #71717a);
        }
      }

      .preview-table-wrapper {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid var(--surface-200, #e4e4e7);
      }
    }

    /* SQL Block Enhanced */
    .sql-block {
      position: relative;
      background: #1e1e1e;
      border-radius: 8px;
      overflow: hidden;

      .sql-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--spacing-2) var(--spacing-3);
        background: rgba(255, 255, 255, 0.05);
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);

        span {
          font-size: var(--font-size-xs);
          color: rgba(255, 255, 255, 0.6);
          font-weight: var(--font-weight-medium);
        }

        .copy-btn {
          color: white;
          opacity: 0.6;
          padding: 4px 8px;

          &:hover { opacity: 1; }
        }
      }

      pre {
        margin: 0;
        padding: var(--spacing-3);
        overflow-x: auto;

        code {
          color: #a5d6ff;
          font-family: 'JetBrains Mono', monospace;
          font-size: var(--font-size-xs);
        }
      }
    }

    /* Tables in Plan */
    .tables-item {
      flex-direction: column !important;
      align-items: flex-start !important;

      .tables-list {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-2);
        margin-top: var(--spacing-1);
      }

      .table-chip {
        display: flex;
        align-items: center;
        gap: var(--spacing-1);
        padding: 4px 10px;
        background: rgba(124, 58, 237, 0.08);
        border-radius: 6px;
        font-size: var(--font-size-xs);
        color: var(--primary-700, #7c3aed);

        i {
          font-size: 0.625rem;
        }

        .table-role {
          color: var(--text-color-secondary, #71717a);
          font-size: 10px;
        }
      }
    }

    .validation-badge {
      margin-left: auto;
    }

    /* SQL Code Block */
    .sql-code-block {
      background: #1e1e2e;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);

      .sql-code-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--spacing-2) var(--spacing-3);
        background: rgba(124, 58, 237, 0.15);
        border-bottom: 1px solid rgba(124, 58, 237, 0.2);

        .sql-code-label {
          display: flex;
          align-items: center;
          gap: var(--spacing-2);
          color: #cba6f7;
          font-size: var(--font-size-xs);
          font-weight: var(--font-weight-medium);

          i {
            font-size: 0.875rem;
          }
        }

        .copy-sql-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          background: rgba(255, 255, 255, 0.1);
          border: none;
          border-radius: 6px;
          color: rgba(255, 255, 255, 0.7);
          cursor: pointer;
          transition: all 0.2s ease;

          &:hover {
            background: rgba(255, 255, 255, 0.2);
            color: white;
          }

          i {
            font-size: 0.75rem;
          }
        }
      }

      .sql-code-content {
        margin: 0;
        padding: var(--spacing-4);
        overflow-x: auto;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 13px;
        line-height: 1.6;
        color: #cdd6f4;

        code {
          display: block;
          white-space: pre-wrap;
          word-break: break-word;
        }
      }
    }

    :host ::ng-deep {
      .sql-keyword {
        color: #cba6f7;
        font-weight: 600;
      }

      .sql-string {
        color: #a6e3a1;
      }

      .sql-table {
        color: #89b4fa;
      }

      .sql-number {
        color: #fab387;
      }
    }

    /* Collapsible Cards - Clean Minimal Style */
    .collapsible-card {
      background: #f8f8f6;
      border-radius: 10px;
      overflow: hidden;

      &.verification-type.success {
        border-left: 3px solid var(--success-color, #10b981);
      }

      &.verification-type.warning {
        border-left: 3px solid var(--warning-color, #f59e0b);
      }

      .collapsible-header {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 16px;
        background: transparent;
        border: none;
        cursor: pointer;
        text-align: left;
        transition: background 0.15s ease;

        &:hover {
          background: rgba(0, 0, 0, 0.02);
        }

        .collapsible-summary {
          flex: 1;
          font-size: 14px;
          color: #333;
          line-height: 1.5;
          margin-right: 12px;
        }

        .pi-chevron-down, .pi-chevron-up {
          font-size: 11px;
          color: #999;
          flex-shrink: 0;
        }
      }

      .collapsible-body {
        padding: 12px 16px 16px;
        border-top: 1px solid rgba(0, 0, 0, 0.04);
      }
    }

    /* Steps Indicator */
    .steps-indicator {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 0 12px;

      .pi-chevron-up {
        font-size: 10px;
        color: #888;
      }

      .steps-count {
        font-size: 13px;
        font-weight: 500;
        color: #444;
      }

      .steps-progress {
        flex: 1;
        height: 3px;
        background: #e8e8e8;
        border-radius: 2px;
        overflow: hidden;

        .progress-bar {
          height: 100%;
          background: #3b82f6;
          border-radius: 2px;
        }
      }
    }

    /* Step Items */
    .step-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 6px 0;
      font-size: 13px;
      color: #555;
      border-left: 2px solid #e0e0e0;
      padding-left: 12px;
      margin-left: 4px;

      .pi {
        font-size: 13px;
        color: #888;
      }
    }

    .step-summary {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 6px 0;
      font-size: 13px;
      color: #666;
      line-height: 1.5;

      .bullet {
        color: #f59e0b;
        flex-shrink: 0;
      }
    }

    /* Plan Section */
    .plan-analysis {
      font-size: 13px;
      color: #555;
      line-height: 1.5;
      margin: 12px 0;
      padding: 12px;
      background: rgba(255, 255, 255, 0.6);
      border-radius: 8px;
    }

    .plan-section {
      margin-top: 12px;

      .section-label {
        display: block;
        font-size: 11px;
        font-weight: 600;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
      }

      .method-badge {
        display: inline-block;
        padding: 4px 10px;
        background: rgba(59, 130, 246, 0.1);
        color: #3b82f6;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
      }
    }

    .chips-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;

      .chip {
        display: inline-block;
        padding: 4px 10px;
        background: rgba(0, 0, 0, 0.05);
        color: #555;
        border-radius: 4px;
        font-size: 12px;
      }
    }

    /* Compact SQL Block */
    .sql-code-block.compact {
      margin-top: 12px;

      .sql-code-header {
        padding: 8px 12px;
      }

      .sql-code-content {
        padding: 12px;
        font-size: 12px;
        max-height: 200px;
        overflow-y: auto;
      }
    }

    /* Compact Preview */
    .preview-section.compact {
      margin-top: 12px;
      padding-top: 12px;

      .preview-header {
        margin-bottom: 8px;

        i {
          font-size: 14px;
        }

        span {
          font-size: 13px;
        }
      }
    }

    /* Result Actions in Collapsible */
    .collapsible-card .result-actions {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid rgba(0, 0, 0, 0.06);
      display: flex;
      gap: 8px;

      .p-button-text {
        font-size: 12px;
        color: #666;

        &:hover {
          background: rgba(0, 0, 0, 0.05);
          color: #333;
        }
      }
    }

    /* Preview Table Styles */
    :host ::ng-deep .preview-table-wrapper {
      .p-datatable {
        .p-datatable-thead > tr > th {
          background: var(--surface-50, #fafafa);
          padding: var(--spacing-2) var(--spacing-3);
          font-size: var(--font-size-xs);
          font-weight: var(--font-weight-semibold);
          color: var(--text-color-secondary, #71717a);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          border-bottom: 1px solid var(--surface-200, #e4e4e7);
        }

        .p-datatable-tbody > tr > td {
          padding: var(--spacing-2) var(--spacing-3);
          font-size: var(--font-size-xs);
          color: var(--text-color, #3f3f46);
          border-bottom: 1px solid var(--surface-100, #f4f4f5);
        }

        .p-datatable-tbody > tr:hover {
          background: rgba(124, 58, 237, 0.04);
        }

        .p-datatable-tbody > tr:nth-child(even) {
          background: var(--surface-50, #fafafa);
        }
      }
    }

    /* Thinking Indicator */
    .thinking-indicator {
      display: flex;
      align-items: center;
      gap: var(--spacing-3);
      padding: var(--spacing-3) var(--spacing-4);
      background: rgba(124, 58, 237, 0.08);
      border-radius: 12px;
      font-size: var(--font-size-sm);
      color: var(--primary-700, #7c3aed);
    }

    .thinking-spinner {
      width: 16px;
      height: 16px;
      border: 2px solid var(--primary-700, #7c3aed);
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    /* Input Area */
    .input-area {
      padding: var(--spacing-4) var(--spacing-6) var(--spacing-3);
      max-width: 800px;
      margin: 0 auto;
      width: 100%;
    }

    .input-container {
      width: 100%;
    }

    .input-box {
      display: flex;
      align-items: center;
      gap: var(--spacing-2);
      padding: var(--spacing-2) var(--spacing-3);
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--surface-200, #e4e4e7);
      border-radius: 24px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
      transition: all 0.2s ease;

      &:focus-within {
        border-color: var(--primary-light, #a78bfa);
        box-shadow: 0 4px 20px rgba(124, 58, 237, 0.15);
      }
    }

    .input-action-btn {
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      border-radius: 8px;
      color: var(--text-color-secondary, #71717a);
      cursor: pointer;
      flex-shrink: 0;
      transition: all 0.2s ease;

      &:hover {
        background: rgba(124, 58, 237, 0.08);
        color: var(--primary-700, #7c3aed);
      }
    }

    .chat-input {
      flex: 1;
      padding: 8px 0;
      border: none;
      background: transparent;
      font-size: var(--font-size-sm);
      color: var(--text-color, #3f3f46);
      outline: none;

      &::placeholder {
        color: var(--text-color-secondary, #71717a);
      }
    }

    .model-selector {
      display: flex;
      align-items: center;
      gap: var(--spacing-1);
      padding: 6px 12px;
      background: rgba(124, 58, 237, 0.08);
      border-radius: 8px;
      font-size: var(--font-size-xs);
      color: var(--primary-700, #7c3aed);
      cursor: pointer;
      flex-shrink: 0;
      transition: all 0.2s ease;

      &:hover {
        background: rgba(124, 58, 237, 0.12);
      }

      i {
        font-size: 0.625rem;
      }
    }

    .send-btn {
      width: 36px;
      height: 36px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, var(--primary-700, #7c3aed), var(--primary-dark, #6d28d9));
      border: none;
      border-radius: 50%;
      color: white;
      cursor: pointer;
      flex-shrink: 0;
      transition: all 0.2s ease;
      box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);

      &:hover:not(:disabled) {
        transform: scale(1.05);
        box-shadow: 0 6px 16px rgba(124, 58, 237, 0.4);
      }

      &:disabled {
        background: var(--surface-200, #e4e4e7);
        color: var(--text-color-secondary, #71717a);
        cursor: not-allowed;
        box-shadow: none;
      }

      i {
        font-size: 1rem;
      }
    }

    .disclaimer {
      text-align: center;
      font-size: var(--font-size-xs);
      color: var(--text-color-secondary, #71717a);
      margin: var(--spacing-3) 0 0 0;
    }
  `]
})
export class ChatPanelComponent implements AfterViewChecked, OnChanges {
  @Input() session: ChatSession | null = null;
  @Output() saveToPlan = new EventEmitter<{ goal: string; sql?: string }>();

  @ViewChild('messagesContainer') private messagesContainer!: ElementRef<HTMLDivElement>;

  private chatSessionService = inject(ChatSessionService);
  private authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private shouldScrollToBottom = true;

  userInput = '';
  thinkingExpanded: Record<string, boolean> = {};
  toolCallExpanded: Record<string, boolean> = {};
  blockExpanded: Record<string, boolean> = {};
  thinkingProcessExpanded: Record<string, boolean> = {};

  // Workflow state signals (from STATE_DELTA events)
  workflowState = signal<WorkflowState | null>(null);
  executionPlan = signal<ExecutionPlan | null>(null);
  executionResult = signal<ExecutionResult | null>(null);
  verification = signal<Verification | null>(null);
  campaignSummary = signal<any | null>(null);

  // Tool calls tracking (keyed by message ID)
  private toolCallsMap = new Map<string, ToolCall[]>();
  private currentToolCalls: ToolCall[] = [];

  // CopilotKit integration
  private agentStore = injectAgentStore('revive_ai');

  messages = computed(() => {
    return this.agentStore()?.messages() ?? [];
  });

  // Filter out empty assistant messages
  filteredMessages = computed(() => {
    const msgs = this.messages();
    return msgs.filter(msg => {
      if (msg.role === 'user') return true;
      if (msg.role === 'assistant') {
        return this.hasVisibleContent(msg);
      }
      return true;
    });
  });

  isRunning = computed(() => {
    return this.agentStore()?.isRunning() ?? false;
  });

  userName = computed(() => {
    const user = this.authService.currentUser();
    return user?.name || 'there';
  });

  constructor() {
    effect(() => {
      const msgs = this.messages();
      const session = this.session;
      if (session && msgs.length > 0) {
        // Save messages to session
      }
      // Trigger scroll on message changes
      this.shouldScrollToBottom = true;

      // Associate pending tool calls with new assistant messages
      if (this.currentToolCalls.length > 0) {
        const latestAssistantMsg = msgs.filter(m => m.role === 'assistant').pop();
        if (latestAssistantMsg && !this.toolCallsMap.has(latestAssistantMsg.id)) {
          this.toolCallsMap.set(latestAssistantMsg.id, [...this.currentToolCalls]);
        }
      }
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    const change = changes['session'];
    if (!change) return;
    const current: ChatSession | null = change.currentValue;
    if (!current || current.id === change.previousValue?.id) return;
    void this.switchThread(current);
  }

  /** Point the AG-UI agent at the selected session's thread and restore its
   *  history (backend session id == AG-UI thread id). */
  private async switchThread(session: ChatSession): Promise<void> {
    const agent = this.agentStore()?.agent;
    if (!agent) return;
    agent.threadId = session.id;
    const history = await this.chatSessionService.loadMessages(session.id);
    agent.messages = [];
    for (const m of history) {
      agent.addMessage({
        id: m.id,
        role: m.role,
        content: m.content,
      } as Message);
    }
    this.toolCallsMap.clear();
    this.currentToolCalls = [];
    this.workflowState.set(null);
    this.executionPlan.set(null);
    this.executionResult.set(null);
    this.verification.set(null);
    this.campaignSummary.set(null);
    this.shouldScrollToBottom = true;
    this.cdr.markForCheck();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  private scrollToBottom(): void {
    if (this.messagesContainer?.nativeElement) {
      const element = this.messagesContainer.nativeElement;
      element.scrollTop = element.scrollHeight;
    }
  }

  getGreeting(): string {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  }

  setInput(text: string): void {
    this.userInput = text;
  }

  toggleThinking(messageId: string): void {
    this.thinkingExpanded[messageId] = !this.thinkingExpanded[messageId];
  }

  toggleBlock(blockId: string): void {
    // Default is true (expanded), so toggle from current state
    const currentState = this.blockExpanded[blockId] ?? true;
    this.blockExpanded[blockId] = !currentState;
  }

  isBlockExpanded(blockId: string): boolean {
    // Default to expanded (true) for plan/result cards
    return this.blockExpanded[blockId] ?? true;
  }

  /**
   * Check if thinking process should be expanded.
   * - Expanded by default while active (no content after it)
   * - Collapsed when content appears after it
   * - User can manually toggle
   */
  isThinkingProcessExpanded(messageId: string, itemIndex: number, displayItems: Array<{ type: string }>): boolean {
    const key = messageId + '-think-' + itemIndex;

    // If user has manually toggled, use that state
    if (this.thinkingProcessExpanded[key] !== undefined) {
      return this.thinkingProcessExpanded[key];
    }

    // Auto-expand if this is the last item (still active, no content after)
    // Auto-collapse if there's content after this thinking box
    const hasContentAfter = displayItems.slice(itemIndex + 1).some(item => item.type !== 'thinking');
    return !hasContentAfter;
  }

  getThinkingText(message: Message): string | null {
    // Extract thinking/reasoning from message if present
    if (typeof message.content === 'string') {
      const match = message.content.match(/^(Analyzing|Processing|Looking|Checking|Searching).*?\./);
      if (match) return match[0];
    }
    return null;
  }

  async sendMessage(): Promise<void> {
    const input = this.userInput.trim();
    if (!input || this.isRunning()) return;

    const agent = this.agentStore()?.agent;
    if (!agent) return;

    this.userInput = '';

    const newMessage: Message = {
      id: randomUUID(),
      role: 'user',
      content: input
    };

    agent.addMessage(newMessage);
    this.cdr.markForCheck();

    // Reset tool calls for this run
    this.currentToolCalls = [];

    try {
      await agent.runAgent({}, {
        onRunStartedEvent: (event: any) => {
          this.cdr.detectChanges();
        },
        onRunFinishedEvent: (event: any) => {
          // Final association of tool calls
          const msgs = this.messages();
          const latestAssistantMsg = msgs.filter(m => m.role === 'assistant').pop();
          if (latestAssistantMsg && this.currentToolCalls.length > 0) {
            this.toolCallsMap.set(latestAssistantMsg.id, [...this.currentToolCalls]);
          }
          this.cdr.detectChanges();
        },
        onTextMessageStartEvent: (event: any) => {
          // Associate any existing tool calls with latest assistant message
          if (this.currentToolCalls.length > 0) {
            const msgs = this.messages();
            const latestAssistantMsg = msgs.filter(m => m.role === 'assistant').pop();
            if (latestAssistantMsg) {
              this.toolCallsMap.set(latestAssistantMsg.id, [...this.currentToolCalls]);
            }
          }
          this.cdr.detectChanges();
        },
        onTextMessageEndEvent: (event: any) => {
          // When text message ends, associate any tool calls collected so far
          if (this.currentToolCalls.length > 0) {
            const msgs = this.messages();
            const latestAssistantMsg = msgs.filter(m => m.role === 'assistant').pop();
            if (latestAssistantMsg) {
              this.toolCallsMap.set(latestAssistantMsg.id, [...this.currentToolCalls]);
            }
          }
          this.cdr.detectChanges();
        },
        onToolCallStartEvent: (event: any) => {
          const toolCall: ToolCall = {
            id: event.toolCallId,
            name: event.toolCallName || event.name || '',
            args: {},
            status: 'running'
          };
          this.currentToolCalls.push(toolCall);

          // Find the latest assistant message from messages array
          const msgs = this.messages();
          const latestAssistantMsg = msgs.filter(m => m.role === 'assistant').pop();
          if (latestAssistantMsg) {
            this.toolCallsMap.set(latestAssistantMsg.id, [...this.currentToolCalls]);
          }
          this.cdr.detectChanges();
        },
        onToolCallArgsEvent: (event: any) => {
          const toolCall = this.currentToolCalls.find(tc => tc.id === event.toolCallId);
          if (toolCall && event.delta) {
            try {
              toolCall.args = JSON.parse(event.delta);
            } catch {
              // Args might be streamed in chunks
            }
          }
          // Update the map using latest assistant message
          const msgs = this.messages();
          const latestAssistantMsg = msgs.filter(m => m.role === 'assistant').pop();
          if (latestAssistantMsg) {
            this.toolCallsMap.set(latestAssistantMsg.id, [...this.currentToolCalls]);
          }
          this.cdr.detectChanges();
        },
        onToolCallResultEvent: (event: any) => {
          const toolCall = this.currentToolCalls.find(tc => tc.id === event.toolCallId);
          if (toolCall) {
            toolCall.result = event.content;
            toolCall.status = 'completed';
          }
          // Update the map using latest assistant message
          const msgs = this.messages();
          const latestAssistantMsg = msgs.filter(m => m.role === 'assistant').pop();
          if (latestAssistantMsg) {
            this.toolCallsMap.set(latestAssistantMsg.id, [...this.currentToolCalls]);
          }
          this.cdr.detectChanges();
        },
        onStateDeltaEvent: (event: any) => {
          const delta = event.delta;

          // Update workflow state
          if (delta?.workflow) {
            this.workflowState.set(delta.workflow);
          }

          // Update execution plan
          if (delta?.execution_plan) {
            this.executionPlan.set(delta.execution_plan);
          }

          // Update execution result
          if (delta?.execution_result) {
            this.executionResult.set(delta.execution_result);
          }

          // Update verification
          if (delta?.verification) {
            this.verification.set(delta.verification);
          }

          // Update campaign summary
          if (delta?.campaign_summary) {
            this.campaignSummary.set(delta.campaign_summary);
          }

          this.cdr.detectChanges();
        },
      });
    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      // Associate remaining tool calls with the last message
      const msgs = this.messages();
      if (msgs.length > 0 && this.currentToolCalls.length > 0) {
        const lastAssistantMsg = msgs.filter(m => m.role === 'assistant').pop();
        if (lastAssistantMsg) {
          this.toolCallsMap.set(lastAssistantMsg.id, [...this.currentToolCalls]);
        }
      }
      this.cdr.markForCheck();
    }
  }

  retryMessage(message: Message): void {
    // Find the previous user message and resend
    const msgs = this.messages();
    const idx = msgs.findIndex(m => m.id === message.id);
    if (idx > 0) {
      const prevUserMsg = msgs.slice(0, idx).reverse().find(m => m.role === 'user');
      if (prevUserMsg) {
        this.userInput = this.getMessageContent(prevUserMsg);
        this.sendMessage();
      }
    }
  }

  getMessageContent(message: Message): string {
    const content = message.content;

    // String content
    if (typeof content === 'string') {
      return content;
    }

    // Null or undefined
    if (content == null) {
      return '';
    }

    // AG-UI style content with parts array
    if (typeof content === 'object') {
      const obj = content as Record<string, unknown>;

      // Handle nested content.content structure (some AG-UI formats)
      if (obj['content'] && typeof obj['content'] === 'object') {
        const inner = obj['content'] as Record<string, unknown>;
        if (Array.isArray(inner['parts'])) {
          const parts = inner['parts'] as Array<{ text?: string }>;
          const text = parts.filter(p => p.text).map(p => p.text).join('');
          if (text) return text;
        }
      }

      // Handle { role, parts: [{ text }] } structure
      if (Array.isArray(obj['parts'])) {
        const parts = obj['parts'] as Array<{ text?: string }>;
        const text = parts.filter(p => p.text).map(p => p.text).join('');
        if (text) return text;
      }

      // Handle { text } structure
      if (typeof obj['text'] === 'string') {
        return obj['text'];
      }

      // Handle delta accumulation (AG-UI streaming)
      if (typeof obj['delta'] === 'string') {
        return obj['delta'];
      }
    }

    // Return empty string instead of JSON for non-text messages (tool calls, etc.)
    return '';
  }

  parseContent(content: string | any): ParsedContent {
    if (typeof content !== 'string') {
      return { textBefore: '', textAfter: '' };
    }

    const result: ParsedContent = { textBefore: '', textAfter: '' };

    const planMatch = content.match(/```PLAN\s*([\s\S]*?)```/);
    if (planMatch) {
      try {
        result.plan = JSON.parse(planMatch[1]) as ExecutionPlan;
        result.textBefore = content.substring(0, planMatch.index).trim();
        result.textAfter = content.substring(planMatch.index! + planMatch[0].length).trim();
      } catch (e) {
        result.textBefore = content;
      }
    }

    const resultMatch = content.match(/```RESULT\s*([\s\S]*?)```/);
    if (resultMatch) {
      try {
        result.result = JSON.parse(resultMatch[1]) as ExecutionResult;
        if (!result.textBefore) {
          result.textBefore = content.substring(0, resultMatch.index).trim();
        }
        result.textAfter = content.substring(resultMatch.index! + resultMatch[0].length).trim();
      } catch (e) {
        // Keep original text
      }
    }

    if (!result.textBefore && !result.plan && !result.result) {
      result.textBefore = content;
    }

    return result;
  }

  formatText(text: string): string {
    if (!text) return '';
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  formatSql(sql: string): string {
    if (!sql) return '';

    // SQL keywords to highlight
    const keywords = [
      'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
      'ON', 'AS', 'IN', 'NOT', 'NULL', 'IS', 'LIKE', 'BETWEEN', 'EXISTS',
      'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'OFFSET', 'DISTINCT',
      'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE', 'ALTER', 'DROP',
      'TABLE', 'INDEX', 'VIEW', 'UNION', 'ALL', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
      'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'CAST', 'EXTRACT'
    ];

    let formatted = sql;

    // Escape HTML first
    formatted = formatted
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Highlight string literals (single quotes)
    formatted = formatted.replace(/'([^']*)'/g, '<span class="sql-string">\'$1\'</span>');

    // Highlight keywords (case-insensitive)
    keywords.forEach(keyword => {
      const regex = new RegExp(`\\b(${keyword})\\b`, 'gi');
      formatted = formatted.replace(regex, '<span class="sql-keyword">$1</span>');
    });

    // Highlight table/column names after FROM, JOIN, AS (simplified)
    formatted = formatted.replace(/\b(report\.\w+)\b/gi, '<span class="sql-table">$1</span>');

    // Highlight numbers
    formatted = formatted.replace(/\b(\d+)\b/g, '<span class="sql-number">$1</span>');

    return formatted;
  }

  getResultIcon(status: string): string {
    switch (status) {
      case 'success': return 'pi pi-check-circle';
      case 'error': return 'pi pi-times-circle';
      case 'needs_input': return 'pi pi-question-circle';
      default: return 'pi pi-info-circle';
    }
  }

  getResultTitle(status: string): string {
    switch (status) {
      case 'success': return 'Query Generated';
      case 'error': return 'Error';
      case 'needs_input': return 'Additional Input Needed';
      default: return 'Result';
    }
  }

  copyToClipboard(text: string): void {
    navigator.clipboard.writeText(text);
  }

  onSaveToPlan(parsed: ParsedContent): void {
    const goal = parsed.plan?.goal || '';
    const sql = parsed.result?.sql;
    this.saveToPlan.emit({ goal, sql });
  }

  onSaveToPlanFromBlock(result: ExecutionResult): void {
    const goal = result.explanation || 'Query Result';
    const sql = result.sql;
    this.saveToPlan.emit({ goal, sql });
  }

  // === Tool Call Methods ===

  getToolCallsForMessage(messageId: string): ToolCall[] {
    return this.toolCallsMap.get(messageId) || [];
  }

  getValidToolCalls(messageId: string): ToolCall[] {
    // First, try to get tool calls from the message object directly (CopilotKit embeds them)
    const msgs = this.messages();
    const message = msgs.find(m => m.id === messageId);
    if (message && (message as any).toolCalls) {
      const embeddedToolCalls = (message as any).toolCalls as Array<{
        id: string;
        type: string;
        function: { name: string; arguments: string; };
      }>;

      // Find tool results from "tool" role messages
      const toolResultMessages = msgs.filter(m => (m as any).role === 'tool') as Array<{
        toolCallId: string;
        content: string;
      }>;

      // Transform to our ToolCall format and attach results
      const transformed: ToolCall[] = embeddedToolCalls.map(tc => {
        const resultMsg = toolResultMessages.find(r => r.toolCallId === tc.id);
        let args = {};
        try {
          args = tc.function?.arguments ? JSON.parse(tc.function.arguments) : {};
        } catch {
          args = {};
        }
        return {
          id: tc.id,
          name: tc.function?.name || '',
          args,
          result: resultMsg?.content,
          status: 'completed' as const
        };
      });
      return transformed.filter(tc => tc.name && tc.name.trim() !== '');
    }

    // Fallback to our tracked tool calls
    const toolCalls = this.getToolCallsForMessage(messageId);
    return toolCalls.filter(tc => tc.name && tc.name.trim() !== '');
  }

  // DS-Agent tools (planning phase)
  private dsAgentTools = ['get_label_rules', 'get_ontology', 'get_schema', 'submit_execution_plan', 'list_tables', 'analyze_brand'];
  // DE-Agent tools (execution phase)
  private deAgentTools = ['dry_run_sql', 'run_sql_preview'];

  // Check if this is the last assistant message in the current turn
  isLastAssistantInTurn(messageIndex: number): boolean {
    const msgs = this.filteredMessages();
    const currentMsg = msgs[messageIndex];

    if (currentMsg?.role !== 'assistant') return false;

    // Check if next message is a user message or end of list
    const nextMsg = msgs[messageIndex + 1];
    return !nextMsg || nextMsg.role === 'user';
  }

  // Get planning phase tool calls (DS-Agent)
  getPlanningToolCalls(messageIndex: number): ToolCall[] {
    return this.getToolCallsForTurn(messageIndex).filter(tc =>
      this.dsAgentTools.some(tool => tc.name?.includes(tool))
    );
  }

  // Get execution phase tool calls (DE-Agent)
  getExecutionToolCalls(messageIndex: number): ToolCall[] {
    return this.getToolCallsForTurn(messageIndex).filter(tc =>
      this.deAgentTools.some(tool => tc.name?.includes(tool))
    );
  }

  // Get all tool calls for the current turn (from this assistant message back to the previous user message)
  getToolCallsForTurn(messageIndex: number): ToolCall[] {
    const msgs = this.filteredMessages();
    const allToolCalls: ToolCall[] = [];
    const seenIds = new Set<string>();

    // Go backwards from current message to find all assistant messages in this turn
    for (let i = messageIndex; i >= 0; i--) {
      const msg = msgs[i];
      if (msg.role === 'user') break; // Stop at the previous user message

      if (msg.role === 'assistant') {
        const toolCalls = this.getValidToolCalls(msg.id);
        for (const tc of toolCalls) {
          if (!seenIds.has(tc.id)) {
            seenIds.add(tc.id);
            allToolCalls.unshift(tc); // Add to beginning to maintain order
          }
        }
      }
    }
    return allToolCalls;
  }

  hasToolArgs(toolCall: ToolCall): boolean {
    return toolCall.args && Object.keys(toolCall.args).length > 0;
  }

  toggleToolCall(toolCallId: string): void {
    this.toolCallExpanded[toolCallId] = !this.toolCallExpanded[toolCallId];
  }

  toggleThinkingProcess(messageId: string): void {
    this.thinkingProcessExpanded[messageId] = !this.thinkingProcessExpanded[messageId];
  }

  getThinkingStepText(toolCall: ToolCall): string {
    const name = toolCall.name || '';
    const isCompleted = !!toolCall.result;

    // Special formatting for specific tools (no ✓ in text - green icon handles it)
    if (name.includes('submit_execution_plan')) {
      return isCompleted ? 'Submitted execution plan' : 'Submitting plan...';
    }
    if (name.includes('get_label_rules')) {
      return isCompleted ? 'Retrieved label rules' : 'Getting label rules...';
    }
    if (name.includes('get_ontology')) {
      return isCompleted ? 'Retrieved data model' : 'Getting data model...';
    }
    if (name.includes('get_schema')) {
      return isCompleted ? 'Retrieved schema' : 'Getting schema...';
    }
    if (name.includes('dry_run_sql')) {
      return isCompleted ? 'Validated SQL' : 'Validating SQL...';
    }
    if (name.includes('run_sql_preview')) {
      return isCompleted ? 'Executed query' : 'Executing query...';
    }

    // Default format
    const formattedName = this.formatToolName(name);
    return isCompleted ? `Called ${formattedName}` : `Calling ${formattedName}...`;
  }

  formatToolName(name: string | undefined): string {
    if (!name) return 'Unknown Tool';
    // Convert snake_case to Title Case
    return name
      .replace(/_tool$/, '')
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  getToolArgsPreview(toolCall: ToolCall): string {
    if (!toolCall.args) return '';
    const firstValue = Object.values(toolCall.args)[0];
    if (typeof firstValue === 'string' && firstValue.length > 30) {
      return firstValue.substring(0, 30) + '...';
    }
    return String(firstValue || '');
  }

  formatToolResult(result: string): string {
    try {
      const parsed = JSON.parse(result);
      if (parsed.result && typeof parsed.result === 'string') {
        // Schema result - format nicely
        return parsed.result.replace(/,\s*/g, ',\n');
      }
      return JSON.stringify(parsed, null, 2);
    } catch {
      return result;
    }
  }

  // === Content Visibility ===

  hasVisibleContent(message: Message): boolean {
    // Check for tool calls first - messages with tool calls are always visible
    const toolCalls = this.getValidToolCalls(message.id);
    if (toolCalls.length > 0) {
      return true;
    }

    // Get content as string
    const content = this.getMessageContent(message);
    const trimmed = content.trim();

    // Check for empty content
    if (!trimmed) {
      return false;
    }

    // Check if content blocks has any actual content
    const blocks = this.getContentBlocks(trimmed);
    return blocks.length > 0;
  }

  // === Content Block Methods ===

  getContentBlocks(content: string | any): ContentBlock[] {
    if (typeof content !== 'string') {
      return [{ type: 'text', content: JSON.stringify(content) }];
    }
    return parseMessageContent(content);
  }

  getTruncatedText(text: string, maxLength: number): string {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  }

  cleanIterationText(text: string): string {
    // Remove duplicate emojis and clean up iteration text
    // e.g., "🔄 🔄Iteration 1/3" -> "Iteration 1/3"
    return text.replace(/[🔄⏳⚡✅❌🔙➕]+\s*/g, '').trim() || text;
  }

  getTableColumns(sample: Record<string, unknown>[]): string[] {
    if (!sample || sample.length === 0) return [];
    return Object.keys(sample[0]);
  }

  // === Display Items (Interleaved tool calls and content) ===

  /**
   * Check if this message is the first assistant message in the current turn.
   */
  isFirstAssistantInTurn(message: Message): boolean {
    const msgs = this.filteredMessages();
    const msgIndex = msgs.findIndex(m => m.id === message.id);
    if (msgIndex < 0 || message.role !== 'assistant') return false;
    if (msgIndex === 0) return true;
    return msgs[msgIndex - 1]?.role === 'user';
  }

  /**
   * Get display items for a message with proper interleaving.
   * - Groups consecutive tool calls into ONE "thinking" box
   * - When content appears, closes the thinking box and shows content
   * - If more tool calls appear after content, starts a NEW thinking box
   *
   * For first assistant in turn: processes ALL messages in the turn
   * For other assistants: returns empty (handled by first message)
   */
  getDisplayItems(message: Message): Array<{ type: 'thinking'; toolCalls: ToolCall[] } | { type: 'content'; block: ContentBlock }> {
    // Only process for first assistant message in turn (it handles the entire turn)
    if (!this.isFirstAssistantInTurn(message)) {
      return [];
    }

    const result: Array<{ type: 'thinking'; toolCalls: ToolCall[] } | { type: 'content'; block: ContentBlock }> = [];
    const msgs = this.filteredMessages();
    const msgIndex = msgs.findIndex(m => m.id === message.id);

    // Collect all items from all assistant messages in this turn, in order
    type TurnItem = { type: 'toolCall'; toolCall: ToolCall } | { type: 'content'; block: ContentBlock };
    const turnItems: TurnItem[] = [];

    for (let i = msgIndex; i < msgs.length; i++) {
      const msg = msgs[i];
      if (msg.role === 'user') break; // Stop at next user message

      if (msg.role === 'assistant') {
        // Get tool calls for this message
        const toolCalls = this.getValidToolCalls(msg.id);
        for (const tc of toolCalls) {
          turnItems.push({ type: 'toolCall', toolCall: tc });
        }

        // Get content blocks for this message
        const content = this.getMessageContent(msg);
        const contentBlocks = content ? this.getContentBlocks(content) : [];
        for (const block of contentBlocks) {
          turnItems.push({ type: 'content', block });
        }
      }
    }

    // Deduplicate tool calls by name, keeping the completed version (with result)
    const toolCallsByName = new Map<string, ToolCall>();

    for (const item of turnItems) {
      if (item.type === 'toolCall') {
        const name = item.toolCall.name || item.toolCall.id;
        const existing = toolCallsByName.get(name);

        if (!existing || (item.toolCall.result && !existing.result)) {
          // Add new or replace with completed version
          toolCallsByName.set(name, item.toolCall);
        }
      }
    }

    // Now merge consecutive tool calls into thinking boxes
    let currentToolCalls: ToolCall[] = [];
    const seenToolNames = new Set<string>();

    for (const item of turnItems) {
      if (item.type === 'toolCall') {
        const name = item.toolCall.name || item.toolCall.id;
        // Only emit each tool call once (use the best version from map)
        if (!seenToolNames.has(name)) {
          seenToolNames.add(name);
          currentToolCalls.push(toolCallsByName.get(name)!);
        }
      } else {
        // Content block - close current thinking group if any
        if (currentToolCalls.length > 0) {
          result.push({ type: 'thinking', toolCalls: [...currentToolCalls] });
          currentToolCalls = [];
        }
        // Add content block
        result.push({ type: 'content', block: item.block });
      }
    }

    // Don't forget remaining tool calls at the end
    if (currentToolCalls.length > 0) {
      result.push({ type: 'thinking', toolCalls: currentToolCalls });
    }

    return result;
  }
}
