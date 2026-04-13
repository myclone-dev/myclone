"use client";

import React from "react";
import { PhoneOff, MessageSquare, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/i18n";

interface VoiceLimitExceededProps {
  expertName: string;
  onSwitchToText: () => void;
  /** If true, this was a mid-call disconnect due to limit */
  wasMidCall?: boolean;
  /** Widget mode removes max-width constraints */
  widgetToken?: string;
}

/**
 * Component shown when voice chat is unavailable due to owner's quota exhaustion.
 * Matches the styling of VoiceInterface for visual consistency.
 */
export function VoiceLimitExceeded({
  expertName,
  onSwitchToText,
  wasMidCall = false,
  widgetToken,
}: VoiceLimitExceededProps) {
  const { t } = useTranslation();
  const containerClass = widgetToken
    ? "relative w-full"
    : "relative w-full max-w-4xl mx-auto px-4 sm:px-0";

  return (
    <div className={containerClass}>
      <div className="flex flex-col gap-4 min-h-[500px] sm:h-[500px]">
        <div
          className="flex-1 rounded-3xl border border-gray-200/50 shadow-2xl flex items-center justify-center p-8 sm:p-12 relative overflow-hidden"
          style={{
            background:
              "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #e2e8f0 100%)",
          }}
        >
          {/* Gradient orbs for depth */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-slate-100/50 to-slate-200/40 rounded-full blur-3xl" />
          <div className="absolute bottom-0 left-0 w-56 h-56 bg-gradient-to-tr from-slate-50/50 to-yellow-50/30 rounded-full blur-3xl" />

          <div className="flex flex-col items-center justify-center space-y-6 relative z-10 text-center max-w-md">
            {/* Icon */}
            <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center">
              <PhoneOff className="w-10 h-10 text-gray-400" />
            </div>

            {/* Title */}
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-800 mb-2">
                {wasMidCall
                  ? t("voice.limitExceeded.sessionEnded")
                  : t("voice.limitExceeded.unavailable")}
              </h2>
              <p className="text-sm sm:text-base text-gray-600">
                {wasMidCall
                  ? t("voice.limitExceeded.conversationEnded", {
                      name: expertName,
                    })
                  : t("voice.limitExceeded.unavailableMessage", {
                      name: expertName,
                    })}
              </p>
            </div>

            {/* Subtitle */}
            <p className="text-sm text-gray-500">
              {wasMidCall
                ? t("voice.limitExceeded.continueWithText")
                : t("voice.limitExceeded.useTextInstead")}
            </p>

            {/* CTA Button */}
            <div className="flex flex-col gap-3 mt-2">
              <Button
                onClick={onSwitchToText}
                size="lg"
                className="rounded-full px-8 py-3 hover:opacity-90 transition-opacity flex items-center gap-2"
                style={{
                  backgroundColor: "#000000",
                  color: "#FFFFFF",
                  fontWeight: "600",
                }}
              >
                <MessageSquare className="w-5 h-5" />
                {t("voice.limitExceeded.continueWithTextButton")}
              </Button>

              <Button
                onClick={onSwitchToText}
                variant="ghost"
                size="sm"
                className="text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded-full px-6 py-2 flex items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                {t("common.goBack")}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
