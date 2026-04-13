import type { MonetizationSettings } from "../../../types";
import {
  validatePrice,
  DEFAULT_PRICE_CENTS,
  formatDollars,
} from "../utils/validation";

/**
 * Hook to manage price input field state and validation
 */
export function usePriceInput(
  priceDisplay: string,
  setPriceDisplay: (value: string) => void,
  onChange: (updates: Partial<MonetizationSettings>) => void,
) {
  const handlePriceChange = (value: string) => {
    // Allow empty, partial numbers, and valid decimals
    if (value === "" || /^\d*\.?\d{0,2}$/.test(value)) {
      setPriceDisplay(value);
    }
  };

  const handlePriceBlur = () => {
    const cents = validatePrice(priceDisplay);

    if (cents === null) {
      // Invalid price - reset to default
      onChange({ priceInCents: DEFAULT_PRICE_CENTS });
      setPriceDisplay(formatDollars(DEFAULT_PRICE_CENTS));
    } else {
      // Valid price - update and format
      onChange({ priceInCents: cents });
      setPriceDisplay(formatDollars(cents));
    }
  };

  return {
    handlePriceChange,
    handlePriceBlur,
  };
}
