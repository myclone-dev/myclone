"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Workflow as WorkflowIcon,
  BarChart3,
  MoreVertical,
  Copy,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import type { Workflow } from "@/lib/queries/workflows";

interface WorkflowCardProps {
  workflow: Workflow;
  personaName?: string;
  completionCount?: number;
  completionRate?: number;
  onDuplicate?: (workflowId: string) => void;
  onDelete?: (workflowId: string) => void;
}

export function WorkflowCard({
  workflow,
  personaName,
  completionCount = 0,
  completionRate = 0,
  onDuplicate,
  onDelete,
}: WorkflowCardProps) {
  const isPublished = !!workflow.published_at;

  // Safely get question count
  const questionCount = (() => {
    const config = workflow.workflow_config;
    if ("steps" in config && Array.isArray(config.steps)) {
      return config.steps.length;
    }
    return 0;
  })();

  const isScored = workflow.workflow_type === "scored";

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-6">
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <div className="p-2 rounded-lg bg-yellow-bright/10 shrink-0">
                <WorkflowIcon className="size-5 text-yellow-bright" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-lg truncate">
                  {workflow.title}
                </h3>
                {workflow.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                    {workflow.description}
                  </p>
                )}
              </div>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="shrink-0">
                  <MoreVertical className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onDuplicate && (
                  <DropdownMenuItem onClick={() => onDuplicate(workflow.id)}>
                    <Copy className="size-4 mr-2" />
                    Duplicate
                  </DropdownMenuItem>
                )}
                {onDelete && (
                  <DropdownMenuItem
                    onClick={() => onDelete(workflow.id)}
                    className="text-destructive"
                  >
                    <Trash2 className="size-4 mr-2" />
                    Delete
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Badges */}
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={isPublished ? "default" : "secondary"}>
              {isPublished ? "Published" : "Draft"}
            </Badge>
            {personaName && (
              <Badge
                variant="outline"
                className="bg-peach-cream border-yellow-bright/30"
              >
                {personaName}
              </Badge>
            )}
            <Badge variant="outline">
              {questionCount} question{questionCount !== 1 ? "s" : ""}
            </Badge>
            <Badge variant="outline">{isScored ? "Scored" : "Simple"}</Badge>
          </div>

          {/* Stats (if published) */}
          {isPublished && (
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <div>
                <span className="font-medium text-foreground">
                  {completionCount || 0}
                </span>{" "}
                completions
              </div>
              <div>
                <span className="font-medium text-foreground">
                  {completionRate?.toFixed(1) || "0.0"}%
                </span>{" "}
                completion rate
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2">
            <Button variant="outline" size="sm" asChild className="flex-1">
              <Link href={`/dashboard/workflows/${workflow.id}/analytics`}>
                <BarChart3 className="size-4 mr-2" />
                Analytics
              </Link>
            </Button>
            <Button variant="default" size="sm" asChild className="flex-1">
              <Link href={`/dashboard/workflows/${workflow.id}/edit`}>
                Edit
              </Link>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
