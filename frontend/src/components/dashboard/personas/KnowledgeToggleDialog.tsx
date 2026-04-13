"use client";

import { useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Linkedin, Twitter, Globe, FileText, Youtube } from "lucide-react";
import { toast } from "sonner";
import {
  useAvailableKnowledgeSources,
  useAttachKnowledgeSources,
  useDetachKnowledgeSource,
  useToggleKnowledgeSource,
} from "@/lib/queries/persona";

interface KnowledgeToggleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  personaId: string;
  personaName: string;
}

const sourceIcons = {
  linkedin: { icon: Linkedin, color: "text-blue-600", bgColor: "bg-blue-50" },
  twitter: { icon: Twitter, color: "text-sky-500", bgColor: "bg-sky-50" },
  website: { icon: Globe, color: "text-ai-brown 600", bgColor: "bg-orange-50" },
  document: {
    icon: FileText,
    color: "text-orange-600",
    bgColor: "bg-orange-50",
  },
  youtube: { icon: Youtube, color: "text-red-600", bgColor: "bg-red-50" },
};

export function KnowledgeToggleDialog({
  open,
  onOpenChange,
  personaId,
  personaName,
}: KnowledgeToggleDialogProps) {
  const { data: availableSources, isLoading } =
    useAvailableKnowledgeSources(personaId);
  const attachSources = useAttachKnowledgeSources();
  const detachSource = useDetachKnowledgeSource();
  const toggleSource = useToggleKnowledgeSource();

  // Reset local changes when dialog opens (placeholder for future use)
  useEffect(() => {
    if (open) {
      // Reset any local state if needed
    }
  }, [open]);

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

    // If attached and enabled, toggle to disable
    if (isCurrentlyEnabled) {
      try {
        await toggleSource.mutateAsync({
          personaId,
          sourceRecordId,
        });
        toast.success("Knowledge source disabled");
      } catch (error) {
        const err = error as {
          response?: { data?: { detail?: string } };
          message?: string;
        };
        toast.error("Failed to disable source", {
          description: err.response?.data?.detail || err.message,
        });
      }
      return;
    }

    // If attached but disabled, toggle to enable
    try {
      await toggleSource.mutateAsync({
        personaId,
        sourceRecordId,
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
  };

  if (isLoading) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Manage Knowledge Sources</DialogTitle>
            <DialogDescription>Loading knowledge sources...</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-24 rounded-lg bg-slate-200" />
            ))}
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  if (!availableSources) {
    return null;
  }

  const sources = availableSources.available_sources;
  const enabledCount = sources.filter(
    (s) => s.is_attached && s.is_enabled,
  ).length;
  const attachedCount = sources.filter((s) => s.is_attached).length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[620px] max-h-[85vh] overflow-y-auto overflow-x-hidden">
        <DialogHeader>
          <DialogTitle>Manage Knowledge Sources</DialogTitle>
          <DialogDescription>
            Select which knowledge sources to include for{" "}
            <strong>{personaName}</strong>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Summary */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border bg-muted/50 p-3">
              <p className="text-xs text-muted-foreground mb-1">
                Attached Sources
              </p>
              <p className="text-2xl font-bold">{attachedCount}</p>
            </div>
            <div className="rounded-lg border bg-muted/50 p-3">
              <p className="text-xs text-muted-foreground mb-1">
                Enabled & Active
              </p>
              <p className="text-2xl font-bold text-green-600">
                {enabledCount}
              </p>
            </div>
          </div>

          {/* Knowledge Sources List */}
          {sources.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <p className="text-sm text-muted-foreground">
                No knowledge sources available. Please add knowledge sources to
                your library first.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {sources.map((source) => {
                const config = sourceIcons[source.source_type];
                const Icon = config.icon;

                return (
                  <div
                    key={source.source_record_id}
                    className={`rounded-lg border p-4 transition-all ${
                      source.is_attached && source.is_enabled
                        ? "border-green-200 bg-green-50/50"
                        : source.is_attached
                          ? "border-violet-200 bg-orange-50/50"
                          : "bg-card"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Icon */}
                      <div
                        className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${config.bgColor}`}
                      >
                        <Icon className={`size-5 ${config.color}`} />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-medium break-words">
                          {source.display_name}
                        </h4>
                      </div>

                      {/* Toggle */}
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs text-muted-foreground whitespace-nowrap hidden sm:inline">
                          {source.is_attached && source.is_enabled
                            ? "Enabled"
                            : "Disabled"}
                        </span>
                        <Switch
                          checked={source.is_attached && source.is_enabled}
                          onCheckedChange={() =>
                            handleToggle(
                              source.source_record_id,
                              source.is_attached,
                              source.is_enabled,
                            )
                          }
                          disabled={
                            attachSources.isPending ||
                            detachSource.isPending ||
                            toggleSource.isPending
                          }
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
