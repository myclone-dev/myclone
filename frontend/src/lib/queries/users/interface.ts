/**
 * User-related type definitions
 */

export interface PublicUserDetails {
  id: string;
  username: string;
  fullname: string;
  avatar?: string;
  linkedin_url?: string;
  location?: string;
  created_at: string;
  // Optional fields that may exist from LinkedIn enrichment
  company_role?: string;
}

export interface UserProfile {
  id: string;
  email: string;
  username: string;
  fullname: string;
  firstname?: string;
  lastname?: string;
  avatar?: string;
  linkedin_id?: string;
  linkedin_url?: string;
  location?: string;
  company?: string;
  role?: string;
  email_confirmed: boolean;
  onboarding_status: string;
  account_type: string;
  language?: string; // UI language preference (en, es, fr, ar)
  created_at: string;
  updated_at: string;
}

export interface UpdateProfileRequest {
  fullname?: string;
  phone?: string;
  company?: string;
  role?: string;
  language?: string; // UI language preference (en, es, fr, ar)
}

export interface WidgetTokenResponse {
  id: string;
  token: string;
  name: string;
  description: string | null;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

export interface CreateWidgetTokenRequest {
  name: string;
  description?: string;
}

export interface WidgetTokenListResponse {
  tokens: WidgetTokenResponse[];
  total: number;
}

export interface UsernameAvailabilityResponse {
  username: string;
  available: boolean;
  reason: string | null;
}

// Custom Domain Types (USER-LEVEL)
// Custom domains route to: domain.com → /{username}, domain.com/persona → /{username}/{persona}

export interface DNSRecord {
  type: string;
  name: string;
  value: string;
  description?: string;
}

export interface CustomDomainResponse {
  id: string;
  domain: string;
  status:
    | "pending"
    | "verifying"
    | "verified"
    | "active"
    | "failed"
    | "expired";
  user_id: string;
  username: string | null;
  verified: boolean;
  ssl_ready: boolean;
  verification_record: DNSRecord | null;
  routing_record: DNSRecord | null;
  // Optional extra routing records (e.g., AAAA for apex domains)
  additional_routing_records?: DNSRecord[] | null;
  last_error: string | null;
  created_at: string;
  verified_at: string | null;
}

export interface CustomDomainListResponse {
  domains: CustomDomainResponse[];
  total: number;
}

export interface AddCustomDomainRequest {
  domain: string;
}

export interface AddCustomDomainResponse {
  success: boolean;
  domain: CustomDomainResponse;
  message: string;
  dns_instructions: string;
}

export interface VerifyDomainResponse {
  success: boolean;
  verified: boolean;
  domain: CustomDomainResponse;
  message: string;
}

// Widget Configuration Types

/**
 * Widget configuration object - matches the frontend WidgetConfig type
 * Stored as JSONB in the backend
 */
export interface WidgetConfigData {
  // Essentials
  personaName?: string;
  widgetToken?: string;
  // Size & Dimensions
  width?: string;
  height?: string;
  bubbleSize?: string;
  borderRadius?: string;
  chatbotWidth?: string;
  chatbotHeight?: string;
  // Theme & Colors
  primaryColor?: string;
  backgroundColor?: string;
  headerBackground?: string;
  textColor?: string;
  textSecondaryColor?: string;
  bubbleBackgroundColor?: string;
  bubbleTextColor?: string;
  userMessageBg?: string;
  botMessageBg?: string;
  userMessageTextColor?: string;
  botMessageTextColor?: string;
  // Layout & Positioning
  position?: string;
  offsetX?: string;
  offsetY?: string;
  modalPosition?: string;
  chatbotStyle?: "guide" | "classic";
  // Branding
  showBranding?: boolean;
  headerTitle?: string;
  headerSubtitle?: string;
  avatarUrl?: string;
  showAvatar?: boolean;
  bubbleIcon?: string;
  simpleBubble?: boolean;
  // Behavior
  enableVoice?: boolean;
  bubbleText?: string;
  welcomeMessage?: string;
  // Allow additional properties for forward compatibility
  [key: string]: unknown;
}

export interface WidgetConfigResponse {
  config: WidgetConfigData | null;
  updated_at: string | null;
}

export interface UpdateWidgetConfigRequest {
  config: WidgetConfigData;
}

// ============================================================================
// Custom Email Domain Types (Whitelabel Email Sending)
// ============================================================================

/**
 * DNS record for email domain verification (SPF, DKIM, etc.)
 */
export interface EmailDNSRecord {
  record?: string;
  name: string;
  type: string;
  value: string;
  status: "pending" | "verified" | "failed";
  ttl?: string;
  priority?: number;
}

/**
 * Custom email domain for whitelabel email sending
 */
export interface CustomEmailDomain {
  id: string;
  domain: string;
  from_email: string;
  from_name: string | null;
  reply_to_email: string | null;
  status: "pending" | "verifying" | "verified" | "failed";
  dns_records: EmailDNSRecord[] | null;
  created_at: string;
  verified_at: string | null;
}

/**
 * Response for listing email domains
 */
export interface CustomEmailDomainListResponse {
  domains: CustomEmailDomain[];
  total: number;
}

/**
 * Request to create a new custom email domain
 */
export interface CreateEmailDomainRequest {
  domain: string;
  from_email: string;
  from_name?: string;
  reply_to_email?: string;
}

/**
 * Request to update an existing email domain
 */
export interface UpdateEmailDomainRequest {
  from_name?: string;
  reply_to_email?: string;
}
