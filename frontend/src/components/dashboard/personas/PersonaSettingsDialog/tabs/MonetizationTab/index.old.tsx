"use client";

import { motion } from "motion/react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { NumericInput } from "@/components/ui/numeric-input";
import {
  DollarSign,
  AlertCircle,
  Loader2,
  CreditCard,
  CheckCircle,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import type { MonetizationSettings } from "../../types";
import type { PricingModel } from "@/lib/queries/stripe";
import {
  useGetPersonaMonetization,
  useUpdateMonetization,
  useEnableMonetization,
  useStripeConnectOnboard,
  useStripeConnectDashboard,
  formatPrice,
  formatPricingModel,
} from "@/lib/queries/stripe";
import { cn } from "@/lib/utils";

interface MonetizationTabProps {
  personaId: string;
  monetization: MonetizationSettings;
  onChange: (updates: Partial<MonetizationSettings>) => void;
  priceDisplay: string;
  setPriceDisplay: (value: string) => void;
}

/**
 * Monetization Tab
 * Enable paid access to persona and configure pricing via Stripe
 */
export function MonetizationTab({
  personaId,
  monetization,
  onChange,
  priceDisplay,
  setPriceDisplay,
}: MonetizationTabProps) {
  const { data: monetizationData, isLoading: monetizationLoading } =
    useGetPersonaMonetization(personaId);
  const updateMonetization = useUpdateMonetization(personaId);
  const enableMonetization = useEnableMonetization(personaId);
  const connectStripe = useStripeConnectOnboard(personaId);
  const viewDashboard = useStripeConnectDashboard(personaId);

  // Determine if monetization is currently enabled
  const isMonetizationEnabled = monetizationData?.is_active ?? false;
  const hasExistingPricing = !!monetizationData;

  const handlePriceChange = (value: string) => {
    // Allow empty, partial numbers, and valid decimals
    if (value === "" || /^\d*\.?\d{0,2}$/.test(value)) {
      setPriceDisplay(value);
    }
  };

  const handlePriceBlur = () => {
    const dollars = parseFloat(priceDisplay);
    if (isNaN(dollars) || dollars < 1) {
      // Reset to default $9.99
      onChange({ priceInCents: 999 });
      setPriceDisplay("9.99");
    } else {
      // Update cents and format display
      onChange({ priceInCents: Math.round(dollars * 100) });
      setPriceDisplay(dollars.toFixed(2));
    }
  };

  const handleToggleMonetization = async (checked: boolean) => {
    if (checked) {
      // ENABLING MONETIZATION
      if (hasExistingPricing) {
        // Re-enabling with existing pricing
        try {
          await updateMonetization.mutateAsync({ is_active: true });
          toast.success("Monetization enabled");
        } catch (error) {
          console.error("Failed to enable monetization:", error);
          toast.error("Failed to enable monetization");
        }
      } else {
        // First time - use form values (parent component sets defaults)
        try {
          const requestData: {
            pricing_model: typeof monetization.pricingModel;
            price_cents: number;
            currency: "usd";
            access_duration_days?: number | null;
          } = {
            pricing_model: monetization.pricingModel,
            price_cents: monetization.priceInCents,
            currency: "usd",
          };

          // Only include access_duration_days for one_time_duration model
          if (monetization.pricingModel === "one_time_duration") {
            requestData.access_duration_days = monetization.accessDurationDays;
          }

          await enableMonetization.mutateAsync(requestData);
          toast.success("Monetization enabled");
        } catch (error) {
          console.error("Failed to enable monetization:", error);
          toast.error("Failed to enable monetization");
        }
      }
    } else {
      // DISABLING MONETIZATION
      if (hasExistingPricing && monetizationData.is_active) {
        try {
          await updateMonetization.mutateAsync({ is_active: false });
          toast.success("Monetization disabled - persona is now free");
        } catch (error) {
          console.error("Failed to disable monetization:", error);
          toast.error("Failed to disable monetization");
        }
      }
    }
  };

  const handleConnectStripe = () => {
    connectStripe.mutate();
  };

  const handleViewDashboard = () => {
    viewDashboard.mutate();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="space-y-4 sm:space-y-6 max-w-3xl mx-auto"
    >
      {monetizationLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <div className="space-y-2">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <DollarSign className="size-5" />
              Monetization Settings
            </h3>
            <p className="text-sm text-muted-foreground">
              Enable paid access to your persona and configure pricing
            </p>
          </div>

          {/* Toggle Switch for Enable/Disable Monetization */}
          <Card className="border-2">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="monetization-toggle" className="text-base">
                    Enable Monetization
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Charge visitors to access this persona
                  </p>
                </div>
                <Switch
                  id="monetization-toggle"
                  checked={isMonetizationEnabled}
                  onCheckedChange={handleToggleMonetization}
                  disabled={
                    updateMonetization.isPending || enableMonetization.isPending
                  }
                />
              </div>
            </CardContent>
          </Card>

          {/* Current Status - Only show when monetization is enabled */}
          {monetizationData && isMonetizationEnabled && (
            <Card className="border-amber-200 bg-amber-50/50">
              <CardContent className="pt-6">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-gray-900">
                      Current Status
                    </p>
                    <p className="text-lg font-bold text-amber-800">
                      {formatPrice(
                        monetizationData.price_cents,
                        monetizationData.currency,
                      )}{" "}
                      - {formatPricingModel(monetizationData.pricing_model)}
                    </p>
                    {monetizationData.access_duration_days && (
                      <p className="text-xs text-gray-600">
                        Access Duration: {monetizationData.access_duration_days}{" "}
                        days
                      </p>
                    )}
                  </div>
                  <Badge className="bg-green-100 text-green-800 border-green-300">
                    Active
                  </Badge>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Stripe Connect Card - Only show when monetization is active */}
          {monetizationData && isMonetizationEnabled && (
            <Card
              className={cn(
                "border-2",
                monetizationData.stripe_account_id
                  ? "border-green-200 bg-green-50/30"
                  : "border-amber-200 bg-amber-50/30",
              )}
            >
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CreditCard className="size-4" />
                  Receive Payouts via Stripe
                </CardTitle>
                <CardDescription>
                  {monetizationData.stripe_account_id
                    ? "Your Stripe account is connected and ready to receive payments"
                    : "Connect your Stripe account to receive payments from your paid persona"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {monetizationData.stripe_account_id ? (
                  // CONNECTED STATE
                  <>
                    <div className="flex items-center gap-3 p-4 bg-green-100 border border-green-300 rounded-lg">
                      <CheckCircle className="size-5 text-green-700 shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-green-900">
                          ✓ Connected to Stripe
                        </p>
                        <p className="text-xs text-green-700">
                          Payments will be deposited to your connected bank
                          account
                        </p>
                      </div>
                    </div>

                    <button
                      onClick={handleViewDashboard}
                      disabled={viewDashboard.isPending}
                      className="w-full inline-flex items-center justify-center gap-2 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
                    >
                      {viewDashboard.isPending ? (
                        <>
                          <Loader2 className="size-4 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        <>
                          <ExternalLink className="size-4" />
                          View Stripe Dashboard
                        </>
                      )}
                    </button>

                    <p className="text-xs text-muted-foreground">
                      View earnings, payout history, and manage your bank
                      account
                    </p>
                  </>
                ) : (
                  // NOT CONNECTED STATE
                  <>
                    <div className="p-4 bg-amber-100 border border-amber-300 rounded-lg">
                      <div className="flex gap-3">
                        <AlertCircle className="size-5 text-amber-700 shrink-0" />
                        <div className="space-y-1">
                          <p className="text-sm font-medium text-amber-900">
                            Action Required
                          </p>
                          <p className="text-sm text-amber-800">
                            You must connect your Stripe account to receive
                            payments. Without this, visitors cannot purchase
                            access to your persona.
                          </p>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={handleConnectStripe}
                      disabled={connectStripe.isPending}
                      className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
                    >
                      {connectStripe.isPending ? (
                        <>
                          <Loader2 className="size-4 animate-spin" />
                          Connecting...
                        </>
                      ) : (
                        <>
                          <ExternalLink className="size-4" />
                          Connect Stripe Account
                        </>
                      )}
                    </button>

                    <p className="text-xs text-muted-foreground">
                      You'll be redirected to Stripe to complete a quick
                      onboarding process
                    </p>
                  </>
                )}
              </CardContent>
            </Card>
          )}

          {/* Previous Pricing - Show when disabled but has pricing */}
          {monetizationData && !isMonetizationEnabled && (
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
                    Toggle monetization ON to re-enable with these saved
                    settings
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Pricing Configuration - Only show when enabled */}
          {isMonetizationEnabled && (
            <Card className="border-2">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <DollarSign className="size-4" />
                  {monetizationData ? "Update Pricing" : "Configure Pricing"}
                </CardTitle>
                <CardDescription>
                  {monetizationData
                    ? "Modify your persona's pricing model and amount"
                    : "Set up paid access for your persona"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Pricing Model Selection */}
                <div className="space-y-2">
                  <Label
                    htmlFor="pricing-model"
                    className="text-sm font-medium"
                  >
                    Pricing Model
                  </Label>
                  <Select
                    value={monetization.pricingModel}
                    onValueChange={(value) =>
                      onChange({ pricingModel: value as PricingModel })
                    }
                  >
                    <SelectTrigger id="pricing-model">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        value="one_time_lifetime"
                        className="!cursor-pointer"
                      >
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
                        <span className="text-2xl font-semibold text-gray-700">
                          $
                        </span>
                        <Input
                          id="price"
                          type="text"
                          inputMode="decimal"
                          value={priceDisplay}
                          onChange={(e) => handlePriceChange(e.target.value)}
                          onBlur={handlePriceBlur}
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
                        <Label
                          htmlFor="duration"
                          className="text-sm font-medium"
                        >
                          Access Duration (days)
                        </Label>
                        <NumericInput
                          id="duration"
                          value={monetization.accessDurationDays}
                          onChange={(value) =>
                            onChange({ accessDurationDays: value ?? 30 })
                          }
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
                            <li>
                              • Payments processed securely through Stripe
                            </li>
                            <li>
                              • Users must create an account before purchasing
                            </li>
                            <li>
                              • Changing prices creates a new Stripe price (old
                              subscriptions keep their price)
                            </li>
                            <li>
                              • Disabling monetization sets pricing to free
                              (Stripe data preserved)
                            </li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </motion.div>
  );
}
