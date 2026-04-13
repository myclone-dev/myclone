"use client";

import {
  Brain,
  CheckCircle2,
  Clock,
  AlertCircle,
  Database,
} from "lucide-react";
import { useScrapingJobs } from "@/lib/queries/knowledge";
import { Skeleton } from "@/components/ui/skeleton";

interface KnowledgeStatsProps {
  userId: string;
}

export function KnowledgeStats({ userId }: KnowledgeStatsProps) {
  const { data: jobsResponse, isLoading } = useScrapingJobs(userId);

  const jobsArray = jobsResponse?.jobs || [];
  const stats = {
    total: jobsResponse?.total_jobs || 0,
    completed: jobsResponse?.completed_jobs || 0,
    processing: jobsResponse?.active_jobs || 0,
    failed: jobsResponse?.failed_jobs || 0,
    totalRecords: jobsArray.reduce(
      (sum, j) => sum + (j.records_imported || 0),
      0,
    ),
  };

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-20 rounded-lg" />
        ))}
      </div>
    );
  }

  const statItems = [
    {
      label: "Total Jobs",
      value: stats.total,
      icon: Brain,
      color: "text-ai-brown",
      bg: "bg-orange-100",
    },
    {
      label: "Records Imported",
      value: stats.totalRecords.toLocaleString(),
      icon: Database,
      color: "text-ai-brown",
      bg: "bg-orange-100",
    },
    {
      label: "Completed",
      value: stats.completed,
      icon: CheckCircle2,
      color: "text-green-600",
      bg: "bg-green-100",
    },
    {
      label: "Processing",
      value: stats.processing,
      icon: Clock,
      color: "text-amber-600",
      bg: "bg-amber-100",
    },
    {
      label: "Failed",
      value: stats.failed,
      icon: AlertCircle,
      color: "text-red-600",
      bg: "bg-red-100",
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {statItems.map((stat) => {
        const Icon = stat.icon;
        return (
          <div key={stat.label} className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">
                  {stat.label}
                </p>
                <p className="text-2xl font-bold">{stat.value}</p>
              </div>
              <div className={`rounded-md p-2 ${stat.bg}`}>
                <Icon className={`size-4 ${stat.color}`} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
