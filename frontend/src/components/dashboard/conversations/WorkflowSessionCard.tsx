"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Target,
  User,
  Mail,
  Phone,
  FileText,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  Loader2,
  Flame,
  Thermometer,
  Snowflake,
  Clock,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type {
  WorkflowSession,
  LeadEvaluationResult,
} from "@/lib/queries/workflows";
import { isLeadEvaluationResult } from "@/lib/queries/workflows";

interface WorkflowSessionCardProps {
  session: WorkflowSession | null;
  isLoading: boolean;
  error: Error | null;
  defaultExpanded?: boolean;
  className?: string;
}

/**
 * Get color classes based on lead quality
 */
function getLeadQualityStyles(quality: LeadEvaluationResult["lead_quality"]) {
  switch (quality) {
    case "hot":
      return {
        bg: "bg-red-50",
        border: "border-red-200",
        text: "text-red-700",
        icon: Flame,
        iconColor: "text-red-500",
      };
    case "warm":
      return {
        bg: "bg-orange-50",
        border: "border-orange-200",
        text: "text-orange-700",
        icon: Thermometer,
        iconColor: "text-orange-500",
      };
    case "cold":
      return {
        bg: "bg-blue-50",
        border: "border-blue-200",
        text: "text-blue-700",
        icon: Snowflake,
        iconColor: "text-blue-500",
      };
  }
}

/**
 * Get color classes based on priority level
 */
function getPriorityStyles(priority: LeadEvaluationResult["priority_level"]) {
  switch (priority) {
    case "high":
      return { bg: "bg-red-100", text: "text-red-800" };
    case "medium":
      return { bg: "bg-yellow-100", text: "text-yellow-800" };
    case "low":
      return { bg: "bg-gray-100", text: "text-gray-800" };
  }
}

/**
 * Get color for lead score
 */
function getScoreColor(score: number) {
  if (score >= 70) return "text-green-600";
  if (score >= 40) return "text-yellow-600";
  return "text-red-600";
}

/**
 * Get progress bar color
 */
function getProgressColor(score: number) {
  if (score >= 70) return "bg-green-500";
  if (score >= 40) return "bg-yellow-500";
  return "bg-red-500";
}

/**
 * WorkflowSessionCard Component
 * Displays lead evaluation results from conversational workflows
 */
export function WorkflowSessionCard({
  session,
  isLoading,
  error,
  defaultExpanded = true,
  className,
}: WorkflowSessionCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Loading state
  if (isLoading) {
    return (
      <div
        className={cn(
          "rounded-lg border border-purple-200 bg-purple-50/50 p-3 sm:p-4",
          className,
        )}
      >
        <div className="flex items-center gap-2">
          <Loader2 className="size-4 animate-spin text-purple-600" />
          <span className="text-sm text-muted-foreground">
            Loading lead data...
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
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-500" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-red-900">
              Failed to load lead data
            </p>
            <p className="mt-1 text-xs text-red-700">
              {error.message || "An error occurred"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // No session or no lead evaluation result
  if (!session || !isLeadEvaluationResult(session.result_data)) {
    return null;
  }

  const result = session.result_data;
  const qualityStyles = getLeadQualityStyles(result.lead_quality);
  const priorityStyles = getPriorityStyles(result.priority_level);
  const QualityIcon = qualityStyles.icon;

  return (
    <div
      className={cn(
        "rounded-lg border transition-all",
        qualityStyles.border,
        qualityStyles.bg,
        className,
      )}
    >
      {/* Header - Always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between gap-3 p-3 text-left transition-colors hover:bg-white/30 sm:p-4"
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div className="flex items-center gap-2">
            <Target className="size-5 text-purple-600" />
            <span className="text-sm font-semibold text-foreground sm:text-base">
              Lead Evaluation
            </span>
          </div>

          {/* Quick stats badges */}
          <div className="hidden items-center gap-2 sm:flex">
            <Badge
              className={cn(
                "gap-1 font-medium",
                qualityStyles.bg,
                qualityStyles.text,
                qualityStyles.border,
              )}
            >
              <QualityIcon className={cn("size-3", qualityStyles.iconColor)} />
              {result.lead_quality.charAt(0).toUpperCase() +
                result.lead_quality.slice(1)}
            </Badge>
            <Badge
              className={cn(
                "font-medium",
                priorityStyles.bg,
                priorityStyles.text,
              )}
            >
              {result.priority_level.toUpperCase()} Priority
            </Badge>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {/* Lead Score */}
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "text-xl font-bold sm:text-2xl",
                getScoreColor(result.lead_score),
              )}
            >
              {result.lead_score}
            </span>
            <span className="text-xs text-muted-foreground">/100</span>
          </div>

          {isExpanded ? (
            <ChevronUp className="size-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="space-y-4 border-t border-gray-200/50 p-3 sm:p-4">
          {/* Mobile badges */}
          <div className="flex flex-wrap items-center gap-2 sm:hidden">
            <Badge
              className={cn(
                "gap-1 font-medium",
                qualityStyles.bg,
                qualityStyles.text,
                qualityStyles.border,
              )}
            >
              <QualityIcon className={cn("size-3", qualityStyles.iconColor)} />
              {result.lead_quality.charAt(0).toUpperCase() +
                result.lead_quality.slice(1)}
            </Badge>
            <Badge
              className={cn(
                "font-medium",
                priorityStyles.bg,
                priorityStyles.text,
              )}
            >
              {result.priority_level.toUpperCase()}
            </Badge>
          </div>

          {/* Score Progress Bar */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Lead Score</span>
              <span className="font-medium">{result.lead_score}%</span>
            </div>
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-gray-200">
              <div
                className={cn(
                  "h-full transition-all",
                  getProgressColor(result.lead_score),
                )}
                style={{ width: `${result.lead_score}%` }}
              />
            </div>
          </div>

          {/* Contact Information */}
          <div className="rounded-lg border border-gray-200 bg-white p-3">
            <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <User className="size-3.5" />
              Contact Information
            </h4>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <User className="size-4 text-gray-400" />
                <span className="text-sm font-medium">
                  {result.lead_summary.contact.name || "—"}
                </span>
              </div>
              {result.lead_summary.contact.email && (
                <div className="flex items-center gap-2">
                  <Mail className="size-4 text-gray-400" />
                  <a
                    href={`mailto:${result.lead_summary.contact.email}`}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    {result.lead_summary.contact.email}
                  </a>
                </div>
              )}
              {result.lead_summary.contact.phone && (
                <div className="flex items-center gap-2">
                  <Phone className="size-4 text-gray-400" />
                  <a
                    href={`tel:${result.lead_summary.contact.phone}`}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    {result.lead_summary.contact.phone}
                  </a>
                </div>
              )}
            </div>
          </div>

          {/* Service Need */}
          <div className="rounded-lg border border-gray-200 bg-white p-3">
            <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <FileText className="size-3.5" />
              Service Need
            </h4>
            <p className="text-sm text-foreground">
              {result.lead_summary.service_need || "Not specified"}
            </p>
          </div>

          {/* Additional Info */}
          {Object.keys(result.lead_summary.additional_info).length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Additional Details
              </h4>
              <div className="space-y-1">
                {Object.entries(result.lead_summary.additional_info).map(
                  ([key, value]) => (
                    <div key={key} className="flex items-start gap-2 text-sm">
                      <span className="font-medium capitalize text-muted-foreground">
                        {key.replace(/_/g, " ")}:
                      </span>
                      <span className="text-foreground">{value}</span>
                    </div>
                  ),
                )}
              </div>
            </div>
          )}

          {/* Scoring Breakdown */}
          <div className="rounded-lg border border-gray-200 bg-white p-3">
            <h4 className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <TrendingUp className="size-3.5" />
              Scoring Breakdown
            </h4>

            {/* Signals Matched */}
            {result.scoring.signals_matched.length > 0 && (
              <div className="mb-3">
                <span className="text-xs font-medium text-green-700">
                  Positive Signals
                </span>
                <div className="mt-1.5 space-y-1.5">
                  {result.scoring.signals_matched.map((signal) => (
                    <div
                      key={signal.signal_id}
                      className="flex items-start gap-2 rounded bg-green-50 px-2 py-1.5 text-xs"
                    >
                      <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-green-600" />
                      <div className="flex-1">
                        <span className="text-green-800">{signal.reason}</span>
                      </div>
                      <Badge
                        variant="outline"
                        className="shrink-0 border-green-300 bg-green-100 text-green-700"
                      >
                        +{signal.points}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Penalties Applied */}
            {result.scoring.penalties_applied.length > 0 && (
              <div className="mb-3">
                <span className="text-xs font-medium text-red-700">
                  Risk Factors
                </span>
                <div className="mt-1.5 space-y-1.5">
                  {result.scoring.penalties_applied.map((penalty) => (
                    <div
                      key={penalty.penalty_id}
                      className="flex items-start gap-2 rounded bg-red-50 px-2 py-1.5 text-xs"
                    >
                      <TrendingDown className="mt-0.5 size-3.5 shrink-0 text-red-600" />
                      <div className="flex-1">
                        <span className="text-red-800">{penalty.reason}</span>
                      </div>
                      <Badge
                        variant="outline"
                        className="shrink-0 border-red-300 bg-red-100 text-red-700"
                      >
                        {penalty.points}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI Reasoning */}
            {result.scoring.reasoning && (
              <div className="rounded bg-gray-50 p-2 text-xs text-muted-foreground">
                <span className="font-medium">AI Analysis:</span>{" "}
                {result.scoring.reasoning}
              </div>
            )}
          </div>

          {/* Follow-up Questions */}
          {result.lead_summary.follow_up_questions.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <HelpCircle className="size-3.5" />
                Suggested Follow-up Questions
              </h4>
              <ul className="space-y-1.5">
                {result.lead_summary.follow_up_questions.map(
                  (question, index) => (
                    <li
                      key={index}
                      className="flex items-start gap-2 text-sm text-foreground"
                    >
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-purple-400" />
                      {question}
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}

          {/* Metadata Footer */}
          <div className="flex flex-wrap items-center gap-3 border-t border-gray-200/50 pt-3 text-xs text-muted-foreground">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger className="flex items-center gap-1">
                  <span className="font-medium">Confidence:</span>
                  <span>{Math.round(result.confidence * 100)}%</span>
                </TooltipTrigger>
                <TooltipContent>
                  <p>AI confidence in the evaluation accuracy</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <div className="flex items-center gap-1">
              <Clock className="size-3" />
              <span>
                {new Date(result.evaluated_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </span>
            </div>

            <div className="flex items-center gap-1">
              <span className="font-medium">Status:</span>
              <Badge
                variant="outline"
                className={cn(
                  "text-xs",
                  session.status === "completed"
                    ? "border-green-300 bg-green-50 text-green-700"
                    : session.status === "in_progress"
                      ? "border-blue-300 bg-blue-50 text-blue-700"
                      : "border-gray-300 bg-gray-50 text-gray-700",
                )}
              >
                {session.status.replace("_", " ")}
              </Badge>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
