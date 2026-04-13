/**
 * Workflow TypeScript Interfaces
 * Based on API spec for /api/v1/workflows
 */

// ============================================================================
// WORKFLOW CONFIGURATION TYPES
// ============================================================================

export type WorkflowType = "simple" | "scored" | "conversational";

export type StepType =
  | "text_input"
  | "text_area"
  | "number_input"
  | "multiple_choice"
  | "yes_no";

export interface WorkflowOption {
  label: string;
  text: string;
  score: number | null;
}

export interface WorkflowValidation {
  min_length?: number;
  max_length?: number;
  min?: number;
  max?: number;
}

export interface WorkflowStep {
  step_id: string;
  step_type: StepType;
  question_text: string;
  required: boolean;
  options?: WorkflowOption[] | null;
  validation?: WorkflowValidation | null;
}

export interface WorkflowConfig {
  steps: WorkflowStep[];
}

export interface ResultCategory {
  name: string;
  min_score: number;
  max_score: number;
  message: string;
}

export interface ResultConfig {
  scoring_type: "sum";
  categories: ResultCategory[];
}

export type PromotionMode = "proactive" | "contextual" | "reactive";

export interface TriggerConfig {
  promotion_mode: PromotionMode;
  max_attempts: number; // 1-10, default: 3
  cooldown_turns: number; // 1-20, default: 5
}

// ============================================================================
// API REQUEST/RESPONSE TYPES
// ============================================================================

export interface CreateWorkflowRequest {
  workflow_type: WorkflowType;
  title: string;
  description?: string | null;
  opening_message?: string | null;
  workflow_objective?: string | null;
  workflow_config: WorkflowConfig;
  result_config?: ResultConfig | null;
  trigger_config?: TriggerConfig | null;
}

export interface UpdateWorkflowRequest {
  title?: string;
  description?: string;
  workflow_objective?: string;
  workflow_config?: WorkflowConfig;
  result_config?: ResultConfig;
  trigger_config?: TriggerConfig | null;
  is_active?: boolean;
}

export interface Workflow {
  id: string;
  persona_id: string;
  workflow_type: WorkflowType;
  title: string;
  description: string | null;
  opening_message: string | null;
  workflow_objective: string | null;
  workflow_config: WorkflowConfig; // Keep as WorkflowConfig for backward compatibility
  result_config: ResultConfig | null;
  output_template: OutputTemplate | null;
  is_active: boolean;
  version: number;
  published_at: string | null;
  trigger_config: TriggerConfig | null;
  extra_metadata: Record<string, unknown> | null;
  // Template tracking fields
  template_id: string | null;
  is_template_customized: boolean;
  template_version: number | null;
  created_at: string;
  updated_at: string;
  // Analytics data (included in list endpoint)
  total_sessions?: number;
  completed_sessions?: number;
  completion_rate?: number;
  avg_score?: number;
}

export interface WorkflowsListResponse {
  workflows: Workflow[];
  total: number;
}

// ============================================================================
// SESSION TYPES
// ============================================================================

export type SessionStatus = "in_progress" | "completed" | "abandoned";

/**
 * Result data for simple/scored workflows (linear step-based)
 */
export interface SessionResultData {
  total_score: number;
  max_possible_score: number;
  percentage: number;
  category: string;
  category_message: string;
}

/**
 * Lead evaluation result for conversational workflows
 * Contains scoring, contact info, and AI-generated insights
 */
export interface LeadEvaluationResult {
  // Core scores
  lead_score: number; // 0-100
  priority_level: "high" | "medium" | "low";
  lead_quality: "hot" | "warm" | "cold";
  urgency_level: "high" | "medium" | "low";

  // Structured summary (for display)
  lead_summary: {
    contact: {
      name: string;
      email: string | null;
      phone: string | null;
    };
    service_need: string; // What they're looking for
    additional_info: Record<string, string>; // Extra fields like state, timeline
    follow_up_questions: string[]; // Suggested questions for sales team
  };

  // Scoring breakdown (for detailed view)
  scoring: {
    score: number; // Same as lead_score
    priority: string; // Same as priority_level
    signals_matched: Array<{
      signal_id: string; // e.g., "urgent_timeline"
      points: number; // e.g., 10
      reason: string; // e.g., "The lead has an immediate timeline"
    }>;
    penalties_applied: Array<{
      penalty_id: string;
      points: number; // Negative number
      reason: string;
    }>;
    reasoning: string; // LLM's overall explanation
  };

  // Metadata
  confidence: number; // 0.0-1.0
  evaluated_at: string; // ISO timestamp
}

/**
 * Extracted field from conversational workflow
 */
export interface ExtractedField {
  value: string;
  confidence: number; // 0.0-1.0
}

export interface WorkflowSession {
  id: string;
  workflow_id: string;
  persona_id: string;
  conversation_id: string | null;
  user_id: string | null;
  status: SessionStatus;
  current_step_id: string | null;
  progress_percentage: number;
  collected_data: Record<string, unknown>; // Raw step answers (for linear workflows)
  result_data: SessionResultData | LeadEvaluationResult | null; // SessionResultData for linear, LeadEvaluationResult for conversational
  extracted_fields: Record<string, ExtractedField> | null; // Raw extracted fields (conversational only)
  session_metadata: Record<string, unknown> | null;
  started_at: string;
  completed_at: string | null;
  updated_at: string;
}

/**
 * Type guard to check if result_data is LeadEvaluationResult
 */
export function isLeadEvaluationResult(
  result: SessionResultData | LeadEvaluationResult | null,
): result is LeadEvaluationResult {
  return result !== null && "lead_score" in result && "lead_summary" in result;
}

/**
 * Type guard to check if result_data is SessionResultData (linear workflow)
 */
export function isSessionResultData(
  result: SessionResultData | LeadEvaluationResult | null,
): result is SessionResultData {
  return result !== null && "total_score" in result && "category" in result;
}

export interface CreateSessionRequest {
  workflow_id: string;
  conversation_id?: string | null;
  user_id?: string | null;
  session_metadata?: Record<string, unknown> | null;
}

export interface SubmitAnswerRequest {
  step_id: string;
  answer: unknown;
  raw_answer?: string | null;
}

export interface SessionsListResponse {
  sessions: WorkflowSession[];
  total: number;
}

// ============================================================================
// ANALYTICS TYPES
// ============================================================================

export interface WorkflowAnalytics {
  workflow_id: string;
  total_sessions: number;
  completed_sessions: number;
  abandoned_sessions: number;
  in_progress_sessions: number;
  completion_rate: number;
  avg_completion_time_seconds: number | null;
  avg_score: number | null;
  score_distribution: Record<string, number> | null;
  drop_off_by_step: Record<string, number> | null;
}

// ============================================================================
// UI HELPER TYPES
// ============================================================================

export interface WorkflowWithPersona extends Workflow {
  persona_name?: string;
  persona_display_name?: string;
}

export interface QuestionFormData {
  question_text: string;
  step_type: StepType;
  required: boolean;
  options: WorkflowOption[];
}

// ============================================================================
// WORKFLOW TEMPLATES (CONVERSATIONAL WORKFLOWS)
// ============================================================================

/**
 * Plan tier levels for template access control
 * @deprecated Backend now uses tier IDs (0-6) instead of string names.
 * Keep for backward compatibility documentation only.
 */
export type PlanTier = "free" | "professional" | "business" | "enterprise";

/**
 * Template category (industry-specific)
 */
export type TemplateCategory = "cpa" | "tax" | "insurance";

/**
 * Field type for conversational workflow configuration
 */
export type ConversationalFieldType =
  | "text"
  | "email"
  | "phone"
  | "choice"
  | "number"
  | "date";

/**
 * Individual field configuration in conversational workflow
 */
export interface ConversationalField {
  field_id: string;
  field_type: ConversationalFieldType;
  label: string;
  description?: string;
  clarifying_question?: string;
  options?: string[];
}

/**
 * Extraction strategy for conversational workflows
 */
export interface ExtractionStrategy {
  opening_question?: string;
  max_clarifying_questions?: number;
  confirmation_required?: boolean;
  confidence_threshold?: number;
}

/**
 * Scoring rule signal
 */
export interface ScoringSignal {
  signal_id: string;
  points: number;
  condition: {
    field: string;
    operator: string;
    value: string | number | boolean;
  };
}

/**
 * Risk penalty configuration
 */
export interface RiskPenalty {
  penalty_id: string;
  points: number;
  condition: {
    any_of?: Array<{
      field: string;
      operator: string;
      value?: string | number | boolean;
    }>;
  };
}

/**
 * Scoring rules for output template
 */
export interface ScoringRules {
  base_score?: number;
  field_completeness_weight?: number;
  quality_signals?: ScoringSignal[];
  risk_penalties?: RiskPenalty[];
}

/**
 * Conversational workflow configuration
 * (extends WorkflowConfig for conversational type)
 */
export interface ConversationalWorkflowConfig {
  required_fields?: ConversationalField[];
  optional_fields?: ConversationalField[];
  extraction_strategy?: ExtractionStrategy;
  [key: string]: unknown;
}

/**
 * Output template configuration
 */
export interface OutputTemplate {
  format?: string;
  sections?: string[];
  scoring_rules?: ScoringRules;
  [key: string]: unknown;
}

/**
 * Workflow Template (read-only, managed by admins)
 */
export interface WorkflowTemplate {
  id: string;
  template_key: string;
  template_name: string;
  template_category: TemplateCategory;
  /** Minimum tier ID required to access this template (0=Free, 1=Pro, 2=Business, 3=Enterprise) */
  minimum_plan_tier_id: number;
  workflow_type: WorkflowType;
  workflow_config: WorkflowConfig | ConversationalWorkflowConfig;
  output_template: OutputTemplate;
  description: string | null;
  preview_image_url: string | null;
  tags: string[] | null;
  version: number;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  // Optional fields (only with include_stats=true)
  usage_count?: number;
  customization_rate?: number;
}

/**
 * Query parameters for listing templates
 */
export interface TemplateListParams {
  category?: TemplateCategory;
  include_stats?: boolean;
  limit?: number;
  offset?: number;
}

/**
 * Response from template list endpoint
 */
export interface TemplateListResponse {
  templates: WorkflowTemplate[];
  total: number;
}

/**
 * Request body for enabling a template
 */
export interface EnableTemplateRequest {
  template_id: string;
  auto_publish?: boolean;
}

/**
 * Query parameters for enable template endpoint
 */
export interface EnableTemplateParams {
  persona_id: string;
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Get smart defaults for trigger_config based on workflow type
 * Used when trigger_config is null/undefined (old workflows or when not provided)
 */
export function getDefaultTriggerConfig(
  workflowType: WorkflowType,
): TriggerConfig {
  return {
    promotion_mode: workflowType === "scored" ? "proactive" : "contextual",
    max_attempts: 3,
    cooldown_turns: 5,
  };
}
