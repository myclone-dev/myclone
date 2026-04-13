"use client";

import { Crown, ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { EXTERNAL_URLS, CONTACT } from "@/lib/constants/urls";

interface UpgradeCTAProps {
  /** Title for the CTA */
  title?: string;
  /** Description/message */
  description?: string;
  /** List of features/benefits */
  features?: string[];
  /** Link to upgrade page */
  upgradeLink?: string;
  /** Custom CTA button text */
  ctaText?: string;
  /** Variant style */
  variant?: "card" | "inline" | "minimal";
  /** Additional class name */
  className?: string;
  /** Show contact option instead of direct upgrade */
  showContactOption?: boolean;
  /** Contact email */
  contactEmail?: string;
}

/**
 * Reusable upgrade CTA component with multiple variants
 */
export function UpgradeCTA({
  title = "Upgrade Your Plan",
  description = "Get more features and higher limits with a paid plan.",
  features = [
    "More storage and files",
    "Higher usage limits",
    "Priority support",
    "Advanced features",
  ],
  upgradeLink = EXTERNAL_URLS.PRICING,
  ctaText = "View Plans",
  variant = "card",
  className,
  showContactOption = false,
  contactEmail = CONTACT.EMAIL,
}: UpgradeCTAProps) {
  if (variant === "minimal") {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <Crown className="size-4 text-banner-yellow-icon" />
        <span className="text-sm text-muted-foreground">{description}</span>
        <Button
          variant="link"
          size="sm"
          className="h-auto gap-1 p-0 text-sm"
          asChild
        >
          <a href={upgradeLink} target="_blank" rel="noopener noreferrer">
            {ctaText}
            <ArrowRight className="size-3" />
          </a>
        </Button>
      </div>
    );
  }

  if (variant === "inline") {
    return (
      <div
        className={cn(
          "flex flex-col gap-3 rounded-lg border border-banner-yellow-border bg-banner-yellow-bg p-4 sm:flex-row sm:items-center sm:justify-between",
          className,
        )}
      >
        <div className="flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-yellow-bright">
            <Crown className="size-5 text-white" />
          </div>
          <div>
            <p className="font-medium text-banner-yellow-text">{title}</p>
            <p className="text-sm text-banner-yellow-icon">{description}</p>
          </div>
        </div>
        <Button className="w-full gap-2 sm:w-auto" variant="default" asChild>
          <a href={upgradeLink} target="_blank" rel="noopener noreferrer">
            {ctaText}
            <ArrowRight className="size-4" />
          </a>
        </Button>
      </div>
    );
  }

  // Card variant (default)
  return (
    <Card
      className={cn(
        "border-banner-yellow-border bg-banner-yellow-bg/50",
        className,
      )}
    >
      <CardHeader>
        <div className="flex items-start gap-4">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-yellow-400 to-orange-500">
            <Crown className="size-6 text-white" />
          </div>
          <div className="flex-1">
            <CardTitle>{title}</CardTitle>
            <CardDescription className="mt-1">{description}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {features.length > 0 && (
          <div className="grid gap-2 text-sm sm:grid-cols-2">
            {features.map((feature, index) => (
              <div key={index} className="flex items-center gap-2">
                <Check className="size-4 text-green-600" />
                <span>{feature}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-2 sm:flex-row">
          <Button className="flex-1 gap-2" asChild>
            <a href={upgradeLink} target="_blank" rel="noopener noreferrer">
              {ctaText}
              <ArrowRight className="size-4" />
            </a>
          </Button>
          {showContactOption && (
            <Button variant="outline" className="flex-1" asChild>
              <a href={`mailto:${contactEmail}`}>Contact Sales</a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
