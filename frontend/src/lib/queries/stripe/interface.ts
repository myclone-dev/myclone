/**
 * Stripe Payment Integration Type Definitions
 * Feature 2: Persona Monetization
 */

// ============================================================================
// Pricing Models
// ============================================================================

export type PricingModel =
  | "free"
  | "one_time_lifetime"
  | "one_time_duration"
  | "subscription_monthly"
  | "subscription_yearly";

export type Currency = "usd"; // Phase 1 only supports USD

// ============================================================================
// Persona Monetization Types
// ============================================================================

export interface PersonaMonetizationResponse {
  id: string;
  persona_id: string;
  pricing_model: PricingModel;
  price_cents: number;
  currency: Currency;
  access_duration_days: number | null;
  stripe_product_id: string;
  stripe_price_id: string;
  stripe_account_id?: string | null; // Stripe Connect account ID (null if not connected)
  trial_enabled: boolean;
  trial_duration_days: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EnableMonetizationRequest {
  pricing_model: PricingModel;
  price_cents: number;
  currency?: Currency;
  access_duration_days?: number | null;
  trial_enabled?: boolean;
  trial_duration_days?: number | null;
}

export interface UpdateMonetizationRequest {
  pricing_model?: PricingModel;
  price_cents?: number;
  access_duration_days?: number | null;
  is_active?: boolean;
}

export interface DisableMonetizationResponse {
  success: boolean;
  message: string;
  persona_id: string;
  note: string;
}

// ============================================================================
// Persona Access Types
// ============================================================================

export type AccessType = "owner" | "free" | "purchased" | null;

export interface PersonaAccessResponse {
  has_access: boolean;
  access_type: AccessType;
  expires_at: string | null;
  purchase_id: string | null;
}

export interface CreatePersonaCheckoutRequest {
  persona_id: string;
  success_url?: string;
  cancel_url?: string;
}

export interface CreatePersonaCheckoutResponse {
  checkout_url: string;
  session_id: string;
}

// ============================================================================
// Platform Subscription Types (for future use)
// ============================================================================

export interface CreatePlatformSubscriptionRequest {
  tier_id: number;
  success_url?: string;
  cancel_url?: string;
}

export interface CreatePlatformSubscriptionResponse {
  checkout_url: string;
  session_id: string;
}

// ============================================================================
// Helper Types
// ============================================================================

export interface PricingDisplay {
  isFree: boolean;
  priceDisplay?: string;
  model?: PricingModel;
  duration?: number;
}

// Price formatting helpers
export const formatPrice = (
  cents: number,
  currency: Currency = "usd",
): string => {
  const dollars = cents / 100;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(dollars);
};

export const formatPricingModel = (model: PricingModel): string => {
  switch (model) {
    case "free":
      return "Free";
    case "one_time_lifetime":
      return "One-time (Lifetime)";
    case "one_time_duration":
      return "One-time (Limited Duration)";
    case "subscription_monthly":
      return "Monthly Subscription";
    case "subscription_yearly":
      return "Yearly Subscription";
  }
};

// ============================================================================
// Stripe Connect Types (Feature 2b: Creator Payouts)
// ============================================================================

/**
 * Response from Stripe Connect onboarding initiation
 */
export interface StripeConnectOnboardResponse {
  onboarding_url: string; // Stripe-hosted onboarding URL
  account_id: string; // Stripe Connect account ID
}

/**
 * Response from Stripe Connect dashboard link generation
 */
export interface StripeConnectDashboardResponse {
  dashboard_url: string; // Stripe Express Dashboard URL (short-lived)
}
