"use client";

import { useState } from "react";
import { Code2, Key, Palette, ExternalLink } from "lucide-react";
import { useUserMe } from "@/lib/queries/users";
import { PageLoader } from "@/components/ui/page-loader";
import { Card } from "@/components/ui/card";
import { UnifiedWidgetCustomizer } from "@/components/dashboard/widgets/UnifiedWidgetCustomizer";
import { WidgetTokenSection } from "@/components/dashboard/widgets/WidgetTokenSection";
import { env } from "@/env";

type WidgetTab = "customize" | "tokens";

/**
 * Widgets Page
 * Embed widgets on any website with customization options
 */
export default function WidgetsPage() {
  const [activeTab, setActiveTab] = useState<WidgetTab>("customize");
  const { data: user, isLoading: isLoadingUser } = useUserMe();

  if (isLoadingUser || !user) {
    return <PageLoader />;
  }

  const username = user.username || "";

  // Use NEXT_PUBLIC_APP_URL for profile base URL
  const profileBaseUrl = env.NEXT_PUBLIC_APP_URL;
  const profileUrl = `${profileBaseUrl}/${username}`;
  // Extract display domain from URL (remove protocol)
  const displayDomain = profileBaseUrl.replace(/^https?:\/\//, "");

  return (
    <div className="max-w-7xl mx-auto py-4 space-y-6 px-4 sm:py-8 sm:space-y-8 sm:px-6 lg:px-8">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="flex size-10 sm:size-12 items-center justify-center rounded-full bg-yellow-bright shrink-0">
            <Code2 className="size-5 sm:size-6 text-gray-900" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-slate-900 sm:text-2xl">
              Embed Widget
            </h1>
            <p className="text-xs text-slate-600 sm:text-sm">
              Add a chat widget to any existing website
            </p>
          </div>
        </div>

        {/* Public Profile Link */}
        <a
          href={profileUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm text-gray-700 hover:text-gray-900 transition-colors bg-slate-100 hover:bg-yellow-light px-3 py-1.5 rounded-lg"
        >
          <span className="font-medium">
            {displayDomain}/{username}
          </span>
          <ExternalLink className="size-3.5" />
        </a>
      </div>

      {/* Widget Management Card */}
      <Card className="p-4 sm:p-6">
        {/* Sliding Tab Toggle - 2 tabs */}
        <div className="flex justify-center mb-6">
          <div className="inline-flex rounded-full border border-gray-200 bg-gray-50 p-1 gap-1">
            <button
              onClick={() => setActiveTab("customize")}
              className={`flex items-center gap-1.5 px-4 sm:px-5 py-2 rounded-full transition-all duration-200 whitespace-nowrap ${
                activeTab === "customize"
                  ? "bg-ai-gold text-gray-900 shadow-md"
                  : "text-gray-600 hover:text-gray-900 hover:bg-yellow-light/50"
              }`}
            >
              <Palette className="size-3.5 sm:size-4" />
              <span className="text-xs sm:text-sm font-medium">
                Customize Widget
              </span>
            </button>
            <button
              onClick={() => setActiveTab("tokens")}
              className={`flex items-center gap-1.5 px-4 sm:px-5 py-2 rounded-full transition-all duration-200 whitespace-nowrap ${
                activeTab === "tokens"
                  ? "bg-ai-gold text-gray-900 shadow-md"
                  : "text-gray-600 hover:text-gray-900 hover:bg-yellow-light/50"
              }`}
            >
              <Key className="size-3.5 sm:size-4" />
              <span className="text-xs sm:text-sm font-medium">API Tokens</span>
            </button>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === "customize" && (
          <UnifiedWidgetCustomizer username={username} />
        )}
        {activeTab === "tokens" && <WidgetTokenSection />}
      </Card>
    </div>
  );
}
