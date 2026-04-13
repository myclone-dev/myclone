"use client";

import { Smile, Meh, Frown, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ConversationSentiment } from "@/lib/queries/conversations";

interface SentimentBadgeProps {
  sentiment: ConversationSentiment;
  size?: "sm" | "md" | "lg";
  showIcon?: boolean;
  className?: string;
}

const sentimentConfig = {
  positive: {
    label: "Positive",
    icon: Smile,
    colorClass: "bg-sentiment-positive-light text-sentiment-positive",
    borderClass: "border-sentiment-positive/20",
  },
  neutral: {
    label: "Neutral",
    icon: Meh,
    colorClass: "bg-sentiment-neutral-light text-sentiment-neutral",
    borderClass: "border-sentiment-neutral/20",
  },
  negative: {
    label: "Negative",
    icon: Frown,
    colorClass: "bg-sentiment-negative-light text-sentiment-negative",
    borderClass: "border-sentiment-negative/20",
  },
  mixed: {
    label: "Mixed",
    icon: TrendingUp,
    colorClass: "bg-sentiment-mixed-light text-sentiment-mixed",
    borderClass: "border-sentiment-mixed/20",
  },
} as const;

const sizeConfig = {
  sm: {
    badge: "text-xs px-2 py-0.5 h-5",
    icon: "size-3",
  },
  md: {
    badge: "text-sm px-2.5 py-1 h-6",
    icon: "size-3.5",
  },
  lg: {
    badge: "text-sm px-3 py-1.5 h-7",
    icon: "size-4",
  },
} as const;

/**
 * SentimentBadge Component
 * Displays sentiment analysis result with color-coded badge and optional icon
 */
export function SentimentBadge({
  sentiment,
  size = "md",
  showIcon = true,
  className,
}: SentimentBadgeProps) {
  const config = sentimentConfig[sentiment];
  const sizes = sizeConfig[size];
  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      className={cn(
        "font-medium transition-colors",
        config.colorClass,
        config.borderClass,
        sizes.badge,
        showIcon && "gap-1",
        className,
      )}
    >
      {showIcon && <Icon className={sizes.icon} />}
      <span>{config.label}</span>
    </Badge>
  );
}
