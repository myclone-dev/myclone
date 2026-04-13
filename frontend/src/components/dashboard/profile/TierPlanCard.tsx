"use client";

import { Crown, Calendar, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageLoader } from "@/components/ui/page-loader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useUserSubscription } from "@/lib/queries/tier";
import type { UserMeResponse } from "@/lib/queries/users/useUserMe";
import { CONTACT } from "@/lib/constants/urls";

interface TierPlanCardProps {
  user?: UserMeResponse;
}

const TIER_COLORS = {
  free: "bg-tier-free-bg text-tier-free-text border-tier-free-border",
  pro: "bg-gradient-to-r from-violet-500 to-purple-600 text-white border-purple-700",
  business:
    "bg-gradient-to-r from-blue-500 to-indigo-600 text-white border-indigo-700",
  enterprise:
    "bg-gradient-to-r from-amber-500 to-orange-600 text-white border-orange-700",
};

const TIER_ICONS = {
  free: Sparkles,
  pro: Crown,
  business: Crown,
  enterprise: Crown,
};

export function TierPlanCard({ user: _user }: TierPlanCardProps) {
  const { data: subscription, isLoading, error } = useUserSubscription();

  if (isLoading) {
    return (
      <Card className="p-6">
        <PageLoader />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <Alert variant="destructive">
          <AlertDescription>
            Failed to load subscription information. Please try again later.
          </AlertDescription>
        </Alert>
      </Card>
    );
  }

  if (!subscription) {
    return null;
  }

  const tierName = subscription.tier_name.toLowerCase();
  const TierIcon = TIER_ICONS[tierName as keyof typeof TIER_ICONS] || Sparkles;
  const tierColor =
    TIER_COLORS[tierName as keyof typeof TIER_COLORS] || TIER_COLORS.free;

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  };

  const isExpiringSoon =
    subscription.subscription_end_date &&
    new Date(subscription.subscription_end_date) <
      new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 days

  return (
    <Card className="overflow-hidden">
      {/* Header with gradient background */}
      <div
        className={`${tierColor} border-b-2 px-6 py-4 transition-all duration-300`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm">
              <TierIcon className="size-5" />
            </div>
            <div>
              <h3 className="text-lg font-semibold capitalize">
                {subscription.tier_name} Plan
              </h3>
              <p
                className={`text-sm ${tierName === "free" ? "text-slate-600" : "text-white/90"}`}
              >
                Current subscription
              </p>
            </div>
          </div>
          <Badge
            variant={subscription.status === "active" ? "default" : "secondary"}
            className="capitalize"
          >
            {subscription.status}
          </Badge>
        </div>
      </div>

      {/* Subscription Details */}
      <div className="space-y-4 p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Calendar className="size-4" />
              <span className="font-medium">Started</span>
            </div>
            <p className="text-sm font-semibold text-slate-900">
              {formatDate(subscription.subscription_start_date)}
            </p>
          </div>

          {subscription.subscription_end_date && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Calendar className="size-4" />
                <span className="font-medium">Expires</span>
              </div>
              <p
                className={`text-sm font-semibold ${isExpiringSoon ? "text-orange-600" : "text-slate-900"}`}
              >
                {formatDate(subscription.subscription_end_date)}
                {isExpiringSoon && " (Expiring soon)"}
              </p>
            </div>
          )}

          {!subscription.subscription_end_date && tierName !== "free" && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Calendar className="size-4" />
                <span className="font-medium">Expires</span>
              </div>
              <p className="text-sm font-semibold text-slate-900">
                Never (Lifetime)
              </p>
            </div>
          )}
        </div>

        {/* Upgrade CTA for free tier */}
        {tierName === "free" && (
          <Alert className="border-alert-info-border bg-alert-info-bg">
            <Crown className="size-4 text-alert-info-accent" />
            <AlertDescription className="text-sm text-alert-info-text">
              Upgrade to <span className="font-semibold">Pro</span> or{" "}
              <span className="font-semibold">Business</span> for increased
              limits and features. Contact{" "}
              <a
                href={CONTACT.MAILTO}
                className="font-semibold text-alert-info-accent underline hover:text-alert-info-accent-hover"
              >
                {CONTACT.EMAIL}
              </a>{" "}
              to upgrade your plan.
            </AlertDescription>
          </Alert>
        )}
      </div>
    </Card>
  );
}
