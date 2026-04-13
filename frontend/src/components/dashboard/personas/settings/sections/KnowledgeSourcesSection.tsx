"use client";

import Link from "next/link";
import {
  Linkedin,
  Twitter,
  Globe,
  FileText,
  Youtube,
  BookOpen,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { SectionHeader } from "../components/SectionHeader";
import {
  useAvailableKnowledgeSources,
  useAttachKnowledgeSources,
  useToggleKnowledgeSource,
} from "@/lib/queries/persona";
import { cn } from "@/lib/utils";

interface KnowledgeSourcesSectionProps {
  personaId: string;
}

const sourceIcons = {
  linkedin: { icon: Linkedin, color: "text-blue-600", bgColor: "bg-blue-50" },
  twitter: { icon: Twitter, color: "text-sky-500", bgColor: "bg-sky-50" },
  website: { icon: Globe, color: "text-orange-600", bgColor: "bg-orange-50" },
  document: {
    icon: FileText,
    color: "text-orange-600",
    bgColor: "bg-orange-50",
  },
  youtube: { icon: Youtube, color: "text-red-600", bgColor: "bg-red-50" },
};

export function KnowledgeSourcesSection({
  personaId,
}: KnowledgeSourcesSectionProps) {
  const { data: availableSources, isLoading } =
    useAvailableKnowledgeSources(personaId);
  const attachSources = useAttachKnowledgeSources();
  const toggleSource = useToggleKnowledgeSource();

  const handleToggle = async (
    sourceRecordId: string,
    isCurrentlyAttached: boolean,
    isCurrentlyEnabled: boolean,
  ) => {
    // If not attached, attach and enable
    if (!isCurrentlyAttached) {
      try {
        await attachSources.mutateAsync({
          personaId,
          request: {
            sources: [
              {
                source_type: availableSources!.available_sources.find(
                  (s) => s.source_record_id === sourceRecordId,
                )!.source_type,
                source_record_id: sourceRecordId,
              },
            ],
          },
        });
        toast.success("Knowledge source enabled");
      } catch (error) {
        const err = error as {
          response?: { data?: { detail?: string } };
          message?: string;
        };
        toast.error("Failed to enable source", {
          description: err.response?.data?.detail || err.message,
        });
      }
      return;
    }

    // If attached, toggle enabled/disabled
    try {
      await toggleSource.mutateAsync({
        personaId,
        sourceRecordId,
      });
      toast.success(
        isCurrentlyEnabled
          ? "Knowledge source disabled"
          : "Knowledge source enabled",
      );
    } catch (error) {
      const err = error as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      toast.error(
        `Failed to ${isCurrentlyEnabled ? "disable" : "enable"} source`,
        {
          description: err.response?.data?.detail || err.message,
        },
      );
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <SectionHeader
          title="Knowledge Sources"
          description="Manage which knowledge sources this persona uses"
        />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (!availableSources) {
    return null;
  }

  const sources = availableSources.available_sources;
  const totalCount = sources.length;
  const attachedCount = sources.filter((s) => s.is_attached).length;
  const enabledCount = sources.filter(
    (s) => s.is_attached && s.is_enabled,
  ).length;
  const disabledCount = attachedCount - enabledCount;

  const isMutating = attachSources.isPending || toggleSource.isPending;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Knowledge Sources"
        description="Manage which knowledge sources this persona uses"
        isSaving={isMutating}
      />

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground mb-1">Total Sources</p>
          <p className="text-2xl font-bold">{totalCount}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground mb-1">Attached</p>
          <p className="text-2xl font-bold">{attachedCount}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground mb-1">Enabled</p>
          <p className="text-2xl font-bold text-green-600">{enabledCount}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground mb-1">Disabled</p>
          <p className="text-2xl font-bold text-amber-600">{disabledCount}</p>
        </Card>
      </div>

      {/* Quick Action */}
      <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg border">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-yellow-light">
            <BookOpen className="size-5 text-yellow-600" />
          </div>
          <div>
            <p className="text-sm font-medium">Add More Knowledge</p>
            <p className="text-xs text-muted-foreground">
              Go to Knowledge Library to add new sources
            </p>
          </div>
        </div>
        <Button variant="outline" asChild>
          <Link href="/dashboard/knowledge">
            <ExternalLink className="size-4 mr-2" />
            Knowledge Library
          </Link>
        </Button>
      </div>

      {/* Sources List */}
      {sources.length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <BookOpen className="size-8 text-muted-foreground mx-auto mb-3" />
          <p className="text-sm font-medium mb-1">
            No knowledge sources available
          </p>
          <p className="text-xs text-muted-foreground mb-4">
            Please add knowledge sources to your library first.
          </p>
          <Button variant="outline" asChild>
            <Link href="/dashboard/knowledge">
              <ExternalLink className="size-4 mr-2" />
              Go to Knowledge Library
            </Link>
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map((source) => {
            const config = sourceIcons[source.source_type];
            const Icon = config.icon;
            const isEnabled = source.is_attached && source.is_enabled;

            return (
              <Card
                key={source.source_record_id}
                className={cn(
                  "p-4 transition-all",
                  isEnabled && "border-green-200 bg-green-50/50",
                  source.is_attached &&
                    !source.is_enabled &&
                    "border-amber-200 bg-amber-50/50",
                )}
              >
                <div className="flex items-start gap-3">
                  {/* Icon */}
                  <div
                    className={cn(
                      "flex size-10 shrink-0 items-center justify-center rounded-xl",
                      config.bgColor,
                    )}
                  >
                    <Icon className={cn("size-5", config.color)} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-medium break-words">
                      {source.display_name}
                    </h4>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {source.source_type.charAt(0).toUpperCase() +
                        source.source_type.slice(1)}
                    </p>
                  </div>

                  {/* Toggle */}
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-muted-foreground whitespace-nowrap hidden sm:inline">
                      {isEnabled ? "Enabled" : "Disabled"}
                    </span>
                    <Switch
                      checked={isEnabled}
                      onCheckedChange={() =>
                        handleToggle(
                          source.source_record_id,
                          source.is_attached,
                          source.is_enabled,
                        )
                      }
                      disabled={isMutating}
                    />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
