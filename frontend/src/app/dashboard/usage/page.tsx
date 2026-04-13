"use client";

import {
  BarChart3,
  FileText,
  File,
  Video,
  Youtube,
  Crown,
  Phone,
  MessageSquare,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { useUserMe } from "@/lib/queries/users";
import { useUserUsage, useUserSubscription } from "@/lib/queries/tier";
import { isFreeTier } from "@/lib/constants/tiers";
import { EXTERNAL_URLS, CONTACT } from "@/lib/constants/urls";
import { PageLoader } from "@/components/ui/page-loader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TierBadge, FreeTierBanner } from "@/components/tier";

/**
 * Limits & Usage Page
 * Displays user's current usage vs tier limits with improved UI
 */
export default function UsagePage() {
  const { data: user, isLoading: userLoading } = useUserMe();
  const { data: usage, isLoading: usageLoading } = useUserUsage({
    refetchInterval: 30000, // Refresh every 30 seconds
  });
  const { data: subscription, isLoading: subscriptionLoading } =
    useUserSubscription();

  const isLoading = userLoading || usageLoading || subscriptionLoading;

  // Check if user is on free tier
  const isFree = isFreeTier(subscription?.tier_id);

  // Calculate if any limits are near or at capacity
  const hasLimitsNearCapacity =
    (usage?.documents?.files?.percentage ?? 0) >= 80 ||
    (usage?.multimedia?.files?.percentage ?? 0) >= 80 ||
    (usage?.youtube?.videos?.percentage ?? 0) >= 80 ||
    (usage?.voice?.percentage ?? 0) >= 80 ||
    (usage?.text?.percentage ?? 0) >= 80 ||
    (usage?.personas?.percentage ?? 0) >= 80;

  if (isLoading || !user || !usage || !subscription) {
    return <PageLoader />;
  }

  // Helper to format percentage with color
  const getPercentageColor = (percentage: number) => {
    if (percentage >= 90) return "text-status-danger";
    if (percentage >= 80) return "text-status-warning";
    return "text-status-default";
  };

  // Custom progress bar component with dynamic colors (slate by default, warning colors at high usage)
  const UsageProgress = ({ percentage }: { percentage: number }) => {
    const value = Math.min(percentage, 100);

    // Determine colors based on usage percentage
    const getColors = () => {
      if (percentage >= 90)
        return {
          bg: "bg-progress-danger-bg",
          bar: "bg-progress-danger-bar",
          glow: "shadow-progress-danger-glow",
        };
      if (percentage >= 80)
        return {
          bg: "bg-progress-warning-bg",
          bar: "bg-progress-warning-bar",
          glow: "shadow-progress-warning-glow",
        };
      return {
        bg: "bg-progress-default-bg",
        bar: "bg-progress-default-bar",
        glow: "",
      };
    };

    const { bg, bar, glow } = getColors();

    return (
      <div
        className={`relative h-2.5 w-full overflow-hidden rounded-full ${bg}`}
      >
        <div
          className={`h-full transition-all duration-300 ease-out ${bar} ${glow ? `shadow-sm ${glow}` : ""}`}
          style={{ width: `${value}%` }}
        />
      </div>
    );
  };

  const formatNumber = (num: number) => {
    if (num === -1) return "Unlimited";
    return num.toLocaleString();
  };

  const formatHours = (hours: number) => {
    if (hours === -1) return "Unlimited";
    return `${hours.toFixed(1)}h`;
  };

  const formatMB = (mb: number) => {
    if (mb === -1) return "Unlimited";
    if (mb >= 1000) return `${(mb / 1000).toFixed(1)} GB`;
    return `${mb.toFixed(1)} MB`;
  };

  const formatMinutes = (minutes: number) => {
    if (minutes === -1) return "Unlimited";
    return `${minutes.toFixed(1)} min`;
  };

  const formatMessages = (messages: number) => {
    if (messages === -1) return "Unlimited";
    return messages.toLocaleString();
  };

  const formatResetDate = (date: string | null) => {
    if (!date) return "N/A";
    return new Date(date).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
      {/* Free Tier Upgrade Banner */}
      {isFree && hasLimitsNearCapacity && (
        <FreeTierBanner
          title="Approaching Your Free Plan Limits"
          description="Some of your limits are reaching capacity. Upgrade to unlock higher limits and more features."
          variant="warning"
          dismissible
        />
      )}

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-12 items-center justify-center rounded-xl bg-gradient-to-br from-yellow-light to-peach-cream">
            <BarChart3 className="size-6 text-ai-brown" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              Limits & Usage
            </h1>
            <p className="text-sm text-slate-600">
              Track your current usage against your{" "}
              <span className="font-semibold capitalize">{usage.tier}</span>{" "}
              plan limits
            </p>
          </div>
        </div>

        {/* Current Plan with Upgrade Button */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-3 rounded-lg border-2 border-yellow-bright/30 bg-gradient-to-br from-yellow-light to-peach-cream px-4 py-2.5 shadow-sm">
            <TierBadge tierId={subscription.tier_id} size="md" />
          </div>
          {isFree && (
            <Button className="gap-2" variant="default" asChild>
              <a
                href={EXTERNAL_URLS.PRICING}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Sparkles className="size-4" />
                Upgrade
                <ArrowRight className="size-4" />
              </a>
            </Button>
          )}
        </div>
      </div>

      {/* Section 1: Knowledge Library Limits */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-slate-100">
            <FileText className="size-4 text-slate-600" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900">
            Knowledge Library Limits
          </h2>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Raw Text Usage */}
          <Card className="p-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-lg bg-blue-100">
                <FileText className="size-6 text-blue-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  Raw Text Files
                </h2>
                <p className="text-sm text-slate-600">
                  Twitter, LinkedIn, and website content
                </p>
              </div>
            </div>

            <div className="space-y-5">
              {/* File Count */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">File Count</span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.raw_text.files.percentage)}`}
                  >
                    {usage.raw_text.files.used} /{" "}
                    {formatNumber(usage.raw_text.files.limit)}
                    <span className="ml-1 text-xs">
                      ({usage.raw_text.files.percentage}%)
                    </span>
                  </span>
                </div>
                <UsageProgress percentage={usage.raw_text.files.percentage} />
              </div>

              {/* Storage */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Storage Used
                  </span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.raw_text.storage.percentage)}`}
                  >
                    {formatMB(usage.raw_text.storage.used_mb)} /{" "}
                    {formatMB(usage.raw_text.storage.limit_mb)}
                    <span className="ml-1 text-xs">
                      ({usage.raw_text.storage.percentage}%)
                    </span>
                  </span>
                </div>
                <UsageProgress percentage={usage.raw_text.storage.percentage} />
              </div>
            </div>
          </Card>

          {/* Documents Usage */}
          <Card className="p-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-lg bg-green-100">
                <File className="size-6 text-green-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  Document Files
                </h2>
                <p className="text-sm text-slate-600">
                  PDF, DOCX, XLSX, PPTX (Max:{" "}
                  {formatMB(usage.documents.max_file_size_mb)})
                </p>
              </div>
            </div>

            <div className="space-y-5">
              {/* File Count */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">File Count</span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.documents.files.percentage)}`}
                  >
                    {usage.documents.files.used} /{" "}
                    {formatNumber(usage.documents.files.limit)}
                    <span className="ml-1 text-xs">
                      ({usage.documents.files.percentage}%)
                    </span>
                  </span>
                </div>
                <UsageProgress percentage={usage.documents.files.percentage} />
              </div>

              {/* Storage */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Storage Used
                  </span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.documents.storage.percentage)}`}
                  >
                    {formatMB(usage.documents.storage.used_mb)} /{" "}
                    {formatMB(usage.documents.storage.limit_mb)}
                    <span className="ml-1 text-xs">
                      ({usage.documents.storage.percentage}%)
                    </span>
                  </span>
                </div>
                <UsageProgress
                  percentage={usage.documents.storage.percentage}
                />
              </div>
            </div>
          </Card>

          {/* Multimedia Usage */}
          <Card className="p-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-lg bg-purple-100">
                <Video className="size-6 text-purple-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  Audio & Video Files
                </h2>
                <p className="text-sm text-slate-600">
                  MP3, WAV, MP4 (Max:{" "}
                  {formatMB(usage.multimedia.max_file_size_mb)})
                </p>
              </div>
            </div>

            <div className="space-y-5">
              {/* File Count */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">File Count</span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.multimedia.files.percentage)}`}
                  >
                    {usage.multimedia.files.used} /{" "}
                    {formatNumber(usage.multimedia.files.limit)}
                    <span className="ml-1 text-xs">
                      ({usage.multimedia.files.percentage}%)
                    </span>
                  </span>
                </div>
                <UsageProgress percentage={usage.multimedia.files.percentage} />
              </div>

              {/* Storage */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Storage Used
                  </span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.multimedia.storage.percentage)}`}
                  >
                    {formatMB(usage.multimedia.storage.used_mb)} /{" "}
                    {formatMB(usage.multimedia.storage.limit_mb)}
                    <span className="ml-1 text-xs">
                      ({usage.multimedia.storage.percentage}%)
                    </span>
                  </span>
                </div>
                <UsageProgress
                  percentage={usage.multimedia.storage.percentage}
                />
              </div>

              {/* Duration */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Total Duration
                  </span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.multimedia.duration.percentage)}`}
                  >
                    {formatHours(usage.multimedia.duration.used_hours)} /{" "}
                    {formatHours(usage.multimedia.duration.limit_hours)}
                    <span className="ml-1 text-xs">
                      ({usage.multimedia.duration.percentage}%)
                    </span>
                  </span>
                </div>
                <UsageProgress
                  percentage={usage.multimedia.duration.percentage}
                />
                {usage.multimedia.duration.hard_limit_hours && (
                  <p className="text-xs text-slate-500">
                    Hard limit:{" "}
                    {formatHours(usage.multimedia.duration.hard_limit_hours)}
                  </p>
                )}
              </div>
            </div>
          </Card>

          {/* YouTube Usage */}
          <Card className="p-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-lg bg-red-100">
                <Youtube className="size-6 text-red-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  YouTube Videos
                </h2>
                <p className="text-sm text-slate-600">
                  Max video length: {usage.youtube.max_video_duration_minutes}{" "}
                  min
                </p>
              </div>
            </div>

            <div className="space-y-5">
              {/* Video Count */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Video Count
                  </span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.youtube.videos.percentage)}`}
                  >
                    {usage.youtube.videos.used} /{" "}
                    {formatNumber(usage.youtube.videos.limit)}
                    <span className="ml-1 text-xs">
                      ({usage.youtube.videos.percentage}%)
                    </span>
                  </span>
                </div>
                <UsageProgress percentage={usage.youtube.videos.percentage} />
                {usage.youtube.videos.hard_limit && (
                  <p className="text-xs text-slate-500">
                    Hard limit: {formatNumber(usage.youtube.videos.hard_limit)}{" "}
                    videos
                  </p>
                )}
              </div>

              {/* Total Duration */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Total Duration
                  </span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.youtube.duration.percentage)}`}
                  >
                    {formatHours(usage.youtube.duration.used_hours)} /{" "}
                    {formatHours(usage.youtube.duration.limit_hours)}
                    <span className="ml-1 text-xs">
                      ({usage.youtube.duration.percentage}%)
                    </span>
                  </span>
                </div>
                <UsageProgress percentage={usage.youtube.duration.percentage} />
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Section 2: Chat Usage (Voice & Text side by side) */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber-100 to-blue-100">
            <Phone className="size-4 text-amber-600" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900">Chat Usage</h2>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Voice Chat Usage Card */}
          <Card className="p-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-lg bg-amber-100">
                <Phone className="size-6 text-amber-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  Voice Chat
                </h2>
                <p className="text-sm text-slate-600">
                  Real-time voice conversations
                </p>
              </div>
            </div>

            <div className="space-y-5">
              {/* Monthly Minutes Used */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Monthly Minutes
                  </span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.voice.percentage)}`}
                  >
                    {formatMinutes(usage.voice.minutes_used)} /{" "}
                    {formatMinutes(usage.voice.minutes_limit)}
                    {usage.voice.minutes_limit !== -1 && (
                      <span className="ml-1 text-xs">
                        ({usage.voice.percentage}%)
                      </span>
                    )}
                  </span>
                </div>
                <UsageProgress percentage={usage.voice.percentage} />
                <p className="text-xs text-slate-500">
                  Resets: {formatResetDate(usage.voice.reset_date)}
                </p>
              </div>

              {/* Per-Persona Breakdown */}
              {usage.voice.per_persona &&
                usage.voice.per_persona.length > 0 && (
                  <div className="space-y-3 border-t border-slate-100 pt-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium text-slate-700">
                        Usage by Persona
                      </h3>
                      <span className="text-xs text-slate-500">
                        {usage.voice.per_persona.length} persona
                        {usage.voice.per_persona.length !== 1 ? "s" : ""}
                      </span>
                    </div>
                    <div className="space-y-2.5">
                      {usage.voice.per_persona.map((persona) => {
                        const personaPercentageOfLimit =
                          usage.voice.minutes_limit > 0
                            ? (persona.minutes_used /
                                usage.voice.minutes_limit) *
                              100
                            : usage.voice.minutes_limit === -1
                              ? 0
                              : 0;
                        return (
                          <div key={persona.persona_id} className="space-y-1">
                            <div className="flex items-center justify-between text-sm">
                              <span className="truncate text-slate-600">
                                {persona.display_name || persona.persona_name}
                              </span>
                              <span className="ml-2 shrink-0 font-medium text-slate-900">
                                {formatMinutes(persona.minutes_used)}
                              </span>
                            </div>
                            <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-usage-bar-bg-amber">
                              <div
                                className="h-full bg-usage-bar-amber transition-all duration-300"
                                style={{
                                  width: `${Math.min(personaPercentageOfLimit, 100)}%`,
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

              {/* No usage yet message */}
              {(!usage.voice.per_persona ||
                usage.voice.per_persona.length === 0) &&
                usage.voice.minutes_used === 0 && (
                  <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-center">
                    <p className="text-sm text-slate-500">
                      No voice chat usage yet this billing period
                    </p>
                  </div>
                )}
            </div>
          </Card>

          {/* Text Chat Usage Card */}
          <Card className="p-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-lg bg-blue-100">
                <MessageSquare className="size-6 text-blue-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  Text Chat
                </h2>
                <p className="text-sm text-slate-600">
                  Text conversations with personas
                </p>
              </div>
            </div>

            <div className="space-y-5">
              {/* Monthly Messages Used */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">
                    Monthly Messages
                  </span>
                  <span
                    className={`font-semibold ${getPercentageColor(usage.text.percentage)}`}
                  >
                    {formatMessages(usage.text.messages_used)} /{" "}
                    {formatMessages(usage.text.messages_limit)}
                    {usage.text.messages_limit !== -1 && (
                      <span className="ml-1 text-xs">
                        ({usage.text.percentage}%)
                      </span>
                    )}
                  </span>
                </div>
                <UsageProgress percentage={usage.text.percentage} />
                <p className="text-xs text-slate-500">
                  Resets: {formatResetDate(usage.text.reset_date)}
                </p>
              </div>

              {/* No usage yet message */}
              {usage.text.messages_used === 0 && (
                <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-center">
                  <p className="text-sm text-slate-500">
                    No text chat usage yet this billing period
                  </p>
                </div>
              )}

              {/* Tier-specific messaging */}
              {usage.text.messages_limit !== -1 &&
                usage.text.percentage >= 80 && (
                  <div className="rounded-lg border border-alert-warning-border bg-alert-warning-bg p-4">
                    <p className="text-sm text-alert-warning-text">
                      <span className="font-semibold">
                        Running low on messages!
                      </span>{" "}
                      Upgrade for more monthly messages.
                    </p>
                  </div>
                )}
            </div>
          </Card>
        </div>
      </div>

      {/* Info Alert */}
      <Alert className="border-yellow-bright/30 bg-yellow-light">
        <Crown className="size-4 text-ai-brown" />
        <AlertDescription className="text-sm text-slate-900">
          Usage statistics are updated in real-time. Some limits (like
          multimedia duration) have hard limits that apply across all tiers.
          Contact{" "}
          <a
            href={CONTACT.MAILTO}
            className="font-semibold text-ai-brown underline hover:text-orange-700"
          >
            {CONTACT.EMAIL}
          </a>{" "}
          to upgrade your plan if you need higher limits.
        </AlertDescription>
      </Alert>
    </div>
  );
}
