"use client";

import { useState, useMemo } from "react";
import {
  FileText,
  Linkedin,
  Twitter,
  Globe,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  Music,
  Video,
  Youtube,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  ChevronDown,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useRefreshDocument } from "@/lib/queries/knowledge";
import type {
  DataSourceType,
  ScrapingStatus,
  ScrapingJob,
} from "@/lib/queries/knowledge";

interface RecentImportsProps {
  jobs: ScrapingJob[];
}

const sourceConfig: Record<
  DataSourceType | "document",
  { icon: typeof Linkedin; label: string; color: string }
> = {
  linkedin: { icon: Linkedin, label: "LinkedIn", color: "text-linkedin" },
  twitter: { icon: Twitter, label: "Twitter", color: "text-twitter" },
  website: { icon: Globe, label: "Website", color: "text-website" },
  pdf: { icon: FileText, label: "PDF", color: "text-red-600" },
  document: { icon: FileText, label: "Document", color: "text-document" },
  audio: { icon: Music, label: "Audio", color: "text-emerald-600" },
  video: { icon: Video, label: "Video", color: "text-blue-600" },
  youtube: { icon: Youtube, label: "YouTube", color: "text-youtube" },
};

const statusConfig: Record<
  ScrapingStatus,
  {
    label: string;
    variant: "default" | "secondary" | "destructive";
    icon: typeof Clock;
  }
> = {
  queued: { label: "Queued", variant: "secondary", icon: Clock },
  pending: { label: "Pending", variant: "secondary", icon: Clock },
  processing: { label: "Processing", variant: "default", icon: Loader2 },
  completed: { label: "Completed", variant: "default", icon: CheckCircle2 },
  failed: { label: "Failed", variant: "destructive", icon: XCircle },
};

// Helper function to detect file extension from filename
function getFileExtension(filename: string | null): string | null {
  if (!filename) return null;
  const match = filename.match(/\.([^.]+)$/);
  return match ? match[1].toLowerCase() : null;
}

// Helper function to get source display information based on job type and metadata
function getSourceDisplay(job: ScrapingJob) {
  // For document uploads, check both file_type and filename extension
  const fileExt = getFileExtension(job.source_name);

  // Prioritize checking the filename extension for Office documents
  // since backend may send file_type="pdf" for all document processing
  if (fileExt) {
    if (fileExt === "docx") {
      return {
        icon: FileText,
        label: "DOCX",
        name: job.source_name || "Word Document",
        color: "text-blue-700",
      };
    } else if (fileExt === "pptx") {
      return {
        icon: FileText,
        label: "PPTX",
        name: job.source_name || "PowerPoint Presentation",
        color: "text-orange-600",
      };
    } else if (fileExt === "xlsx") {
      return {
        icon: FileText,
        label: "XLSX",
        name: job.source_name || "Excel Spreadsheet",
        color: "text-green-700",
      };
    } else if (fileExt === "pdf") {
      return {
        icon: FileText,
        label: "PDF",
        name: job.source_name || "PDF Document",
        color: "text-red-600",
      };
    } else if (fileExt === "txt" || fileExt === "md") {
      return {
        icon: FileText,
        label: fileExt.toUpperCase(),
        name: job.source_name || "Text Document",
        color: "text-gray-600",
      };
    }
  }

  // Fallback to file_type for media files
  if (job.file_type) {
    if (job.file_type === "audio") {
      return {
        icon: Music,
        label: "Audio",
        name: job.source_name || "Audio file",
        color: "text-green-600",
      };
    } else if (job.file_type === "video") {
      return {
        icon: Video,
        label: "Video",
        name: job.source_name || "Video file",
        color: "text-blue-600",
      };
    }
  }

  // Handle YouTube videos - use source_name (video title) from backend
  if (job.source_type === "youtube") {
    return {
      icon: Youtube,
      label: "YouTube",
      name: job.source_name || "YouTube Video",
      color: "text-youtube",
    };
  }

  // For other source types, use the default configuration
  const config = sourceConfig[job.source_type] || sourceConfig.pdf;
  return {
    icon: config.icon,
    label: config.label,
    name: job.source_name || config.label,
    color: config.color,
  };
}

export function RecentImports({ jobs }: RecentImportsProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  const refreshDocument = useRefreshDocument();

  // Separate active jobs (processing/pending/queued) from completed/failed
  const { activeJobs, hasActiveJobs, recentCompletedJobs } = useMemo(() => {
    const active = jobs.filter(
      (job) =>
        job.status === "processing" ||
        job.status === "pending" ||
        job.status === "queued",
    );

    // Get jobs completed/failed in the last 24 hours
    const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const recentCompleted = jobs.filter((job) => {
      if (job.status !== "completed" && job.status !== "failed") return false;
      const jobDate = new Date(job.started_at);
      return jobDate > oneDayAgo;
    });

    return {
      activeJobs: active,
      hasActiveJobs: active.length > 0,
      recentCompletedJobs: recentCompleted,
    };
  }, [jobs]);

  // Default expanded state: only expand if there are active jobs
  const [isExpanded, setIsExpanded] = useState(hasActiveJobs);

  const handleRetry = async (
    documentId: string,
    userId: string,
    sourceName: string,
  ) => {
    try {
      await refreshDocument.mutateAsync({
        user_id: userId,
        document_id: documentId,
      });
      toast.success(`Started refreshing embeddings for ${sourceName}`);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to refresh document embeddings",
      );
    }
  };

  // Don't show anything if no jobs at all
  if (jobs.length === 0) {
    return null;
  }

  // If no active jobs and no recent completed jobs, don't show the section
  if (!hasActiveJobs && recentCompletedJobs.length === 0) {
    return null;
  }

  // Calculate pagination
  const totalPages = Math.ceil(jobs.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentJobs = jobs.slice(startIndex, endIndex);

  const handlePrevPage = () => {
    setCurrentPage((prev) => Math.max(1, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((prev) => Math.min(totalPages, prev + 1));
  };

  return (
    <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
      <div className="rounded-xl border bg-card overflow-hidden">
        {/* Header - Always visible */}
        <CollapsibleTrigger asChild>
          <button className="w-full p-3 sm:p-4 flex items-center gap-3 hover:bg-muted/30 transition-colors text-left">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <span className="inline-block size-1.5 rounded-full bg-primary shrink-0" />
              <span className="font-semibold text-sm sm:text-base">
                Recent Activity
              </span>
              {hasActiveJobs && (
                <Badge
                  variant="default"
                  className="h-5 gap-1 text-[10px] sm:text-xs animate-pulse"
                >
                  <Loader2 className="size-2.5 animate-spin" />
                  {activeJobs.length} processing
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-2">
              <div className="px-2 sm:px-3 py-0.5 sm:py-1 rounded-full bg-muted/50 border">
                <span className="text-[10px] sm:text-xs font-medium text-muted-foreground">
                  {jobs.length} {jobs.length === 1 ? "import" : "imports"}
                </span>
              </div>
              <ChevronDown
                className={cn(
                  "size-4 sm:size-5 text-muted-foreground transition-transform duration-200 shrink-0",
                  isExpanded && "rotate-180",
                )}
              />
            </div>
          </button>
        </CollapsibleTrigger>

        {/* Expanded content */}
        <CollapsibleContent>
          <div className="border-t">
            <div className="p-2 sm:p-4 space-y-2 sm:space-y-3 max-h-[350px] overflow-y-auto">
              {currentJobs.map((job) => {
                const sourceDisplay = getSourceDisplay(job);
                const status = statusConfig[job.status] || statusConfig.pending;
                const SourceIcon = sourceDisplay.icon;
                const StatusIcon = status.icon;

                return (
                  <div
                    key={job.job_id}
                    className={`group flex items-center gap-2 sm:gap-3 rounded-lg sm:rounded-xl border p-2.5 sm:p-4 transition-all duration-300 hover:shadow-md ${
                      job.status === "completed"
                        ? "border-green-200 bg-linear-to-r from-green-50/50 to-green-50/20 hover:from-green-50 hover:to-green-50/40"
                        : job.status === "failed"
                          ? "border-red-200 bg-linear-to-r from-red-50/50 to-red-50/20 hover:from-red-50 hover:to-red-50/40"
                          : job.status === "processing"
                            ? "border-blue-200 bg-linear-to-r from-blue-50/50 to-blue-50/20 hover:from-blue-50 hover:to-blue-50/40 animate-pulse"
                            : "bg-card hover:bg-muted/50 border-border"
                    }`}
                  >
                    {/* Icon - Smaller on mobile */}
                    <div
                      className={`flex size-9 sm:size-11 shrink-0 items-center justify-center rounded-lg sm:rounded-xl ${
                        job.status === "completed"
                          ? "bg-green-100"
                          : job.status === "failed"
                            ? "bg-red-100"
                            : job.status === "processing"
                              ? "bg-blue-100"
                              : "bg-muted"
                      }`}
                    >
                      <SourceIcon
                        className={`size-4 sm:size-5 ${sourceDisplay.color}`}
                      />
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 sm:gap-2 mb-0.5 sm:mb-1 flex-wrap">
                        <p className="font-medium text-xs sm:text-sm">
                          {sourceDisplay.label}
                        </p>
                        <Badge
                          variant={status.variant}
                          className="gap-0.5 sm:gap-1 h-4 sm:h-5 text-[10px] sm:text-xs px-1.5 sm:px-2"
                        >
                          <StatusIcon
                            className={`size-2.5 sm:size-3 ${job.status === "processing" ? "animate-spin" : ""}`}
                          />
                          {status.label}
                        </Badge>
                      </div>
                      <p className="text-[10px] sm:text-xs text-muted-foreground truncate">
                        {sourceDisplay.name}
                      </p>
                      <p className="text-[10px] sm:text-xs text-muted-foreground">
                        {new Date(job.started_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>

                    {/* Stats for completed - Hidden on mobile */}
                    {job.status === "completed" && (
                      <div className="hidden items-center gap-4 sm:flex">
                        {job.records_imported > 0 && (
                          <div className="flex flex-col items-end">
                            <span className="text-lg font-bold text-green-700">
                              {job.records_imported.toLocaleString()}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              records
                            </span>
                          </div>
                        )}
                        {job.posts_imported > 0 && (
                          <div className="flex flex-col items-end">
                            <span className="text-lg font-bold text-green-700">
                              {job.posts_imported.toLocaleString()}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              posts
                            </span>
                          </div>
                        )}
                        {job.pages_imported > 0 && (
                          <div className="flex flex-col items-end">
                            <span className="text-lg font-bold text-green-700">
                              {job.pages_imported.toLocaleString()}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              pages
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Retry button for failed jobs */}
                    {job.status === "failed" && job.document_id && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          handleRetry(
                            job.document_id!,
                            job.user_id,
                            sourceDisplay.name,
                          )
                        }
                        disabled={refreshDocument.isPending}
                        className="h-6 sm:h-7 gap-1 sm:gap-1.5 text-[10px] sm:text-xs px-2 sm:px-3 hover:bg-yellow-bright hover:text-black"
                      >
                        <RefreshCw
                          className={`size-2.5 sm:size-3 ${refreshDocument.isPending ? "animate-spin" : ""}`}
                        />
                        <span className="hidden sm:inline">
                          {refreshDocument.isPending ? "Retrying..." : "Retry"}
                        </span>
                        <span className="sm:hidden">
                          {refreshDocument.isPending ? "..." : "Retry"}
                        </span>
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex flex-col gap-3 p-3 sm:p-4 border-t sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-muted-foreground sm:text-sm">
                  Showing {startIndex + 1} to {Math.min(endIndex, jobs.length)}{" "}
                  of {jobs.length} imports
                </p>
                <div className="flex items-center justify-between gap-2 sm:justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePrevPage}
                    disabled={currentPage === 1}
                    className="h-8 px-2 sm:h-9 sm:px-3"
                  >
                    <ChevronLeft className="size-3 sm:size-4 sm:mr-1" />
                    <span className="hidden sm:inline">Previous</span>
                  </Button>
                  <span className="text-xs sm:text-sm whitespace-nowrap">
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleNextPage}
                    disabled={currentPage === totalPages}
                    className="h-8 px-2 sm:h-9 sm:px-3"
                  >
                    <span className="hidden sm:inline">Next</span>
                    <ChevronRight className="size-3 sm:size-4 sm:ml-1" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
