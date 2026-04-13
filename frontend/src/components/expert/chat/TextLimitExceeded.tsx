"use client";

import React from "react";
import { MessageSquareOff, Phone, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/i18n";

interface TextLimitExceededProps {
  expertName: string;
  messagesUsed?: number;
  messagesLimit?: number;
  onSwitchToVoice?: () => void;
  onGoBack?: () => void;
  /** If voice is available as an alternative */
  voiceAvailable?: boolean;
}

/**
 * Component shown when text chat is unavailable due to owner's quota exhaustion.
 * Matches the styling of chat interface for visual consistency.
 */
export function TextLimitExceeded({
  expertName,
  messagesUsed,
  messagesLimit,
  onSwitchToVoice,
  onGoBack,
  voiceAvailable = false,
}: TextLimitExceededProps) {
  const { t } = useTranslation();

  return (
    <div className="relative w-full h-full">
      <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 p-8 sm:p-12">
        <div className="flex max-w-md flex-col items-center justify-center space-y-6 text-center">
          {/* Icon */}
          <div className="flex size-20 items-center justify-center rounded-full bg-orange-50">
            <MessageSquareOff className="size-10 text-orange-400" />
          </div>

          {/* Title */}
          <div>
            <h2 className="mb-2 text-2xl font-bold text-gray-800 sm:text-3xl">
              {t("textLimit.title")}
            </h2>
            <p className="text-sm text-gray-600 sm:text-base">
              {t("textLimit.quotaReached", { name: expertName })}
            </p>
          </div>

          {/* Usage info */}
          {messagesLimit && messagesLimit > 0 && (
            <div className="flex items-center gap-2 rounded-lg bg-orange-50 px-4 py-2">
              <span className="text-sm font-medium text-orange-700">
                {t("textLimit.usageInfo", {
                  used: messagesUsed?.toLocaleString() ?? 0,
                  limit: messagesLimit.toLocaleString(),
                })}
              </span>
            </div>
          )}

          {/* Subtitle */}
          <p className="text-sm text-gray-500">
            {voiceAvailable
              ? t("textLimit.continueWithVoice")
              : t("textLimit.tryAgainLater")}
          </p>

          {/* CTA Buttons */}
          <div className="mt-2 flex flex-col gap-3">
            {voiceAvailable && onSwitchToVoice && (
              <Button
                onClick={onSwitchToVoice}
                size="lg"
                className="flex items-center gap-2 rounded-full px-8 py-3 transition-opacity hover:opacity-90"
                style={{
                  backgroundColor: "#000000",
                  color: "#FFFFFF",
                  fontWeight: "600",
                }}
              >
                <Phone className="size-5" />
                {t("textLimit.continueWithVoiceButton")}
              </Button>
            )}

            {onGoBack && (
              <Button
                onClick={onGoBack}
                variant="ghost"
                size="sm"
                className="flex items-center gap-2 rounded-full px-6 py-2 text-gray-500 hover:bg-gray-50 hover:text-gray-700"
              >
                <ArrowLeft className="size-4" />
                {t("common.goBack")}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
