import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { NumericInput } from "@/components/ui/numeric-input";
import { AlertCircle } from "lucide-react";
import type { MonetizationSettings } from "../../../types";
import type { PricingModel } from "@/lib/queries/stripe";

interface PricingFormSectionProps {
  monetization: MonetizationSettings;
  priceDisplay: string;
  onPricingModelChange: (value: PricingModel) => void;
  onPriceChange: (value: string) => void;
  onPriceBlur: () => void;
  onAccessDurationChange: (value: number) => void;
}

/**
 * Pricing Form Section
 * Form for configuring pricing model, price, and duration
 */
export function PricingFormSection({
  monetization,
  priceDisplay,
  onPricingModelChange,
  onPriceChange,
  onPriceBlur,
  onAccessDurationChange,
}: PricingFormSectionProps) {
  return (
    <div className="space-y-6">
      {/* Pricing Model Selection */}
      <div className="space-y-2">
        <Label htmlFor="pricing-model" className="text-sm font-medium">
          Pricing Model
        </Label>
        <Select
          value={monetization.pricingModel}
          onValueChange={onPricingModelChange}
        >
          <SelectTrigger id="pricing-model">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="one_time_lifetime" className="!cursor-pointer">
              One-time (Lifetime Access)
            </SelectItem>
            <SelectItem
              value="one_time_duration"
              disabled
              className="!cursor-not-allowed !pointer-events-auto"
            >
              One-time (Limited Duration) - Coming Soon
            </SelectItem>
            <SelectItem
              value="subscription_monthly"
              disabled
              className="!cursor-not-allowed !pointer-events-auto"
            >
              Monthly Subscription - Coming Soon
            </SelectItem>
            <SelectItem
              value="subscription_yearly"
              disabled
              className="!cursor-not-allowed !pointer-events-auto"
            >
              Yearly Subscription - Coming Soon
            </SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          Choose how you want to charge for access
        </p>
      </div>

      {monetization.pricingModel !== "free" && (
        <>
          {/* Price Input */}
          <div className="space-y-2">
            <Label htmlFor="price" className="text-sm font-medium">
              Price (USD)
            </Label>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-semibold text-gray-700">$</span>
              <Input
                id="price"
                type="text"
                inputMode="decimal"
                value={priceDisplay}
                onChange={(e) => onPriceChange(e.target.value)}
                onBlur={onPriceBlur}
                className="text-2xl font-semibold h-14 w-40"
                placeholder="9.99"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Set your price (minimum $1.00)
            </p>
          </div>

          {/* Duration (only for one_time_duration) */}
          {monetization.pricingModel === "one_time_duration" && (
            <div className="space-y-2">
              <Label htmlFor="duration" className="text-sm font-medium">
                Access Duration (days)
              </Label>
              <NumericInput
                id="duration"
                value={monetization.accessDurationDays}
                onChange={(value) => onAccessDurationChange(value ?? 30)}
                min={1}
                placeholder="30"
                className="h-10"
              />
              <p className="text-xs text-muted-foreground">
                How many days should access last after purchase?
              </p>
            </div>
          )}

          {/* Info Box */}
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex gap-3">
              <AlertCircle className="size-5 text-blue-700 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-blue-900">
                  Pricing Information
                </p>
                <ul className="text-xs text-blue-800 space-y-1">
                  <li>• Payments processed securely through Stripe</li>
                  <li>• Users must create an account before purchasing</li>
                  <li>
                    • Changing prices creates a new Stripe price (old
                    subscriptions keep their price)
                  </li>
                  <li>
                    • Disabling monetization sets pricing to free (Stripe data
                    preserved)
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
