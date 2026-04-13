import type { PricingModel } from "@/lib/queries/stripe";

/**
 * Format price in cents to dollar string
 * @example formatPrice(999) => "$9.99"
 */
export function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

/**
 * Parse price string to cents
 * @example parsePriceToCents("9.99") => 999
 */
export function parsePriceToCents(priceString: string): number {
  const price = parseFloat(priceString);
  if (isNaN(price)) return 0;
  return Math.round(price * 100);
}

/**
 * Format cents to price input value (without $)
 * @example formatPriceInput(999) => "9.99"
 */
export function formatPriceInput(cents: number): string {
  return (cents / 100).toFixed(2);
}

/**
 * Format pricing model for display
 */
export function formatPricingModel(model: PricingModel): string {
  switch (model) {
    case "free":
      return "Free";
    case "one_time_lifetime":
      return "One-time (Lifetime)";
    case "one_time_duration":
      return "One-time (Duration)";
    case "subscription_monthly":
      return "Monthly Subscription";
    case "subscription_yearly":
      return "Yearly Subscription";
    default:
      return model;
  }
}

/**
 * Format access duration in days to human-readable string
 */
export function formatAccessDuration(days: number | null): string {
  if (days === null) return "Lifetime";
  if (days === 1) return "1 Day";
  if (days === 7) return "1 Week";
  if (days === 30) return "1 Month";
  if (days === 90) return "3 Months";
  if (days === 365) return "1 Year";
  return `${days} Days`;
}

/**
 * Truncate text to max length with ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + "...";
}

/**
 * Format date to relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffDay > 0) return `${diffDay} day${diffDay > 1 ? "s" : ""} ago`;
  if (diffHour > 0) return `${diffHour} hour${diffHour > 1 ? "s" : ""} ago`;
  if (diffMin > 0) return `${diffMin} minute${diffMin > 1 ? "s" : ""} ago`;
  return "Just now";
}
