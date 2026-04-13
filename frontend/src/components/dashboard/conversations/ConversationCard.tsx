"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  User,
  ChevronRight,
  Clock,
  Mail,
  Phone as PhoneIcon,
  Sparkles,
  Timer,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn, decodeHtmlEntities } from "@/lib/utils";
import { useConversationSummary } from "@/lib/queries/conversations";
import { ConversationSummaryCard } from "./ConversationSummaryCard";
import type { ConversationSummary } from "@/lib/queries/conversations";

interface ConversationCardProps {
  conversation: ConversationSummary;
  isFirstCard?: boolean;
}

/**
 * ConversationCard Component
 * Individual conversation card with optional AI summary display
 */
export function ConversationCard({
  conversation,
  isFirstCard = false,
}: ConversationCardProps) {
  const router = useRouter();
  const [showSummary, setShowSummary] = useState(false);

  // Fetch summary only when user requests it
  // Auth is handled via cookies (myclone_token)
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
  } = useConversationSummary(showSummary ? conversation.id : null, {
    enabled: showSummary,
  });

  const isVoice = conversation.conversation_type === "voice";

  // Format voice duration for display
  const formatVoiceDuration = (seconds: number | undefined) => {
    if (!seconds || seconds <= 0) return null;
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins >= 60) {
      const hours = Math.floor(mins / 60);
      const remainingMins = mins % 60;
      return `${hours}h ${remainingMins}m`;
    }
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  };

  const voiceDuration = formatVoiceDuration(
    conversation.voice_duration_seconds,
  );

  const handleCardClick = () => {
    if (!showSummary) {
      router.push(`/dashboard/conversations/${conversation.id}`);
    }
  };

  const handleSummaryToggle = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click when toggling summary
    const newState = !showSummary;
    console.log("[ConversationCard] Summary button clicked:", {
      conversationId: conversation.id,
      currentState: showSummary,
      newState,
    });
    setShowSummary(newState);
  };

  return (
    <Card
      className={cn(
        "group relative p-4 transition-all sm:p-5",
        !showSummary &&
          "cursor-pointer hover:shadow-md hover:border-primary/20",
      )}
    >
      <div onClick={handleCardClick}>
        <div className="flex items-start gap-3 sm:gap-4">
          {/* User Avatar */}
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 sm:size-12">
            <User className="size-5 text-primary sm:size-6" />
          </div>

          {/* Content */}
          <div className="min-w-0 flex-1">
            {/* Header Row - Name */}
            <div className="mb-1 flex items-center gap-1.5 sm:mb-1.5 sm:gap-2">
              <User className="size-3 text-muted-foreground sm:size-3.5 shrink-0" />
              <span className="truncate text-xs font-semibold text-foreground sm:text-sm">
                {conversation.user_fullname ||
                  conversation.user_email ||
                  "Anonymous Visitor"}
              </span>
            </div>

            {/* Email/Phone Row - Separate row on mobile for better truncation */}
            {(conversation.user_email && conversation.user_fullname) ||
            conversation.user_phone ? (
              <div className="mb-1.5 flex items-center gap-1.5 sm:gap-2 overflow-hidden">
                {conversation.user_email && conversation.user_fullname && (
                  <div className="flex items-center gap-1 min-w-0 max-w-[150px] sm:max-w-none">
                    <Mail className="size-3 text-muted-foreground shrink-0" />
                    <span className="truncate text-[10px] sm:text-xs text-muted-foreground">
                      {conversation.user_email}
                    </span>
                  </div>
                )}
                {conversation.user_phone && (
                  <>
                    {conversation.user_email && conversation.user_fullname && (
                      <span className="text-[10px] sm:text-xs text-muted-foreground shrink-0">
                        •
                      </span>
                    )}
                    <div className="flex items-center gap-1 min-w-0">
                      <PhoneIcon className="size-3 text-muted-foreground shrink-0" />
                      <span className="truncate text-[10px] sm:text-xs text-muted-foreground">
                        {conversation.user_phone}
                      </span>
                    </div>
                  </>
                )}
              </div>
            ) : null}

            {/* Badges Row */}
            <div className="mb-2 flex flex-wrap items-center gap-1.5 sm:mb-2.5 sm:gap-2">
              <Badge
                variant={isVoice ? "default" : "secondary"}
                className="text-xs font-medium"
              >
                {conversation.conversation_type}
              </Badge>
              {/* Voice duration badge - shown next to voice type badge */}
              {isVoice && voiceDuration && (
                <Badge
                  variant="outline"
                  className="flex items-center gap-1 border-voice-duration-border bg-voice-duration-bg text-xs text-voice-duration-text"
                >
                  <Timer className="size-3" aria-hidden="true" />
                  {voiceDuration}
                </Badge>
              )}
              <Badge variant="outline" className="text-xs">
                {conversation.message_count}{" "}
                {conversation.message_count === 1 ? "message" : "messages"}
              </Badge>
            </div>

            {/* Last Message Preview */}
            {conversation.last_message_preview && (
              <p className="mb-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground sm:mb-2.5 sm:text-sm">
                {decodeHtmlEntities(conversation.last_message_preview)}
              </p>
            )}

            {/* Timestamp */}
            <div className="flex items-center gap-1 text-xs text-muted-foreground sm:gap-1.5">
              <Clock className="size-3 sm:size-3.5" />
              <span className="truncate">
                {new Date(
                  conversation.updated_at || conversation.created_at,
                ).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex shrink-0 flex-col items-end gap-1.5 sm:gap-2">
            {/* Summary Chip - Shows "Summary" or "Hide" - Larger touch target on mobile */}
            <button
              id={isFirstCard ? "conversation-summary-button" : undefined}
              onClick={handleSummaryToggle}
              className={cn(
                "group/chip relative flex items-center gap-1 overflow-hidden rounded-full bg-gradient-to-r font-semibold text-foreground transition-all",
                "h-7 px-2.5 text-[11px] sm:h-6 sm:px-2.5 sm:text-xs",
                "min-w-[72px] justify-center",
                showSummary
                  ? "from-ai-gold/80 to-ai-amber/80 shadow-md hover:shadow-lg"
                  : "from-ai-gold/60 to-ai-amber/60 hover:from-ai-gold/70 hover:to-ai-amber/70",
              )}
            >
              <Sparkles className="size-3 transition-transform group-hover/chip:rotate-12" />
              <span>{showSummary ? "Hide" : "Summary"}</span>
              {/* Shimmer effect */}
              {!showSummary && (
                <div
                  className="pointer-events-none absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent opacity-0 transition-opacity group-hover/chip:opacity-100"
                  style={{
                    animation: "ai-shimmer 2s ease-in-out infinite",
                    backgroundSize: "200% 100%",
                  }}
                />
              )}
            </button>

            {/* Arrow Indicator - Larger touch target on mobile */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                router.push(`/dashboard/conversations/${conversation.id}`);
              }}
              className="flex items-center justify-center text-muted-foreground transition-transform hover:translate-x-0.5 h-7 w-7 sm:h-auto sm:w-auto"
            >
              <ChevronRight className="size-5 sm:size-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Summary Section - Rendered below the card content */}
      {showSummary && (
        <div className="mt-3 sm:mt-4">
          <ConversationSummaryCard
            summary={summary || null}
            isLoading={summaryLoading}
            error={summaryError}
            defaultExpanded={true}
          />
        </div>
      )}
    </Card>
  );
}
