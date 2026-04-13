"use client";

import { motion } from "motion/react";
import { Loader2 } from "lucide-react";
import type { MonetizationSettings } from "../../types";
import type { PricingModel } from "@/lib/queries/stripe";
import { useGetPersonaMonetization } from "@/lib/queries/stripe";
import { CurrentStatusCard } from "./components/CurrentStatusCard";
import { PricingConfigCard } from "./components/PricingConfigCard";
import { usePriceInput } from "./hooks/usePriceInput";
import { useStripeConnect } from "./hooks/useStripeConnect";

interface MonetizationTabProps {
  personaId: string;
  monetization: MonetizationSettings;
  onChange: (updates: Partial<MonetizationSettings>) => void;
  priceDisplay: string;
  setPriceDisplay: (value: string) => void;
  onInstantToggle?: (checked: boolean) => Promise<void>; // Optional instant toggle handler
  onSetupExpanded?: (expanded: boolean) => void; // Notify parent when setup form is expanded
}

/**
 * Monetization Tab
 * Enable paid access to persona and configure pricing via Stripe
 *
 * KEY BEHAVIOR:
 * - Toggle: If onInstantToggle provided, calls API immediately (instant UX)
 * - Toggle: If onInstantToggle not provided, updates local state (requires Save)
 * - Price/Model changes: Always update local state, require Save button
 * - This allows instant enable/disable while batching price changes
 */
export function MonetizationTab({
  personaId,
  monetization,
  onChange,
  priceDisplay,
  setPriceDisplay,
  onInstantToggle,
  onSetupExpanded,
}: MonetizationTabProps) {
  // Fetch current monetization data from backend
  const { data: monetizationData, isLoading: monetizationLoading } =
    useGetPersonaMonetization(personaId);

  // Price input handlers
  const { handlePriceChange, handlePriceBlur } = usePriceInput(
    priceDisplay,
    setPriceDisplay,
    onChange,
  );

  // Stripe Connect handlers
  const {
    connectStripe,
    viewDashboard,
    handleConnectStripe,
    handleViewDashboard,
  } = useStripeConnect(personaId);

  // Derived state
  const isMonetizationEnabled = monetization.isActive ?? false;
  const hasExistingPricing = !!monetizationData;
  const isStripeConnected = !!monetizationData?.stripe_account_id;

  // Handler: Toggle monetization on/off
  // If onInstantToggle is provided, use it (instant API call)
  // Otherwise, use onChange (requires Save button)
  const handleToggle = async (checked: boolean) => {
    if (onInstantToggle) {
      // Instant toggle - call API immediately
      await onInstantToggle(checked);
    } else {
      // Deferred toggle - update local state, parent save handler calls API
      onChange({ isActive: checked });
    }
  };

  // Handler: Update pricing model
  const handlePricingModelChange = (value: PricingModel) => {
    onChange({ pricingModel: value });
  };

  // Handler: Update access duration
  const handleAccessDurationChange = (value: number) => {
    onChange({ accessDurationDays: value });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="max-w-3xl mx-auto"
    >
      {monetizationLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Single Unified Card */}
          <PricingConfigCard
            monetization={monetization}
            priceDisplay={priceDisplay}
            hasExistingPricing={hasExistingPricing}
            onPricingModelChange={handlePricingModelChange}
            onPriceChange={handlePriceChange}
            onPriceBlur={handlePriceBlur}
            onAccessDurationChange={handleAccessDurationChange}
            monetizationData={monetizationData ?? undefined}
            onConnectStripe={handleConnectStripe}
            onViewDashboard={handleViewDashboard}
            isConnecting={connectStripe.isPending}
            isLoadingDashboard={viewDashboard.isPending}
            isEnabled={isMonetizationEnabled}
            onToggle={handleToggle}
            hasInstantToggle={!!onInstantToggle}
            onSetupExpanded={onSetupExpanded}
          />

          {/* Current Status - Only show when enabled and Stripe is connected */}
          {isMonetizationEnabled && isStripeConnected && monetizationData && (
            <div className="mt-6">
              <CurrentStatusCard monetizationData={monetizationData} />
            </div>
          )}
        </>
      )}
    </motion.div>
  );
}
