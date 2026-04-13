import { Card, CardContent } from "@/components/ui/card";
import { formatPrice, formatPricingModel } from "@/lib/queries/stripe";
import type { PersonaMonetizationResponse } from "@/lib/queries/stripe";

interface PreviousPricingCardProps {
  monetizationData: PersonaMonetizationResponse;
}

/**
 * Displays previous pricing configuration when monetization is disabled
 * Shows what settings will be restored when re-enabled
 */
export function PreviousPricingCard({
  monetizationData,
}: PreviousPricingCardProps) {
  return (
    <Card className="border-gray-200 bg-gray-50/50">
      <CardContent className="pt-6">
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-900">
            Previous Pricing Configuration
          </p>
          <p className="text-base font-semibold text-gray-700">
            {formatPrice(
              monetizationData.price_cents,
              monetizationData.currency,
            )}{" "}
            - {formatPricingModel(monetizationData.pricing_model)}
          </p>
          <p className="text-xs text-muted-foreground">
            Toggle monetization ON to re-enable with these saved settings
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
