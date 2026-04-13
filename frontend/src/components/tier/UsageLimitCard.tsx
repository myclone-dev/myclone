"use client";

import { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { isUnlimited } from "@/lib/constants/tiers";
import { cn } from "@/lib/utils";

interface UsageLimitCardProps {
  /** Title of the usage category */
  title: string;
  /** Description of what this limit covers */
  description?: string;
  /** Icon to display */
  icon?: ReactNode;
  /** Current usage value */
  used: number;
  /** Maximum limit (-1 for unlimited) */
  limit: number;
  /** Unit label (e.g., "files", "MB", "minutes") */
  unit: string;
  /** Whether to show upgrade CTA */
  showUpgrade?: boolean;
  /** Callback when upgrade is clicked */
  onUpgrade?: () => void;
  /** Additional class name */
  className?: string;
  /** Color theme */
  colorTheme?: "default" | "blue" | "green" | "purple" | "orange" | "red";
}

/**
 * Card component to display a usage limit with progress bar
 */
export function UsageLimitCard({
  title,
  description,
  icon,
  used,
  limit,
  unit,
  showUpgrade = true,
  onUpgrade,
  className,
  colorTheme = "default",
}: UsageLimitCardProps) {
  const unlimited = isUnlimited(limit);
  const percentage = unlimited ? 0 : Math.min((used / limit) * 100, 100);
  const isAtLimit = !unlimited && used >= limit;
  const isNearLimit = !unlimited && percentage >= 80;

  // Color themes
  const themes = {
    default: {
      icon: "bg-slate-100 text-slate-600",
      progress: "bg-slate-600",
      text: "text-slate-600",
    },
    blue: {
      icon: "bg-blue-100 text-blue-600",
      progress: "bg-blue-600",
      text: "text-blue-600",
    },
    green: {
      icon: "bg-green-100 text-green-600",
      progress: "bg-green-600",
      text: "text-green-600",
    },
    purple: {
      icon: "bg-purple-100 text-purple-600",
      progress: "bg-purple-600",
      text: "text-purple-600",
    },
    orange: {
      icon: "bg-orange-100 text-orange-600",
      progress: "bg-orange-600",
      text: "text-orange-600",
    },
    red: {
      icon: "bg-red-100 text-red-600",
      progress: "bg-red-600",
      text: "text-red-600",
    },
  };

  const theme = themes[colorTheme];

  // Status colors override theme when at/near limit
  const statusColor = isAtLimit
    ? "text-red-600"
    : isNearLimit
      ? "text-orange-600"
      : theme.text;

  const progressColor = isAtLimit
    ? "bg-red-600"
    : isNearLimit
      ? "bg-orange-600"
      : theme.progress;

  const formatValue = (value: number): string => {
    if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}k`;
    }
    return value.toString();
  };

  return (
    <Card className={cn("relative", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            {icon && (
              <div
                className={cn(
                  "flex size-10 items-center justify-center rounded-lg",
                  theme.icon,
                )}
              >
                {icon}
              </div>
            )}
            <div>
              <CardTitle className="text-base font-semibold">{title}</CardTitle>
              {description && (
                <p className="text-sm text-muted-foreground">{description}</p>
              )}
            </div>
          </div>

          {/* Status badge */}
          {isAtLimit ? (
            <Badge variant="destructive" className="gap-1">
              <XCircle className="size-3" />
              Limit Reached
            </Badge>
          ) : isNearLimit ? (
            <Badge
              variant="outline"
              className="gap-1 border-orange-200 bg-orange-50 text-orange-700"
            >
              <AlertTriangle className="size-3" />
              Near Limit
            </Badge>
          ) : unlimited ? (
            <Badge
              variant="outline"
              className="gap-1 border-green-200 bg-green-50 text-green-700"
            >
              <CheckCircle2 className="size-3" />
              Unlimited
            </Badge>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Usage</span>
            <span className={cn("font-semibold", statusColor)}>
              {formatValue(used)} /{" "}
              {unlimited ? "Unlimited" : formatValue(limit)} {unit}
            </span>
          </div>

          {!unlimited && (
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className={cn(
                  "h-full transition-all duration-500 ease-out",
                  progressColor,
                )}
                style={{ width: `${percentage}%` }}
              />
            </div>
          )}

          {unlimited && (
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-green-100">
              <div className="h-full w-full bg-green-500" />
            </div>
          )}
        </div>

        {/* Upgrade CTA when at or near limit */}
        {showUpgrade && (isAtLimit || isNearLimit) && (
          <div
            className={cn(
              "flex items-center justify-between rounded-lg p-3",
              isAtLimit ? "bg-red-50" : "bg-orange-50",
            )}
          >
            <p
              className={cn(
                "text-sm font-medium",
                isAtLimit ? "text-red-800" : "text-orange-800",
              )}
            >
              {isAtLimit
                ? "Upgrade to continue using this feature"
                : "Upgrade for higher limits"}
            </p>
            <Button
              size="sm"
              variant={isAtLimit ? "destructive" : "default"}
              onClick={
                onUpgrade ||
                (() => window.open("/pricing", "_blank"))
              }
            >
              Upgrade
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
