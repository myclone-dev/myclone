/**
 * Constants for PersonaSettings Dialog
 */

// Email capture
export const MIN_EMAIL_THRESHOLD = 1;
export const MAX_EMAIL_THRESHOLD = 100;
export const DEFAULT_EMAIL_THRESHOLD = 5;

// Pricing
export const MIN_PRICE_CENTS = 99; // $0.99
export const MAX_PRICE_CENTS = 999999; // $9,999.99
export const DEFAULT_PRICE_CENTS = 999; // $9.99

// Calendar
export const MAX_CALENDAR_URL_LENGTH = 500;

// Form defaults
export const DEFAULT_GREETING = "Hi! How can I help you today?";
export const DEFAULT_EMAIL_CAPTURE_REQUIRE_FULLNAME = true;
export const DEFAULT_EMAIL_CAPTURE_REQUIRE_PHONE = false;

// Access duration options (in days)
export const ACCESS_DURATION_OPTIONS = [
  { label: "1 Day", value: 1 },
  { label: "7 Days", value: 7 },
  { label: "30 Days", value: 30 },
  { label: "90 Days", value: 90 },
  { label: "1 Year", value: 365 },
  { label: "Lifetime", value: null },
] as const;

// Session Time Limit
export const MIN_SESSION_LIMIT_MINUTES = 1;
export const MAX_SESSION_LIMIT_MINUTES = 120; // 2 hours
export const DEFAULT_SESSION_LIMIT_MINUTES = 30;

export const MIN_SESSION_WARNING_MINUTES = 1;
export const MAX_SESSION_WARNING_MINUTES = 10;
export const DEFAULT_SESSION_WARNING_MINUTES = 2;

// Session limit duration options (in minutes)
export const SESSION_LIMIT_OPTIONS = [
  { label: "5 minutes", value: 5 },
  { label: "10 minutes", value: 10 },
  { label: "15 minutes", value: 15 },
  { label: "30 minutes", value: 30 },
  { label: "45 minutes", value: 45 },
  { label: "1 hour", value: 60 },
  { label: "1.5 hours", value: 90 },
  { label: "2 hours", value: 120 },
] as const;

// Session warning options (in minutes)
export const SESSION_WARNING_OPTIONS = [
  { label: "1 minute", value: 1 },
  { label: "2 minutes", value: 2 },
  { label: "3 minutes", value: 3 },
  { label: "5 minutes", value: 5 },
  { label: "10 minutes", value: 10 },
] as const;
