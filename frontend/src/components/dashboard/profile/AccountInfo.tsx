"use client";

import { Clock, Crown, Sparkles, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useUserSubscription } from "@/lib/queries/tier";
import type { UserMeResponse } from "@/lib/queries/users/useUserMe";
import { CONTACT, EXTERNAL_URLS } from "@/lib/constants/urls";

interface AccountInfoProps {
  user: UserMeResponse;
}

const TIER_COLORS = {
  free: {
    bg: "bg-slate-100",
    text: "text-slate-700",
    border: "border-slate-300",
  },
  pro: {
    bg: "bg-amber-100",
    text: "text-amber-700",
    border: "border-amber-300",
  },
  business: {
    bg: "bg-yellow-light",
    text: "text-ai-brown",
    border: "border-yellow-bright/30",
  },
  enterprise: {
    bg: "bg-yellow-light",
    text: "text-ai-brown",
    border: "border-yellow-bright/30",
  },
};

export function AccountInfo({ user }: AccountInfoProps) {
  const {
    data: subscription,
    isLoading: subscriptionLoading,
    error,
  } = useUserSubscription();

  const tierName =
    subscription?.tier_name.toLowerCase() as keyof typeof TIER_COLORS;
  const tierColors =
    tierName && TIER_COLORS[tierName]
      ? TIER_COLORS[tierName]
      : TIER_COLORS.free;

  return (
    <Card className="p-6">
      <h3 className="mb-4 text-lg font-semibold text-slate-900">
        Account Information
      </h3>

      <div className="space-y-4">
        {/* Account Type with Plan */}
        {subscriptionLoading ? (
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
              <div className="size-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
            </div>
            <div className="flex-1">
              <div className="h-5 w-24 animate-pulse rounded bg-slate-200" />
              <div className="mt-1 h-4 w-16 animate-pulse rounded bg-slate-100" />
            </div>
          </div>
        ) : error ? (
          <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-red-100 text-red-600">
              <ShieldCheck className="size-5" />
            </div>
            <div>
              <p className="font-medium text-red-900">Error Loading Plan</p>
              <p className="text-sm text-red-700">
                {error instanceof Error
                  ? error.message
                  : "Failed to load subscription"}
              </p>
            </div>
          </div>
        ) : subscription ? (
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-peach-cream text-ai-brown">
              <ShieldCheck className="size-5" />
            </div>
            <div>
              <p className="font-medium text-slate-900">Current Plan</p>
              <div className="flex items-center gap-2">
                <p
                  className={`text-sm font-semibold capitalize ${tierColors.text}`}
                >
                  {subscription.tier_name}
                </p>
                <Badge
                  variant={
                    subscription.status === "active" ? "default" : "secondary"
                  }
                  className="text-xs"
                >
                  {subscription.status}
                </Badge>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-3 rounded-lg border border-yellow-200 bg-yellow-50 p-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-yellow-100 text-yellow-700">
              <ShieldCheck className="size-5" />
            </div>
            <div>
              <p className="font-medium text-yellow-900">
                No Subscription Found
              </p>
              <p className="text-sm text-yellow-700">
                Unable to load subscription data. Please contact support.
              </p>
            </div>
          </div>
        )}

        {/* Last Updated */}
        <div className="flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
            <Clock className="size-5" />
          </div>
          <div>
            <p className="font-medium text-slate-900">Last Updated</p>
            <p className="text-sm text-slate-600">
              {new Date(user.updated_at).toLocaleString()}
            </p>
          </div>
        </div>

        {/* Upgrade CTA - hide for Enterprise users */}
        {subscription &&
          subscription.tier_name.toLowerCase() !== "enterprise" && (
            <div className="mt-4 rounded-lg border-2 border-yellow-bright/30 bg-gradient-to-br from-yellow-light to-peach-cream p-5 shadow-sm">
              {/* Header */}
              <div className="mb-4 flex items-start gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-yellow-bright shadow-sm">
                  <Sparkles className="size-5 text-ai-brown" />
                </div>
                <div className="flex-1">
                  <h4 className="text-base font-semibold text-slate-900">
                    Upgrade to unlock more features
                  </h4>
                  <p className="mt-0.5 text-sm text-slate-600">
                    Get increased limits and advanced capabilities with our paid
                    plans
                  </p>
                </div>
              </div>

              {/* Tier Options Grid */}
              <div
                className={`mb-4 grid gap-3 ${
                  subscription.tier_name.toLowerCase() === "free"
                    ? "sm:grid-cols-3"
                    : subscription.tier_name.toLowerCase() === "pro"
                      ? "sm:grid-cols-2"
                      : "sm:grid-cols-1"
                }`}
              >
                {/* Pro Tier - hide for Pro users and above */}
                {subscription.tier_name.toLowerCase() === "free" && (
                  <a
                    href={EXTERNAL_URLS.PRICING}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group relative block overflow-hidden rounded-lg border border-amber-200 bg-white p-3.5 shadow-sm transition-all hover:border-amber-300 hover:shadow hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-2"
                  >
                    <div className="absolute right-2 top-2 opacity-5 transition-opacity group-hover:opacity-10">
                      <Crown className="size-12 text-amber-600" />
                    </div>
                    <div className="relative">
                      <div className="mb-2 flex size-8 items-center justify-center rounded-lg bg-amber-50">
                        <Crown className="size-4 text-amber-600" />
                      </div>
                      <h5 className="text-sm font-semibold text-slate-900">
                        Pro
                      </h5>
                      <p className="mt-0.5 text-xs text-slate-600">
                        Perfect for individuals
                      </p>
                    </div>
                  </a>
                )}

                {/* Business Tier - hide for Business users and above */}
                {(subscription.tier_name.toLowerCase() === "free" ||
                  subscription.tier_name.toLowerCase() === "pro") && (
                  <a
                    href={EXTERNAL_URLS.PRICING}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group relative block overflow-hidden rounded-lg border border-amber-200 bg-white p-3.5 shadow-sm transition-all hover:border-amber-300 hover:shadow hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-2"
                  >
                    <div className="absolute right-2 top-2 opacity-5 transition-opacity group-hover:opacity-10">
                      <Crown className="size-12 text-amber-600" />
                    </div>
                    <div className="relative">
                      <div className="mb-2 flex size-8 items-center justify-center rounded-lg bg-amber-50">
                        <Crown className="size-4 text-amber-600" />
                      </div>
                      <h5 className="text-sm font-semibold text-slate-900">
                        Business
                      </h5>
                      <p className="mt-0.5 text-xs text-slate-600">
                        Designed for teams
                      </p>
                    </div>
                  </a>
                )}

                {/* Enterprise Tier - always show except for Enterprise users */}
                <a
                  href={EXTERNAL_URLS.PRICING}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group relative block overflow-hidden rounded-lg border border-yellow-bright/40 bg-white p-3.5 shadow-sm transition-all hover:border-yellow-bright/60 hover:shadow hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-yellow-bright focus:ring-offset-2"
                >
                  <div className="absolute right-2 top-2 opacity-5 transition-opacity group-hover:opacity-10">
                    <Crown className="size-12 text-ai-brown" />
                  </div>
                  <div className="relative">
                    <div className="mb-2 flex size-8 items-center justify-center rounded-lg bg-yellow-light">
                      <Crown className="size-4 text-ai-brown" />
                    </div>
                    <h5 className="text-sm font-semibold text-slate-900">
                      Enterprise
                    </h5>
                    <p className="mt-0.5 text-xs text-slate-600">
                      Custom solutions
                    </p>
                  </div>
                </a>
              </div>

              {/* Footer CTA */}
              <div className="flex flex-col gap-3 border-t border-yellow-bright/30 pt-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-900">
                    Ready to upgrade?
                  </p>
                  <p className="mt-0.5 text-xs text-slate-600">
                    Email us at{" "}
                    <a
                      href={CONTACT.MAILTO}
                      className="font-semibold text-ai-brown underline decoration-ai-brown/30 underline-offset-2 transition-colors hover:text-ai-brown/80"
                    >
                      {CONTACT.EMAIL}
                    </a>
                  </p>
                </div>
                <a
                  href={EXTERNAL_URLS.PRICING}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-yellow-bright px-5 py-2.5 text-sm font-semibold text-black shadow-sm transition-all hover:bg-yellow-bright/90 hover:shadow focus:outline-none focus:ring-2 focus:ring-yellow-bright focus:ring-offset-2"
                >
                  View Plans
                  <svg
                    className="size-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                </a>
              </div>
            </div>
          )}
      </div>
    </Card>
  );
}
