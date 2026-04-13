import { useEffect, useRef, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useScrapingJobs } from "./useScrapingJobs";
import type { ScrapingJob } from "./interface";

interface UseJobPollingOptions {
  userId: string;
  enabled?: boolean;
  pollingInterval?: number;
  onJobCompleted?: (job: ScrapingJob) => void;
  onJobFailed?: (job: ScrapingJob) => void;
}

/**
 * Smart polling hook that automatically manages polling intervals based on job status
 * Replaces the SSE implementation with simple polling approach
 */
export const useJobPolling = ({
  userId,
  enabled = true,
  pollingInterval = 5000,
  onJobCompleted,
  onJobFailed,
}: UseJobPollingOptions) => {
  const queryClient = useQueryClient();
  const previousJobsRef = useRef<Map<string, ScrapingJob>>(new Map());
  const previousHasActiveRef = useRef<boolean | null>(null);

  // Get all jobs - polling will be controlled by the computed interval below
  const { data: jobsResponse, isLoading } = useScrapingJobs(userId, {
    refetchInterval: (query) => {
      if (!enabled) return false;

      const jobs = query.state.data?.jobs || [];
      const hasActive = jobs.some(
        (job) =>
          job.status === "processing" ||
          job.status === "pending" ||
          job.status === "queued",
      );

      // Update previous state and log when polling state changes
      if (previousHasActiveRef.current !== hasActive) {
        previousHasActiveRef.current = hasActive;
      }

      return hasActive ? pollingInterval : false;
    },
  });

  // Extract jobs array from response
  const jobsArray = useMemo(
    () => jobsResponse?.jobs || [],
    [jobsResponse?.jobs],
  );

  // Calculate if there are active jobs
  const hasActiveJobs = useMemo(() => {
    return jobsArray.some(
      (job) =>
        job.status === "processing" ||
        job.status === "pending" ||
        job.status === "queued",
    );
  }, [jobsArray]);

  // Track job status changes and trigger callbacks
  useEffect(() => {
    if (!enabled || jobsArray.length === 0) return;

    jobsArray.forEach((job) => {
      const previousJob = previousJobsRef.current.get(job.job_id);

      // Check if job just completed
      if (
        previousJob &&
        previousJob.status !== "completed" &&
        job.status === "completed"
      ) {
        onJobCompleted?.(job);
        // Invalidate knowledge library to show the new source
        queryClient.invalidateQueries({
          queryKey: ["knowledge-library", userId],
        });
      }

      // Check if job just failed
      if (
        previousJob &&
        previousJob.status !== "failed" &&
        job.status === "failed"
      ) {
        onJobFailed?.(job);
      }

      // Update previous state
      previousJobsRef.current.set(job.job_id, job);
    });

    // Clean up old jobs from tracking
    const currentJobIds = new Set(jobsArray.map((job) => job.job_id));
    for (const [jobId] of previousJobsRef.current) {
      if (!currentJobIds.has(jobId)) {
        previousJobsRef.current.delete(jobId);
      }
    }
  }, [jobsArray, enabled, onJobCompleted, onJobFailed, queryClient, userId]);

  return {
    jobs: jobsArray,
    isLoading,
    hasActiveJobs,
    isPolling: enabled && hasActiveJobs,
  };
};
