"use client";

import { ReactNode } from "react";
import { useUserSubscription } from "@/lib/queries/tier";
import {
  isFreeTier,
  isPaidTier,
  isBusinessOrHigher,
  isEnterpriseTier,
} from "@/lib/constants/tiers";
import { UpgradeCTA } from "./UpgradeCTA";
import { FreeTierBanner } from "./FreeTierBanner";
import { PageLoader } from "@/components/ui/page-loader";

type TierRequirement = "free" | "paid" | "business" | "enterprise";

interface TierGateProps {
  /** Children to render if user has access */
  children: ReactNode;
  /** Minimum tier required to access this feature */
  requiredTier: TierRequirement;
  /** Custom fallback component when user doesn't have access */
  fallback?: ReactNode;
  /** Use banner style instead of full-page block */
  bannerMode?: boolean;
  /** Custom title for the upgrade message */
  title?: string;
  /** Custom description for the upgrade message */
  description?: string;
  /** Custom feature list */
  features?: string[];
  /** Show loading state while checking tier */
  showLoader?: boolean;
}

/**
 * Component that gates content based on user's subscription tier
 * Shows upgrade CTA when user doesn't have required tier
 */
export function TierGate({
  children,
  requiredTier,
  fallback,
  bannerMode = false,
  title,
  description,
  features,
  showLoader = true,
}: TierGateProps) {
  const { data: subscription, isLoading } = useUserSubscription();

  // Show loader while fetching subscription
  if (isLoading && showLoader) {
    return <PageLoader />;
  }

  const tierId = subscription?.tier_id;

  // Check if user meets the tier requirement
  const hasAccess = (() => {
    switch (requiredTier) {
      case "free":
        return true; // Everyone has access to free tier features
      case "paid":
        return isPaidTier(tierId);
      case "business":
        return isBusinessOrHigher(tierId);
      case "enterprise":
        return isEnterpriseTier(tierId);
      default:
        return false;
    }
  })();

  // User has access - render children
  if (hasAccess) {
    return <>{children}</>;
  }

  // User doesn't have access - show fallback or upgrade CTA
  if (fallback) {
    return <>{fallback}</>;
  }

  // Generate default messages based on required tier
  const defaultMessages = {
    paid: {
      title: title || "Upgrade to Pro",
      description:
        description ||
        "This feature requires a Pro plan or higher. Upgrade to unlock more capabilities.",
      features: features || [
        "Increased storage limits",
        "More voice minutes",
        "Higher message limits",
        "Multiple personas",
      ],
    },
    business: {
      title: title || "Business Plan Required",
      description:
        description ||
        "This feature is available on Business plan and above. Upgrade to access advanced features.",
      features: features || [
        "Multiple voice clones",
        "Priority support",
        "Advanced analytics",
        "Team collaboration",
      ],
    },
    enterprise: {
      title: title || "Enterprise Plan Required",
      description:
        description ||
        "This feature is exclusive to Enterprise customers. Contact us for access.",
      features: features || [
        "Unlimited usage",
        "Custom integrations",
        "Dedicated support",
        "SLA guarantees",
      ],
    },
    free: {
      title: title || "Upgrade Your Plan",
      description:
        description || "Upgrade to unlock more features and higher limits.",
      features: features || [],
    },
  };

  const message = defaultMessages[requiredTier];

  if (bannerMode) {
    return (
      <>
        <FreeTierBanner
          title={message.title}
          description={message.description}
          variant="warning"
        />
        {children}
      </>
    );
  }

  return (
    <div className="flex min-h-[400px] items-center justify-center p-8">
      <UpgradeCTA
        title={message.title}
        description={message.description}
        features={message.features}
        showContactOption={requiredTier === "enterprise"}
        className="max-w-lg"
      />
    </div>
  );
}

/**
 * Hook to check if current user has required tier
 */
export function useTierAccess(requiredTier: TierRequirement) {
  const { data: subscription, isLoading } = useUserSubscription();
  const tierId = subscription?.tier_id;

  const hasAccess = (() => {
    if (isLoading) return false;
    switch (requiredTier) {
      case "free":
        return true;
      case "paid":
        return isPaidTier(tierId);
      case "business":
        return isBusinessOrHigher(tierId);
      case "enterprise":
        return isEnterpriseTier(tierId);
      default:
        return false;
    }
  })();

  return {
    hasAccess,
    isLoading,
    tierId,
    tierName: subscription?.tier_name,
    isFreeTier: isFreeTier(tierId),
    isPaidTier: isPaidTier(tierId),
    isBusinessOrHigher: isBusinessOrHigher(tierId),
    isEnterprise: isEnterpriseTier(tierId),
  };
}
