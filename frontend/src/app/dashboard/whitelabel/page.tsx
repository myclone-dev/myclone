"use client";

import { useState } from "react";
import { Globe, Mail, Tag, Crown } from "lucide-react";
import { useUserMe } from "@/lib/queries/users";
import { useUserSubscription } from "@/lib/queries/tier";
import {
  hasCustomEmailDomainAccess,
  isPaidTier,
  getTierDisplayName,
} from "@/lib/constants/tiers";
import { PageLoader } from "@/components/ui/page-loader";
import { Badge } from "@/components/ui/badge";
import { CustomDomainSection } from "@/components/dashboard/widgets/CustomDomainSection";
import { EmailDomainsSection } from "@/components/dashboard/profile/EmailDomainsSection";

type WhitelabelMode = "domain" | "email";

/**
 * Whitelabel Page
 * Manage custom domains for website hosting and email sending
 * - Custom Domain: Host your AI clone on your own domain (Pro+ users)
 * - Custom Email Domain: Send verification emails from your domain (Enterprise)
 */
export default function WhitelabelPage() {
  const [mode, setMode] = useState<WhitelabelMode>("domain");
  const { data: user, isLoading: isLoadingUser } = useUserMe();
  const { data: subscription, isLoading: isLoadingSubscription } =
    useUserSubscription();

  if (isLoadingUser || isLoadingSubscription || !user) {
    return <PageLoader />;
  }

  const tierId = subscription?.tier_id;
  const isPaid = isPaidTier(tierId);
  const hasEmailDomainAccess = hasCustomEmailDomainAccess(tierId);

  return (
    <div className="max-w-7xl mx-auto py-4 space-y-6 px-4 sm:py-8 sm:space-y-8 sm:px-6 lg:px-8">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="flex size-10 sm:size-12 items-center justify-center rounded-full bg-yellow-bright shrink-0">
            <Tag className="size-5 sm:size-6 text-gray-900" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-slate-900 sm:text-2xl">
              Whitelabel
            </h1>
            <p className="text-xs text-slate-600 sm:text-sm">
              Customize your brand with custom domains and email
            </p>
          </div>
        </div>

        {/* Current Tier Info */}
        <div className="flex items-center gap-2 text-sm text-slate-600 bg-slate-100 px-3 py-1.5 rounded-lg">
          <span>Plan:</span>
          <span className="font-medium text-slate-900">
            {getTierDisplayName(tierId)}
          </span>
        </div>
      </div>

      {/* ============================================== */}
      {/* Mode Selection Cards */}
      {/* ============================================== */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Custom Domain Card */}
        <button
          onClick={() => setMode("domain")}
          className={`relative group text-left p-4 sm:p-5 rounded-xl border transition-all duration-300 ease-in-out ${
            mode === "domain"
              ? "border-ai-brown bg-yellow-light/50 shadow-md"
              : "border-slate-200 bg-white hover:border-ai-brown/40 hover:bg-yellow-light/10 hover:shadow-sm"
          }`}
        >
          {/* Pro badge */}
          {!isPaid && (
            <div className="absolute -top-2.5 left-4">
              <Badge className="bg-gradient-to-r from-amber-500 to-orange-500 text-white text-[10px] px-2 py-0.5 shadow-sm border-0">
                <Crown className="size-3 mr-1" />
                Pro
              </Badge>
            </div>
          )}

          {/* Selection indicator dot */}
          <div
            className={`absolute top-4 right-4 size-3 rounded-full transition-all duration-300 ${
              mode === "domain"
                ? "bg-ai-brown scale-100"
                : "bg-slate-200 scale-75 group-hover:bg-ai-brown/30"
            }`}
          />

          <div className="flex items-start gap-3 sm:gap-4 pr-6">
            <div
              className={`flex size-11 sm:size-12 shrink-0 items-center justify-center rounded-full transition-all duration-300 ${
                mode === "domain"
                  ? "bg-yellow-bright shadow-md"
                  : "bg-slate-100 group-hover:bg-yellow-light"
              }`}
            >
              <Globe className="size-5 sm:size-6 text-gray-900" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-slate-900 text-sm sm:text-base">
                Launch on Your Domain
              </h3>
              <p className="text-xs sm:text-sm text-slate-600 mt-0.5">
                Host your AI clone at your own URL with full white-label
                branding. Free SSL included.
              </p>
            </div>
          </div>
        </button>

        {/* Custom Email Domain Card */}
        <button
          onClick={() => setMode("email")}
          className={`relative group text-left p-4 sm:p-5 rounded-xl border transition-all duration-300 ease-in-out ${
            mode === "email"
              ? "border-ai-brown bg-yellow-light/50 shadow-md"
              : "border-slate-200 bg-white hover:border-ai-brown/40 hover:bg-yellow-light/10 hover:shadow-sm"
          }`}
        >
          {/* Enterprise badge */}
          {!hasEmailDomainAccess && (
            <div className="absolute -top-2.5 left-4">
              <Badge className="bg-gradient-to-r from-purple-500 to-indigo-500 text-white text-[10px] px-2 py-0.5 shadow-sm border-0">
                <Crown className="size-3 mr-1" />
                Enterprise
              </Badge>
            </div>
          )}

          {/* Selection indicator dot */}
          <div
            className={`absolute top-4 right-4 size-3 rounded-full transition-all duration-300 ${
              mode === "email"
                ? "bg-ai-brown scale-100"
                : "bg-slate-200 scale-75 group-hover:bg-ai-brown/30"
            }`}
          />

          <div className="flex items-start gap-3 sm:gap-4 pr-6">
            <div
              className={`flex size-11 sm:size-12 shrink-0 items-center justify-center rounded-full transition-all duration-300 ${
                mode === "email"
                  ? "bg-yellow-bright shadow-md"
                  : "bg-slate-100 group-hover:bg-yellow-light"
              }`}
            >
              <Mail className="size-5 sm:size-6 text-gray-900" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-slate-900 text-sm sm:text-base">
                Custom Email Domain
              </h3>
              <p className="text-xs sm:text-sm text-slate-600 mt-0.5">
                Send verification emails from your own domain instead of
                myclone.is for a branded experience.
              </p>
            </div>
          </div>
        </button>
      </div>

      {/* ============================================== */}
      {/* Content based on selected mode */}
      {/* ============================================== */}
      {mode === "domain" ? (
        <CustomDomainSection />
      ) : (
        <EmailDomainsSection isEnterprise={hasEmailDomainAccess} />
      )}
    </div>
  );
}
