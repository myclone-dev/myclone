/**
 * External URLs and contact information
 * Centralized constants to avoid magic strings throughout the codebase
 */

const WEBSITE_URL =
  process.env.NEXT_PUBLIC_WEBSITE_URL || "http://localhost:3000";

export const EXTERNAL_URLS = {
  /** Pricing page for upgrade CTAs */
  PRICING: `${WEBSITE_URL}/pricing`,

  /** Main website */
  WEBSITE: WEBSITE_URL,

  /** Documentation */
  DOCS: `${WEBSITE_URL}/docs`,
} as const;

const SUPPORT_EMAIL =
  process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "support@example.com";

export const CONTACT = {
  /** Support/sales email */
  EMAIL: SUPPORT_EMAIL,

  /** Full mailto link */
  MAILTO: `mailto:${SUPPORT_EMAIL}`,
} as const;
