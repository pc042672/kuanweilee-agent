/**
 * Chat Models - TypeScript interfaces matching backend API spec
 * See: backend/api_spec.md for schema definitions
 */

// === AG-UI Event Types ===

export type AGUIEventType =
  | 'RUN_STARTED'
  | 'RUN_FINISHED'
  | 'TEXT_MESSAGE_START'
  | 'TEXT_MESSAGE_CONTENT'
  | 'TEXT_MESSAGE_END'
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_ARGS'
  | 'TOOL_CALL_END'
  | 'TOOL_CALL_RESULT'
  | 'STATE_DELTA'
  | 'STATE_SNAPSHOT';

// === Workflow State Types (for STATE_DELTA events) ===

export type WorkflowPhase = 'planning' | 'executing' | 'verifying' | 'complete' | 'error' | 'waiting';

export interface WorkflowState {
  phase: WorkflowPhase;
  iteration: number;
  max_iterations: number;
  message?: string;
  error?: string;
}

export interface AgentState {
  workflow?: WorkflowState;
  execution_plan?: ExecutionPlan;
  execution_result?: ExecutionResult;
  verification?: Verification;
}

export interface StateDeltaEvent {
  type: 'STATE_DELTA';
  delta: AgentState[];
}

export interface AGUIEvent {
  type: AGUIEventType;
  threadId?: string;
  runId?: string;
  messageId?: string;
  toolCallId?: string;
  toolCallName?: string;
  role?: 'user' | 'assistant';
  delta?: string;
  content?: string;
  snapshot?: Record<string, unknown>;
}

// === Tool Call Types ===

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: 'pending' | 'running' | 'completed' | 'error';
}

// === Message Content Types ===

export type ContentBlockType =
  | 'iteration'           // "🔄 Iteration 1/3"
  | 'thinking'            // Agent thinking/reasoning
  | 'tool_call'           // Tool invocation
  | 'tool_result'         // Tool response
  | 'plan'                // Execution plan JSON
  | 'sql_result'          // SQL execution result JSON
  | 'sql_code'            // SQL code block
  | 'verification'        // Verification result JSON
  | 'campaign_summary'    // Campaign summary from Verifier
  | 'table_data'          // Preview table data
  | 'completion'          // "✅ Task completed!"
  | 'text'                // Plain text
  | 'error';              // Error message

export interface ContentBlock {
  type: ContentBlockType;
  content: string;
  data?: ExecutionPlan | ExecutionResult | Verification | CampaignSummary | ToolCall | PreviewResult;
}

// === Enhanced Message ===

export interface EnhancedMessage {
  id: string;
  role: 'user' | 'assistant';
  blocks: ContentBlock[];
  toolCalls?: ToolCall[];
  timestamp?: Date;
}

// === Execution Plan (DS-Agent output) ===

export interface ExecutionPlan {
  goal: string;
  label_matched: string | null;
  analysis: string;
  tables_needed: TableInfo[];
  joins: JoinInfo[];
  filters: FilterInfo[];
  aggregations: AggregationInfo[];
  execution_method: 'sql' | 'embedding' | 'llm';
}

export interface TableInfo {
  name: string;
  columns: string[];
  role: string;
}

export interface JoinInfo {
  from: string;
  to: string;
  type: 'INNER JOIN' | 'LEFT JOIN' | 'RIGHT JOIN' | 'FULL JOIN';
  on: string;
}

export interface FilterInfo {
  column: string;
  operator: '=' | '!=' | '>' | '<' | '>=' | '<=' | 'IN' | 'LIKE';
  value: string;
}

export interface AggregationInfo {
  function: 'COUNT' | 'SUM' | 'AVG' | 'MIN' | 'MAX';
  column: string;
  alias?: string;
}

// === Execution Result (DE-Agent output) ===

export interface ExecutionResult {
  status: 'success' | 'error' | 'needs_refinement' | 'needs_input';
  sql?: string;
  validation?: ValidationResult;
  preview?: PreviewResult;
  explanation?: string;
  // Frontend-only fields (preserved for compatibility)
  question?: string;
  options?: string[];
  missing_data?: string;
  message?: string;
}

export interface ValidationResult {
  dry_run: 'passed' | 'failed';
  error?: string;
}

export interface PreviewResult {
  row_count: number;
  sample: Record<string, unknown>[];
}

// === Verification (Verifier output) ===

export interface Verification {
  sufficient: boolean;
  feedback?: string;
  action: 'complete' | 'add_step' | 'backtrack';
}

// === Campaign Summary (Verifier output) ===

export interface CampaignSummary {
  campaign_title: string;
  target_audience?: {
    segment_name?: string;
    count?: number;
    description?: string;
  };
  audience_insights?: AudienceInsight[];
  marketing_recommendations?: MarketingRecommendation[];
  activation_suggestions?: ActivationSuggestions;
  next_steps?: string[];
}

export interface AudienceInsight {
  insight_type: 'value' | 'behavior' | 'preference' | string;
  description: string;
  data_point?: string;
}

export interface MarketingRecommendation {
  strategy: string;
  description: string;
  tactics?: string[];
  expected_outcome?: string;
}

export interface ActivationSuggestions {
  primary_channel?: string;
  best_timing?: string;
  subject_lines?: string[];
  cta_text?: string;
  tone?: string;
}

// === Parsed Content ===

export interface ParsedContent {
  textBefore: string;
  plan?: ExecutionPlan;
  result?: ExecutionResult;
  verification?: Verification;
  textAfter: string;
  blocks?: ContentBlock[];
}

// === Content Detection Helpers ===

export function detectJsonType(obj: Record<string, unknown>): ContentBlockType {
  // Campaign Summary: has campaign_title and target_audience
  if ('campaign_title' in obj && 'target_audience' in obj) {
    return 'campaign_summary';
  }
  // Execution Plan: has goal, segment_type, tables_needed
  if ('goal' in obj && 'tables_needed' in obj) {
    return 'plan';
  }
  // Execution Result: has status, sql, validation
  if ('status' in obj && ('sql' in obj || 'validation' in obj || 'preview' in obj)) {
    return 'sql_result';
  }
  // Verification: has sufficient, action
  if ('sufficient' in obj && 'action' in obj) {
    return 'verification';
  }
  return 'text';
}

export function parseMessageContent(content: string): ContentBlock[] {
  const blocks: ContentBlock[] = [];

  if (!content || typeof content !== 'string') {
    return blocks;
  }

  // Split content by code blocks (json or sql)
  const parts = content.split(/(```(?:json|sql)[\s\S]*?```)/g);

  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    // Check for JSON code block
    const jsonMatch = trimmed.match(/```json\s*([\s\S]*?)```/);
    if (jsonMatch) {
      try {
        const jsonData = JSON.parse(jsonMatch[1]);
        const blockType = detectJsonType(jsonData);
        blocks.push({
          type: blockType,
          content: jsonMatch[1],
          data: jsonData
        });
      } catch {
        // Failed to parse JSON, treat as text
        blocks.push({ type: 'text', content: trimmed });
      }
      continue;
    }

    // Check for SQL code block
    const sqlMatch = trimmed.match(/```sql\s*([\s\S]*?)```/);
    if (sqlMatch) {
      blocks.push({
        type: 'sql_code',
        content: sqlMatch[1].trim()
      });
      continue;
    }

    // Check for CAMPAIGN_SUMMARY section (raw text with JSON)
    const campaignMatch = trimmed.match(/(?:📊\s*)?CAMPAIGN_SUMMARY:?\s*([\s\S]*)/i);
    if (campaignMatch) {
      try {
        const jsonStr = campaignMatch[1].trim();
        const campaignData = JSON.parse(jsonStr);
        if (campaignData.campaign_title) {
          blocks.push({ type: 'campaign_summary', content: jsonStr, data: campaignData });
          continue;
        }
      } catch {
        // Not valid JSON, fall through to other checks
      }
    }

    // Check for iteration indicator
    if (trimmed.match(/^🔄\s*Iteration/)) {
      blocks.push({ type: 'iteration', content: trimmed });
      continue;
    }

    // Check for completion message
    if (trimmed.match(/^✅/)) {
      blocks.push({ type: 'completion', content: trimmed });
      continue;
    }

    // Check for thinking/reasoning
    if (trimmed.match(/^(Analyzing|Processing|Looking|Checking|Searching|I will|Let me)/i)) {
      blocks.push({ type: 'thinking', content: trimmed });
      continue;
    }

    // Default to text
    blocks.push({ type: 'text', content: trimmed });
  }

  return blocks;
}
