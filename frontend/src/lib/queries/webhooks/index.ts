// Webhook Configuration Queries & Mutations
// Centralized exports for webhook management

// Types
export type {
  WebhookEvent,
  WebhookProvider,
  WebhookConfigResponse,
  CreateWebhookRequest,
  UpdateWebhookRequest,
  WebhookHealthResponse,
  WebhookPayload,
} from "./interface";

// Hooks
export { useGetWebhook, getWebhookQueryKey } from "./useGetWebhook";
export { useCreateWebhook } from "./useCreateWebhook";
export { useUpdateWebhook } from "./useUpdateWebhook";
export { useDeleteWebhook } from "./useDeleteWebhook";
export { useWebhookHealth, getWebhookHealthQueryKey } from "./useWebhookHealth";
