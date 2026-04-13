"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Sparkles, Tag, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { SentimentBadge } from "./SentimentBadge";
import type { ConversationSummaryResult } from "@/lib/queries/conversations";

interface ConversationSummaryCardProps {
  summary: ConversationSummaryResult | null;
  isLoading: boolean;
  error: Error | null;
  defaultExpanded?: boolean;
  className?: string;
}

/**
 * ConversationSummaryCard Component
 * Displays AI-generated conversation summary with collapsible design
 *
 * Features:
 * - Collapsible/expandable with smooth animation
 * - Summary text with proper formatting
 * - Key topics as interactive tags
 * - Sentiment analysis badge
 * - Loading and error states
 * - Responsive design (mobile, tablet, desktop)
 */
export function ConversationSummaryCard({
  summary,
  isLoading,
  error,
  defaultExpanded = false,
  className,
}: ConversationSummaryCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Parse key topics (comma-separated string to array)
  const topics = summary?.key_topics
    ? summary.key_topics
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean)
    : [];

  // Loading state
  if (isLoading) {
    return (
      <div
        className={cn(
          "rounded-lg border border-primary/20 bg-yellow-light/30 p-3 sm:p-4",
          className,
        )}
      >
        <div className="flex items-center gap-2">
          <Loader2 className="size-4 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">
            Generating AI summary...
          </span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className={cn(
          "rounded-lg border border-red-200 bg-red-50 p-3 sm:p-4",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 size-4 shrink-0 text-red-500" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-red-900">
              Failed to generate summary
            </p>
            <p className="mt-1 text-xs text-red-700">
              {error.message || "An error occurred"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // No summary available
  if (!summary) {
    return null;
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-primary/20 bg-yellow-light/30 transition-all",
        className,
      )}
    >
      {/* Header - Always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between gap-3 p-3 text-left transition-colors hover:bg-yellow-light/50 sm:p-4"
      >
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Sparkles className="size-4 shrink-0 text-primary sm:size-5" />
          <span className="truncate text-sm font-medium text-foreground sm:text-base">
            AI Summary
          </span>
          <SentimentBadge sentiment={summary.sentiment} size="sm" />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {!isExpanded && (
            <span className="hidden text-xs text-muted-foreground sm:inline">
              Show details
            </span>
          )}
          {isExpanded ? (
            <ChevronUp className="size-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Expanded Content - Collapsible */}
      {isExpanded && (
        <div className="space-y-3 border-t border-primary/10 p-3 sm:space-y-4 sm:p-4">
          {/* Summary Text */}
          <div>
            <p className="text-sm leading-relaxed text-foreground sm:text-base">
              {summary.summary}
            </p>
          </div>

          {/* Key Topics */}
          {topics.length > 0 && (
            <div>
              <div className="mb-2 flex items-center gap-1.5">
                <Tag className="size-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground sm:text-sm">
                  Key Topics
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 sm:gap-2">
                {topics.map((topic, index) => (
                  <Badge
                    key={index}
                    variant="secondary"
                    className="bg-white text-xs font-normal text-foreground hover:bg-white/80"
                  >
                    {topic}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Metadata Footer */}
          <div className="flex flex-wrap items-center gap-2 border-t border-primary/10 pt-3 text-xs text-muted-foreground sm:gap-3">
            <div className="flex items-center gap-1">
              <span className="font-medium">Type:</span>
              <Badge variant="outline" className="h-5 text-xs">
                {summary.conversation_type}
              </Badge>
            </div>
            <div className="flex items-center gap-1">
              <span className="font-medium">Messages:</span>
              <span>{summary.message_count}</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="font-medium">Generated:</span>
              <span>
                {new Date(summary.generated_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </span>
            </div>
          </div>

          {/* Collapse Button for mobile */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(false)}
            className="text-xs text-muted-foreground hover:text-foreground sm:hidden"
          >
            <ChevronUp className="mr-1 size-3" />
            Hide
          </Button>
        </div>
      )}
    </div>
  );
}
