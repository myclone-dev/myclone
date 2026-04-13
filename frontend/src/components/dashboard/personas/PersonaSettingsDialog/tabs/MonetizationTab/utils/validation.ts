/**
 * Validation utilities for monetization settings
 */

export const MINIMUM_PRICE_CENTS = 100; // $1.00
export const DEFAULT_PRICE_CENTS = 999; // $9.99
export const MINIMUM_ACCESS_DURATION_DAYS = 1;
export const DEFAULT_ACCESS_DURATION_DAYS = 30;

/**
 * Validate price in dollars
 * Returns cents if valid, or null if invalid
 */
export function validatePrice(priceString: string): number | null {
  const dollars = parseFloat(priceString);

  if (isNaN(dollars) || dollars < 1) {
    return null;
  }

  return Math.round(dollars * 100);
}

/**
 * Format dollars to display string
 */
export function formatDollars(cents: number): string {
  const dollars = cents / 100;
  return dollars.toFixed(2);
}

/**
 * Check if price is valid for monetization
 */
export function isPriceValid(priceInCents: number): boolean {
  return priceInCents >= MINIMUM_PRICE_CENTS;
}
