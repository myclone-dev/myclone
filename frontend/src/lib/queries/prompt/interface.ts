/**
 * Persona prompt configuration and suggested questions types
 */

export interface UpdatePromptFieldRequest {
  persona_id: string;
  field: string;
  value: string | object;
}

export interface UpdatePromptFieldResponse {
  status: "success";
  action: "field_updated";
  persona_id: string;
  field: string;
  value: string | object;
  archived_version: number;
  message: string;
}

export interface GenerateSuggestedQuestionsRequest {
  persona_id: string;
  num_questions?: number; // 1-10, default 5
  force_regenerate?: boolean; // default false
}

export interface GenerateSuggestedQuestionsResponse {
  status: "success";
  persona_id: string;
  suggested_questions: string[];
  generated_at: string;
  response_settings: {
    response_length: string;
    creativity: string;
  };
  from_cache: boolean;
  message: string;
}

export interface GetSuggestedQuestionsResponse {
  status: string;
  persona_id: string;
  suggested_questions: string[];
  generated_at: string;
  response_settings: Record<string, unknown>;
  from_cache: boolean;
  message: string;
}

export interface ResponseStructure {
  response_length: "intelligent" | "concise" | "explanatory" | "custom";
  creativity: "strict" | "adaptive" | "creative";
}

export interface PersonaPromptFields {
  // Basic fields (always shown)
  introduction?: string; // Prefilled from LinkedIn
  area_of_expertise?: string; // Prefilled from LinkedIn
  chat_objective?: string;
  target_audience?: string;
  response_structure?: ResponseStructure;

  // Advanced fields (shown when is_dynamic = true)
  is_dynamic?: boolean; // Toggle for advanced mode
  thinking_style?: string;
  objective_response?: string;
  example_responses?: string;
  example_prompt?: string;
  conversation_flow?: string;
  strict_guideline?: string; // Guardrails for conversation boundaries
}

export interface PersonaPrefillResponse {
  introduction: string;
  area_of_expertise: string;
}
