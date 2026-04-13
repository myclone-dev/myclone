import React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { DollarSign, Settings, ChevronDown, ChevronUp } from "lucide-react";
import type { MonetizationSettings } from "../../../types";
import type {
  PricingModel,
  PersonaMonetizationResponse,
} from "@/lib/queries/stripe";
import { StripeConnectionSection } from "./StripeConnectionSection";
import { PricingFormSection } from "./PricingFormSection";

interface PricingConfigCardProps {
  monetization: MonetizationSettings;
  priceDisplay: string;
  hasExistingPricing: boolean;
  onPricingModelChange: (value: PricingModel) => void;
  onPriceChange: (value: string) => void;
  onPriceBlur: () => void;
  onAccessDurationChange: (value: number) => void;
  // Stripe connection props
  monetizationData: PersonaMonetizationResponse | undefined;
  onConnectStripe: () => void;
  onViewDashboard: () => void;
  isConnecting: boolean;
  isLoadingDashboard: boolean;
  // Toggle props
  isEnabled: boolean;
  onToggle: (checked: boolean) => void | Promise<void>;
  hasInstantToggle: boolean;
  // Setup expanded callback
  onSetupExpanded?: (expanded: boolean) => void;
}

/**
 * Monetization Settings Card
 * Single unified card with toggle, pricing config, and Stripe connection
 */
export function PricingConfigCard({
  monetization,
  priceDisplay,
  hasExistingPricing: _hasExistingPricing,
  onPricingModelChange,
  onPriceChange,
  onPriceBlur,
  onAccessDurationChange,
  monetizationData,
  onConnectStripe,
  onViewDashboard,
  isConnecting,
  isLoadingDashboard,
  isEnabled,
  onToggle,
  hasInstantToggle,
  onSetupExpanded,
}: PricingConfigCardProps) {
  const [isSetupExpanded, setIsSetupExpanded] = React.useState(false);

  // Determine if we're in first-time setup mode
  const isFirstTimeSetup = hasInstantToggle && !monetizationData;

  // Show form when: (1) First-time setup AND expanded OR (2) Toggle is enabled
  const shouldShowForm = (isFirstTimeSetup && isSetupExpanded) || isEnabled;

  // Handle setup expand/collapse
  const handleSetupToggle = () => {
    const newExpanded = !isSetupExpanded;
    setIsSetupExpanded(newExpanded);
    onSetupExpanded?.(newExpanded);
  };
  return (
    <Card className="border-2">
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <DollarSign className="size-4" />
          Monetization Settings
        </CardTitle>
        <CardDescription>
          Enable paid access to your persona and configure pricing
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* First-time setup: Show setup button */}
        {isFirstTimeSetup ? (
          <div className="flex items-center justify-between">
            <div className="space-y-0.5 flex-1">
              <Label className="text-sm font-medium">Setup Monetization</Label>
              <p className="text-xs text-muted-foreground">
                {isSetupExpanded
                  ? "Configure pricing settings below and click Save to enable monetization"
                  : "Click Setup to configure pricing and enable monetization"}
              </p>
            </div>
            <Button variant="outline" onClick={handleSetupToggle}>
              <Settings className="size-4 mr-2" />
              Setup
              {isSetupExpanded ? (
                <ChevronUp className="size-4 ml-2" />
              ) : (
                <ChevronDown className="size-4 ml-2" />
              )}
            </Button>
          </div>
        ) : (
          /* After setup: Show toggle for instant enable/disable */
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label
                htmlFor="monetization-enabled"
                className="text-sm font-medium"
              >
                Enable monetization
              </Label>
              <p className="text-xs text-muted-foreground">
                When enabled, users must pay to access your persona
              </p>
            </div>
            <Switch
              id="monetization-enabled"
              checked={isEnabled}
              onCheckedChange={onToggle}
            />
          </div>
        )}

        {shouldShowForm && (
          <>
            <div className="h-px bg-border" />

            {/* Stripe Connection Section - Only show after monetization is set up */}
            {!isFirstTimeSetup && (
              <>
                <StripeConnectionSection
                  monetizationData={monetizationData}
                  onConnectStripe={onConnectStripe}
                  onViewDashboard={onViewDashboard}
                  isConnecting={isConnecting}
                  isLoadingDashboard={isLoadingDashboard}
                />

                {/* Divider */}
                <div className="h-px bg-border" />
              </>
            )}

            {/* Pricing Configuration */}
            <PricingFormSection
              monetization={monetization}
              priceDisplay={priceDisplay}
              onPricingModelChange={onPricingModelChange}
              onPriceChange={onPriceChange}
              onPriceBlur={onPriceBlur}
              onAccessDurationChange={onAccessDurationChange}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
}
