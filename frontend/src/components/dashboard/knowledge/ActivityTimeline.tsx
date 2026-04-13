"use client";

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
} from "lucide-react";
import { useScrapingJobs } from "@/lib/queries/knowledge";
import { Badge } from "@/components/ui/badge";
import type { DataSourceType, ScrapingStatus } from "@/lib/queries/knowledge";

interface ActivityTimelineProps {
  userId: string;
}

const sourceConfig: Record<
  DataSourceType,
  { icon: typeof Linkedin; label: string }
> = {
  linkedin: { icon: Linkedin, label: "LinkedIn" },
  twitter: { icon: Twitter, label: "Twitter" },
  website: { icon: Globe, label: "Website" },
  pdf: { icon: FileText, label: "PDF" },
  audio: { icon: Music, label: "Audio" },
  video: { icon: Video, label: "Video" },
  youtube: { icon: Youtube, label: "YouTube" },
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

export function ActivityTimeline({ userId }: ActivityTimelineProps) {
  const { data: jobsResponse } = useScrapingJobs(userId);
  const jobs = jobsResponse?.jobs || [];

  if (!jobs || jobs.length === 0) {
    return null;
  }

  // Show only last 5 jobs
  const recentJobs = jobs.slice(0, 5);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Recent Activity</h2>
        <span className="text-sm text-muted-foreground">
          {jobs.length} total
        </span>
      </div>

      <div className="space-y-2">
        {recentJobs.map((job) => {
          const source = sourceConfig[job.source_type] || sourceConfig.pdf;
          const status = statusConfig[job.status] || statusConfig.queued;
          const SourceIcon = source.icon;
          const StatusIcon = status.icon;

          // Generate a more descriptive label based on source type and source_name
          const getSourceLabel = () => {
            // Use source_name from API if available
            if (job.source_name) {
              return job.source_name;
            }

            // Fallback labels
            if (job.file_type === "pdf") return "PDF Document";
            if (job.file_type === "audio") return "Audio File";
            if (job.file_type === "video") return "Video File";
            if (job.source_type === "linkedin") return "LinkedIn Profile";
            if (job.source_type === "twitter") return "Twitter Profile";
            if (job.source_type === "website") return "Website";
            if (job.source_type === "youtube") return "YouTube Video";
            return source.label;
          };

          const sourceLabel = getSourceLabel();

          return (
            <div
              key={job.job_id}
              className="flex items-center gap-3 rounded-lg border bg-card p-3 text-sm"
            >
              <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted">
                <SourceIcon className="size-4" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-medium truncate" title={sourceLabel}>
                    {sourceLabel}
                  </p>
                  <Badge variant={status.variant} className="gap-1 text-xs h-5">
                    <StatusIcon
                      className={`size-3 ${job.status === "processing" ? "animate-spin" : ""}`}
                    />
                    {status.label}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {new Date(job.started_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </p>
              </div>

              {job.status === "completed" && (
                <div className="flex gap-3 text-xs">
                  {job.records_imported > 0 && (
                    <div className="text-center">
                      <p className="font-bold">{job.records_imported}</p>
                      <p className="text-muted-foreground">records</p>
                    </div>
                  )}
                  {job.posts_imported > 0 && (
                    <div className="text-center">
                      <p className="font-bold">{job.posts_imported}</p>
                      <p className="text-muted-foreground">posts</p>
                    </div>
                  )}
                  {job.pages_imported > 0 && (
                    <div className="text-center">
                      <p className="font-bold">{job.pages_imported}</p>
                      <p className="text-muted-foreground">pages</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
