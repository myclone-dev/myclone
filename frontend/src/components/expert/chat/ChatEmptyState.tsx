"use client";

import { AlertCircle } from "lucide-react";
import { useTranslation } from "@/i18n";

interface ChatEmptyStateProps {
  expertName: string;
  avatarUrl?: string;
  error?: string | null;
}

export function ChatEmptyState({
  expertName: _expertName,
  avatarUrl: _avatarUrl,
  error,
}: ChatEmptyStateProps) {
  const { t } = useTranslation();

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-4">
        <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mb-4">
          <AlertCircle className="w-8 h-8 text-red-600" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          {t("chat.emptyState.connectionError")}
        </h3>
        <p className="text-gray-600 text-sm max-w-md mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-gradient-to-r from-amber-400 to-orange-500 hover:from-amber-500 hover:to-orange-600 text-white text-sm font-medium rounded-lg transition-all shadow-sm"
        >
          {t("chat.emptyState.retryConnection")}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center text-center px-4 pt-12 pb-4">
      <h3 className="text-2xl font-semibold text-gray-900 mb-3">
        {t("chat.emptyState.title")}
      </h3>
      <p className="text-gray-600 text-base max-w-lg mb-6">
        {t("chat.emptyState.subtitle")}
      </p>
      {/* Suggested Questions could go here */}
    </div>
  );
}
