"use client";

import { useParams } from "next/navigation";
import { useWorkflow, useWorkflowAnalytics } from "@/lib/queries/workflows";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  BarChart3,
  TrendingUp,
  Clock,
  Users,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

/**
 * Workflow Analytics Page
 * Shows completion stats, score distribution, and drop-off analysis
 */
export default function WorkflowAnalyticsPage() {
  const params = useParams();
  const workflowId = params.workflowId as string;

  const { data: workflow, isLoading: workflowLoading } =
    useWorkflow(workflowId);
  const { data: analytics, isLoading: analyticsLoading } =
    useWorkflowAnalytics(workflowId);

  if (workflowLoading || analyticsLoading) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="space-y-6 animate-pulse">
          <div className="h-8 w-64 bg-muted rounded" />
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-32 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!workflow || !analytics) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <p>Workflow not found</p>
      </div>
    );
  }

  const isScored = workflow.workflow_type === "scored";

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/dashboard/workflows">
                <ArrowLeft className="size-4 mr-2" />
                Back to Workflows
              </Link>
            </Button>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold">{workflow.title}</h1>
          <div className="flex items-center gap-2">
            <Badge>{isScored ? "Scored" : "Simple"}</Badge>
            <Badge variant="outline">
              {workflow.workflow_config.steps.length} questions
            </Badge>
          </div>
        </div>
        <Button asChild>
          <Link href={`/dashboard/workflows/${workflowId}/edit`}>
            Edit Workflow
          </Link>
        </Button>
      </div>

      {/* AI Guidance Card */}
      {workflow.workflow_objective && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Sparkles className="size-5 text-yellow-bright" />
              AI Guidance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {workflow.workflow_objective}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Overview Stats */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Sessions
            </CardTitle>
            <Users className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analytics.total_sessions}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <TrendingUp className="size-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {analytics.completed_sessions}
            </div>
            <p className="text-xs text-muted-foreground">
              {analytics.completion_rate.toFixed(1)}% completion rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Avg Completion Time
            </CardTitle>
            <Clock className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {analytics.avg_completion_time_seconds
                ? `${Math.round(analytics.avg_completion_time_seconds / 60)}m`
                : "N/A"}
            </div>
          </CardContent>
        </Card>

        {isScored && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Score</CardTitle>
              <BarChart3 className="size-4 text-yellow-bright" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {analytics.avg_score?.toFixed(1) || "N/A"}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Score Distribution (Scored only) */}
      {isScored &&
        analytics.score_distribution &&
        Object.keys(analytics.score_distribution).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Score Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(analytics.score_distribution).map(
                  ([category, count]) => {
                    const percentage =
                      analytics.completed_sessions > 0
                        ? (
                            (count / analytics.completed_sessions) *
                            100
                          ).toFixed(1)
                        : "0";
                    return (
                      <div key={category} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium">{category}</span>
                          <span className="text-muted-foreground">
                            {count} ({percentage}%)
                          </span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-yellow-bright transition-all"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    );
                  },
                )}
              </div>
            </CardContent>
          </Card>
        )}

      {/* Drop-off Analysis */}
      {analytics.drop_off_by_step &&
        Object.keys(analytics.drop_off_by_step).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Drop-off Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(analytics.drop_off_by_step)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 5)
                  .map(([stepId, count]) => {
                    const step = workflow.workflow_config.steps.find(
                      (s) => s.step_id === stepId,
                    );
                    const percentage =
                      analytics.total_sessions > 0
                        ? ((count / analytics.total_sessions) * 100).toFixed(1)
                        : "0";
                    return (
                      <div key={stepId} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium truncate">
                            {step?.question_text || stepId}
                          </span>
                          <span className="text-muted-foreground shrink-0 ml-2">
                            {count} abandoned ({percentage}%)
                          </span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-red-500 transition-all"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </CardContent>
          </Card>
        )}

      {/* Empty State */}
      {analytics.total_sessions === 0 && (
        <Card className="p-12">
          <div className="text-center space-y-3">
            <BarChart3 className="size-12 mx-auto text-muted-foreground" />
            <h3 className="font-semibold">No data yet</h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Analytics will appear here once users start completing this
              workflow.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
