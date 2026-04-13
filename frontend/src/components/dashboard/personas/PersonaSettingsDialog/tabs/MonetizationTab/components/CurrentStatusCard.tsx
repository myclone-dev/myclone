import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatPrice, formatPricingModel } from "@/lib/queries/stripe";
import type { PersonaMonetizationResponse } from "@/lib/queries/stripe";

interface CurrentStatusCardProps {
  monetizationData: PersonaMonetizationResponse;
}

/**
 * Displays current active monetization status
 * Shows pricing, model, and access duration
 */
export function CurrentStatusCard({
  monetizationData,
}: CurrentStatusCardProps) {
  return (
    <Card className="border-amber-200 bg-amber-50/50">
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-900">Current Status</p>
            <p className="text-lg font-bold text-amber-800">
              {formatPrice(
                monetizationData.price_cents,
                monetizationData.currency,
              )}{" "}
              - {formatPricingModel(monetizationData.pricing_model)}
            </p>
            {monetizationData.access_duration_days && (
              <p className="text-xs text-gray-600">
                Access Duration: {monetizationData.access_duration_days} days
              </p>
            )}
          </div>
          <Badge className="bg-green-100 text-green-800 border-green-300">
            Active
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}
