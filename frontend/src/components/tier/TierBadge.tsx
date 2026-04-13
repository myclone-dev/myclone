"use client";

import { Crown, Sparkles, Building2, Rocket } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  TIER_FREE,
  TIER_PRO,
  TIER_BUSINESS,
  TIER_ENTERPRISE,
  getTierDisplayName,
} from "@/lib/constants/tiers";
import { cn } from "@/lib/utils";

interface TierBadgeProps {
  /** Tier ID to display */
  tierId?: number | null;
  /** Optional tier name (used if tierId not provided) */
  tierName?: string;
  /** Size variant */
  size?: "sm" | "md" | "lg";
  /** Show icon */
  showIcon?: boolean;
  /** Additional class name */
  className?: string;
}

/**
 * Badge component to display user's subscription tier
 */
export function TierBadge({
  tierId,
  tierName,
  size = "md",
  showIcon = true,
  className,
}: TierBadgeProps) {
  // Determine tier ID from name if not provided
  const effectiveTierId =
    tierId ?? (tierName?.toLowerCase() === "free" ? TIER_FREE : undefined);

  // Get display name
  const displayName = tierName || getTierDisplayName(effectiveTierId);

  // Get tier-specific styles and icon
  const getTierConfig = () => {
    const tier = effectiveTierId ?? TIER_FREE;

    switch (tier) {
      case TIER_FREE:
        return {
          icon: Crown,
          bgClass: "bg-tier-free-bg",
          textClass: "text-tier-free-text",
          borderClass: "border-tier-free-border",
        };
      case TIER_PRO:
        return {
          icon: Sparkles,
          bgClass: "bg-gradient-to-r from-tier-pro-from to-tier-pro-to",
          textClass: "text-tier-pro-text",
          borderClass: "border-tier-pro-border",
        };
      case TIER_BUSINESS:
        return {
          icon: Building2,
          bgClass:
            "bg-gradient-to-r from-tier-business-from to-tier-business-to",
          textClass: "text-tier-business-text",
          borderClass: "border-tier-business-border",
        };
      case TIER_ENTERPRISE:
        return {
          icon: Rocket,
          bgClass:
            "bg-gradient-to-r from-tier-enterprise-from to-tier-enterprise-to",
          textClass: "text-tier-enterprise-text",
          borderClass: "border-tier-enterprise-border",
        };
      default:
        return {
          icon: Crown,
          bgClass: "bg-tier-free-bg",
          textClass: "text-tier-free-text",
          borderClass: "border-tier-free-border",
        };
    }
  };

  const config = getTierConfig();
  const Icon = config.icon;

  // Size classes
  const sizeClasses = {
    sm: "text-xs px-2 py-0.5",
    md: "text-sm px-2.5 py-1",
    lg: "text-base px-3 py-1.5",
  };

  const iconSizes = {
    sm: "size-3",
    md: "size-3.5",
    lg: "size-4",
  };

  return (
    <Badge
      variant="outline"
      className={cn(
        "font-medium capitalize",
        config.bgClass,
        config.textClass,
        config.borderClass,
        sizeClasses[size],
        className,
      )}
    >
      {showIcon && <Icon className={cn("mr-1", iconSizes[size])} />}
      {displayName}
    </Badge>
  );
}
