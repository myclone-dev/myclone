"use client";

import { useUserMe } from "@/lib/queries/users";
import { useJobPolling } from "@/lib/queries/knowledge";
import { KnowledgeSourceGrid } from "@/components/dashboard/knowledge/KnowledgeSourceGrid";
import { RecentImports } from "@/components/dashboard/knowledge/RecentImports";
import { KnowledgeLibraryView } from "@/components/dashboard/knowledge/KnowledgeLibraryView";
import { PageLoader } from "@/components/ui/page-loader";
import { toast } from "sonner";
import type { ScrapingJob } from "@/lib/queries/knowledge";
import { isOnboardingInProgress } from "@/lib/utils/onboardingProgress";
import { useUserSubscription, useUserUsage } from "@/lib/queries/tier";
import { isFreeTier } from "@/lib/constants/tiers";
import { FreeTierBanner } from "@/components/tier";
import { useTour } from "@/hooks/useTour";
import { TOUR_KEYS } from "@/config/tour-keys";

/**
 * Knowledge Library Page with Smart Polling Updates
 */
export default function KnowledgeLibraryPage() {
  const { data: user, isLoading } = useUserMe();
  const { data: subscription } = useUserSubscription();
  const { data: usage } = useUserUsage();

  // Auto-start knowledge tour with cleanup on unmount
  useTour({
    tourName: "onboarding-knowledge",
    storageKey: TOUR_KEYS.KNOWLEDGE_TOUR,
    shouldStart: () => isOnboardingInProgress(),
    dependencies: [user, isLoading],
  });

  // Check if user is on free tier
  const isFree = isFreeTier(subscription?.tier_id);

  // Calculate total knowledge sources usage from backend data
  const totalSourcesUsed =
    (usage?.documents?.files?.used || 0) +
    (usage?.multimedia?.files?.used || 0) +
    (usage?.youtube?.videos?.used || 0);

  // Calculate total limit from backend-provided limits
  const getTotalSourcesLimit = () => {
    if (!usage) return 0;
    const docLimit = usage.documents?.files?.limit ?? 0;
    const mediaLimit = usage.multimedia?.files?.limit ?? 0;
    const ytLimit = usage.youtube?.videos?.limit ?? 0;

    // If any limit is -1 (unlimited), return -1
    if (docLimit === -1 || mediaLimit === -1 || ytLimit === -1) return -1;
    return docLimit + mediaLimit + ytLimit;
  };
  const totalSourcesLimit = getTotalSourcesLimit();

  // Use smart polling hook that automatically stops when no active jobs
  const { jobs, hasActiveJobs, isPolling } = useJobPolling({
    userId: user?.id || "",
    enabled: !!user?.id,
    pollingInterval: 5000, // Poll every 5 seconds
    onJobCompleted: (job: ScrapingJob) => {
      const sourceLabel = getSourceLabel(job.source_type);
      const stats = getJobStats(job);

      toast.success(`${sourceLabel} import completed!`, {
        description: stats,
        duration: 5000,
      });
    },
    onJobFailed: (job: ScrapingJob) => {
      const sourceLabel = getSourceLabel(job.source_type);

      toast.error(`${sourceLabel} import failed`, {
        description: job.error_message || "An error occurred",
        duration: 7000,
      });
    },
  });

  if (isLoading || !user) {
    return <PageLoader />;
  }

  return (
    <div className="min-h-screen w-full">
      <div className="max-w-7xl mx-auto py-4 sm:py-8 px-4 sm:px-6 lg:px-8 space-y-4 sm:space-y-8">
        {/* Free Tier Banner */}
        {isFree && (
          <FreeTierBanner
            title="Free Plan Limits"
            description="You have limited storage and file uploads on the free plan."
            variant="compact"
            limitInfo={
              totalSourcesLimit > 0
                ? {
                    current: totalSourcesUsed,
                    max: totalSourcesLimit,
                    unit: "sources",
                  }
                : undefined
            }
          />
        )}

        {/* Header Section - More compact on mobile */}
        <div className="space-y-3 sm:space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1 sm:space-y-2 min-w-0">
              <div className="flex items-center gap-2 sm:gap-3">
                <div className="p-1.5 sm:p-2 rounded-lg sm:rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 border border-primary/20 shrink-0">
                  <svg
                    className="size-5 sm:size-6 text-primary"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                    />
                  </svg>
                </div>
                <div className="min-w-0">
                  <h1 className="text-xl sm:text-3xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">
                    Knowledge Library
                  </h1>
                  <p className="text-xs sm:text-base text-muted-foreground mt-0.5 sm:mt-1 line-clamp-2">
                    Connect your data sources to build your AI clone&apos;s
                    knowledge base
                  </p>
                </div>
              </div>
            </div>

            {/* Polling Status Indicator */}
            {hasActiveJobs && isPolling && (
              <div className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1 sm:py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 shrink-0">
                <span className="relative flex size-1.5 sm:size-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full size-1.5 sm:size-2 bg-emerald-500"></span>
                </span>
                <span className="text-[10px] sm:text-xs font-medium">Live</span>
              </div>
            )}
          </div>

          {/* Knowledge Library Stats - Collapsible on mobile */}
          <KnowledgeLibraryView userId={user.id} />
        </div>

        {/* Main Content - Reordered for mobile: Add Sources first */}
        <div className="space-y-4 sm:space-y-8">
          {/* Add Data Sources - Prominent section */}
          <div id="knowledge-source-grid">
            <h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4 flex items-center gap-2">
              <span className="inline-block size-1.5 rounded-full bg-primary" />
              Add Data Sources
            </h2>
            <KnowledgeSourceGrid userId={user.id} jobs={jobs} />
          </div>

          {/* Recent Activity - Below Add Sources */}
          <RecentImports jobs={jobs} />
        </div>
      </div>
    </div>
  );
}

function getSourceLabel(type: string): string {
  const labels: Record<string, string> = {
    linkedin: "LinkedIn",
    twitter: "Twitter",
    website: "Website",
    pdf: "Document",
    docx: "Word Document",
    pptx: "PowerPoint Presentation",
    xlsx: "Excel Spreadsheet",
    audio: "Audio",
    video: "Video",
  };
  return labels[type] || type;
}

function getJobStats(job: ScrapingJob): string {
  const parts: string[] = [];
  if (job.records_imported > 0) parts.push(`${job.records_imported} records`);
  if (job.posts_imported > 0) parts.push(`${job.posts_imported} posts`);
  if (job.pages_imported > 0) parts.push(`${job.pages_imported} pages`);
  return parts.length > 0 ? parts.join(", ") : "Processed successfully";
}
