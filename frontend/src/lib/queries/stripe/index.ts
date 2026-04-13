/**
 * Stripe Payment Integration
 * Feature 2: Persona Monetization
 *
 * Export all Stripe-related hooks and types
 */

// Types and Interfaces
export type {
  PricingModel,
  Currency,
  PersonaMonetizationResponse,
  EnableMonetizationRequest,
  UpdateMonetizationRequest,
  DisableMonetizationResponse,
  AccessType,
  PersonaAccessResponse,
  CreatePersonaCheckoutRequest,
  CreatePersonaCheckoutResponse,
  PricingDisplay,
  CreatePlatformSubscriptionRequest,
  CreatePlatformSubscriptionResponse,
  StripeConnectOnboardResponse,
  StripeConnectDashboardResponse,
} from "./interface";

// Helper Functions
export { formatPrice, formatPricingModel } from "./interface";

// Monetization Management Hooks
export {
  useGetPersonaMonetization,
  usePersonaPricingDisplay,
  getPersonaMonetizationQueryKey,
} from "./useGetPersonaMonetization";

export { useEnableMonetization } from "./useEnableMonetization";
export { useUpdateMonetization } from "./useUpdateMonetization";
export { useToggleMonetizationStatus } from "./useToggleMonetizationStatus";
export { useDisableMonetization } from "./useDisableMonetization";

// Persona Access Hooks
export { usePersonaAccessCheckout } from "./usePersonaAccessCheckout";

export {
  useCheckPersonaAccess,
  usePersonaAccessPolling,
  getPersonaAccessQueryKey,
} from "./useCheckPersonaAccess";

// Stripe Connect Hooks
export { useStripeConnectOnboard } from "./useStripeConnectOnboard";
export { useStripeConnectDashboard } from "./useStripeConnectDashboard";
