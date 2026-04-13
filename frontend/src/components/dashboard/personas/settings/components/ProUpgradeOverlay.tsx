"use client";

import {
  Sparkles,
  ArrowRight,
  Check,
  DollarSign,
  CreditCard,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EXTERNAL_URLS } from "@/lib/constants/urls";

interface ProUpgradeOverlayProps {
  title?: string;
  description?: string;
  features?: string[];
}

/**
 * Overlay component shown when free tier users try to access monetization
 * Clean, modern UI with gradient card design
 */
export function ProUpgradeOverlay({
  title = "Monetize Your AI Clone",
  description = "Unlock persona monetization and start earning revenue from your AI clone with a Pro plan or higher.",
  features = [
    "Set custom pricing for your persona",
    "Accept one-time or subscription payments",
    "Connect your Stripe account",
    "Track earnings and analytics",
  ],
}: ProUpgradeOverlayProps) {
  return (
    <div className="flex items-center justify-center min-h-[60vh] px-4">
      <div className="w-full max-w-lg">
        {/* Main Card */}
        <div className="relative overflow-hidden rounded-2xl border border-amber-200 bg-gradient-to-br from-white to-amber-50/50 shadow-lg">
          {/* Background decoration */}
          <div className="absolute -right-10 -top-10 size-40 rounded-full bg-gradient-to-br from-amber-200/30 to-orange-200/30 blur-3xl" />
          <div className="absolute -bottom-10 -left-10 size-32 rounded-full bg-gradient-to-br from-yellow-200/30 to-orange-200/30 blur-2xl" />

          <div className="relative p-8">
            {/* Icon and Badge */}
            <div className="flex items-center justify-center mb-6">
              <div className="relative">
                <div className="flex size-16 items-center justify-center rounded-2xl bg-amber-100 shadow-lg border border-amber-200">
                  <DollarSign className="size-8 text-amber-600" />
                </div>
                {/* Pro badge */}
                <div className="absolute -right-2 -top-2 flex items-center gap-1 rounded-full bg-amber-500 px-2 py-0.5 text-xs font-semibold text-white shadow-md">
                  <Sparkles className="size-3" />
                  Pro
                </div>
              </div>
            </div>

            {/* Title and Description */}
            <div className="text-center mb-6">
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                {title}
              </h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                {description}
              </p>
            </div>

            {/* Features List */}
            <div className="space-y-3 mb-8">
              {features.map((feature, index) => (
                <div
                  key={index}
                  className="flex items-center gap-3 text-sm text-gray-700"
                >
                  <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-green-100">
                    <Check className="size-3 text-green-600" />
                  </div>
                  {feature}
                </div>
              ))}
            </div>

            {/* CTA Button */}
            <Button
              className="w-full h-12 text-base font-semibold gap-2 bg-gray-900 hover:bg-gray-800 text-white shadow-md border-0"
              asChild
            >
              <a
                href={EXTERNAL_URLS.PRICING}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Sparkles className="size-4" />
                Upgrade to Pro
                <ArrowRight className="size-4" />
              </a>
            </Button>

            {/* Secondary info */}
            <p className="text-center text-xs text-gray-500 mt-4">
              Start monetizing your AI clone today
            </p>
          </div>
        </div>

        {/* Bottom highlights */}
        <div className="flex justify-center gap-6 mt-6">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <CreditCard className="size-3.5" />
            Secure Stripe payments
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <TrendingUp className="size-3.5" />
            Real-time analytics
          </div>
        </div>
      </div>
    </div>
  );
}
