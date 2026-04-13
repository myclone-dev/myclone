// ============================================================================
// Webhook Configuration Types
// ============================================================================

/**
 * Supported webhook events
 */
export type WebhookEvent = "conversation.finished";

/**
 * Supported webhook providers
 */
export type WebhookProvider =
  | "zapier"
  | "make"
  | "n8n"
  | "slack"
  | "discord"
  | "custom";

/**
 * Webhook configuration response (account-level)
 */
export interface WebhookConfigResponse {
  enabled: boolean;
  url: string | null;
  events: WebhookEvent[];
  has_secret: boolean;
  personas_count: number;
}

/**
 * Create/Update webhook request
 */
export interface CreateWebhookRequest {
  url: string; // Must be HTTPS
  events?: WebhookEvent[];
  secret?: string; // Max 255 chars
}

/**
 * Partial update webhook request
 */
export interface UpdateWebhookRequest {
  url?: string; // Must be HTTPS
  events?: WebhookEvent[];
  secret?: string; // Max 255 chars
  enabled?: boolean;
}

/**
 * Webhook health check response
 */
export interface WebhookHealthResponse {
  status: "healthy" | "unhealthy";
  message: string;
  supported_providers: WebhookProvider[];
  supported_events: WebhookEvent[];
}

/**
 * Webhook payload sent to external URL (for reference)
 */
export interface WebhookPayload {
  event: WebhookEvent;
  timestamp: string; // ISO 8601
  persona: {
    id: string;
    name: string;
    persona_name: string;
  };
  data: {
    conversation_id: string;
    duration_seconds: number;
    transcript: string;
    summary: string;
  };
}
