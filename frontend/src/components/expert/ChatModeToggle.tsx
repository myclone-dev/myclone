"use client";

import { Mic, MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";

interface ChatModeToggleProps {
  isVoiceMode: boolean;
  onToggle: (isVoice: boolean) => void;
}

export function ChatModeToggle({ isVoiceMode, onToggle }: ChatModeToggleProps) {
  const { t } = useTranslation();
  return (
    <div className="flex justify-center mb-6">
      <div className="relative inline-flex rounded-full border border-gray-300/50 bg-white/80 backdrop-blur-sm p-1 shadow-sm">
        {/* Sliding Background */}
        <div
          className={`absolute top-1 bottom-1 bg-ai-gold rounded-full shadow-md transition-all duration-300 ease-in-out ${
            isVoiceMode ? "left-1 right-[50%]" : "left-[50%] right-1"
          }`}
        />
        <button
          onClick={() => onToggle(true)}
          className={`relative z-10 flex items-center gap-2 px-6 py-2.5 rounded-full transition-all duration-200 whitespace-nowrap ${
            isVoiceMode ? "text-gray-900" : "text-gray-700 hover:text-gray-900"
          }`}
        >
          <Mic className="w-4 h-4 flex-shrink-0" />
          <span className="font-medium text-sm">
            {t("chat.modeToggle.voice")}
          </span>
        </button>
        <button
          onClick={() => onToggle(false)}
          className={`relative z-10 flex items-center gap-2 px-6 py-2.5 rounded-full transition-all duration-200 whitespace-nowrap ${
            !isVoiceMode ? "text-gray-900" : "text-gray-700 hover:text-gray-900"
          }`}
        >
          <MessageSquare className="w-4 h-4 flex-shrink-0" />
          <span className="font-medium text-sm">
            {t("chat.modeToggle.text")}
          </span>
        </button>
      </div>
    </div>
  );
}
