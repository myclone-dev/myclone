"use client";

import {
  FileText,
  Linkedin,
  Twitter,
  Globe,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Music,
  Video,
  Youtube,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useScrapingJobs } from "@/lib/queries/knowledge";
import type { DataSourceType, ScrapingStatus } from "@/lib/queries/knowledge";

interface ScrapingJobsListProps {
  userId: string;
}

const sourceIcons: Record<DataSourceType, typeof Linkedin> = {
  linkedin: Linkedin,
  twitter: Twitter,
  website: Globe,
  pdf: FileText,
  audio: Music,
  video: Video,
  youtube: Youtube,
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

export function ScrapingJobsList({ userId }: ScrapingJobsListProps) {
  const { data: jobsResponse, isLoading } = useScrapingJobs(userId);
  const jobs = jobsResponse?.jobs || [];

  if (isLoading) {
    return (
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          Recent Activity
        </h3>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-start gap-4">
              <Skeleton className="size-12 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (!jobs || jobs.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          Recent Activity
        </h3>
        <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center">
          <p className="text-sm text-slate-600">No upload activity yet</p>
          <p className="mt-1 text-xs text-slate-500">
            Start by uploading your knowledge sources above
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <h3 className="mb-4 text-lg font-semibold text-slate-900">
        Recent Activity ({jobs.length})
      </h3>
      <div className="space-y-4">
        {jobs.map((job) => {
          const Icon = sourceIcons[job.source_type] || FileText;
          const statusInfo = statusConfig[job.status] || statusConfig.pending;
          const StatusIcon = statusInfo?.icon || Clock;

          // Generate descriptive label
          const getJobLabel = () => {
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
            if (job.source_type === "website") return "Website Import";
            if (job.source_type === "audio") return "Audio File";
            if (job.source_type === "video") return "Video File";
            return `${job.source_type.charAt(0).toUpperCase() + job.source_type.slice(1)} Import`;
          };

          return (
            <div
              key={job.job_id}
              className="flex items-start gap-4 rounded-lg border border-slate-200 p-4 transition-colors hover:bg-slate-50"
            >
              <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-orange-100 text-ai-brown 600">
                <Icon className="size-6" />
              </div>
              <div className="flex-1 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p
                      className="font-medium text-slate-900"
                      title={getJobLabel()}
                    >
                      {getJobLabel()}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Started {new Date(job.started_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge
                    variant={statusInfo.variant}
                    className="flex items-center gap-1"
                  >
                    <StatusIcon
                      className={`size-3 ${job.status === "processing" ? "animate-spin" : ""}`}
                    />
                    {statusInfo.label}
                  </Badge>
                </div>
                {job.status === "completed" && (
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
                    {job.records_imported > 0 && (
                      <span>{job.records_imported} records</span>
                    )}
                    {job.posts_imported > 0 && (
                      <span>{job.posts_imported} posts</span>
                    )}
                    {job.experiences_imported > 0 && (
                      <span>{job.experiences_imported} experiences</span>
                    )}
                    {job.pages_imported > 0 && (
                      <span>{job.pages_imported} pages</span>
                    )}
                  </div>
                )}
                {job.status === "failed" && job.error_message && (
                  <p className="text-xs text-red-600">{job.error_message}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
