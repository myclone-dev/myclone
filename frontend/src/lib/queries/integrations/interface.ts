/**
 * Integration-related type definitions
 */

export type IntegrationType =
  | "stripe"
  | "zapier"
  | "gohighlevel"
  | "canopy"
  | "taxdome"
  | "karbon"
  | "twilio";

export type IntegrationStatus = "connected" | "disconnected" | "pending";

export interface Integration {
  id: string;
  type: IntegrationType;
  name: string;
  description: string;
  icon: string;
  status: IntegrationStatus;
  connected_at?: string;
  last_synced_at?: string;
  config?: Record<string, unknown>;
}

export interface IntegrationListResponse {
  integrations: Integration[];
  total: number;
}

export interface ConnectIntegrationRequest {
  type: IntegrationType;
  config?: Record<string, unknown>;
}

export interface DisconnectIntegrationRequest {
  id: string;
}

export interface IntegrationConfig {
  type: IntegrationType;
  name: string;
  description: string;
  icon: string;
  features: string[];
  requiresBusinessPlan?: boolean; // Requires Business plan or higher
  requiresEnterprisePlan?: boolean; // Requires Enterprise plan
  comingSoon?: boolean;
  color?: string;
  iconColor?: string;
}
