"use client";

import { useState } from "react";
import {
  Music2,
  Clock,
  FileAudio,
  HardDrive,
  CheckCircle,
  Trash2,
  Loader2,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import {
  useDeleteVoiceClone,
  type VoiceClone,
} from "@/lib/queries/voice-clone";

interface VoiceCloneListProps {
  voiceClones: VoiceClone[];
  isLoading: boolean;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString: string) {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function VoiceCloneList({
  voiceClones,
  isLoading,
}: VoiceCloneListProps) {
  const [deletingVoiceId, setDeletingVoiceId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState<string | null>(null);
  const { mutate: deleteVoiceClone, isPending: isDeleting } =
    useDeleteVoiceClone();

  const handleDelete = (voiceClone: VoiceClone) => {
    setDeletingVoiceId(voiceClone.voice_id);
    setDialogOpen(null); // Close dialog immediately when delete starts

    deleteVoiceClone(
      {
        voice_id: voiceClone.voice_id,
      },
      {
        onSuccess: () => {
          toast.success("Voice clone deleted", {
            description: `"${voiceClone.name}" has been permanently deleted.`,
          });
          setDeletingVoiceId(null);
        },
        onError: (error) => {
          toast.error("Failed to delete voice clone", {
            description: error.message,
          });
          setDeletingVoiceId(null);
        },
      },
    );
  };

  if (!voiceClones || voiceClones.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 space-y-0 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <CardTitle>Your Voice Clone</CardTitle>
          <CardDescription>
            Your AI voice clone is automatically applied to all personas
          </CardDescription>
        </div>
        <Badge variant="secondary" className="gap-1.5">
          <CheckCircle className="size-3.5" />
          Active
        </Badge>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-center py-8 text-muted-foreground">
            Loading voice clones...
          </div>
        ) : (
          <div className="space-y-3">
            {voiceClones.map((voiceClone) => (
              <div
                key={voiceClone.id}
                className="flex items-center justify-between rounded-lg border border-border bg-card p-3 transition-colors hover:bg-muted/50 sm:p-4"
              >
                <div className="flex flex-1 items-start gap-2.5 sm:gap-3">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted sm:size-10">
                    <Music2 className="size-4 text-foreground sm:size-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-medium text-foreground sm:text-base">
                      {voiceClone.name}
                    </h3>
                    {voiceClone.description && (
                      <p className="line-clamp-1 text-xs text-muted-foreground sm:text-sm">
                        {voiceClone.description}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground sm:gap-4">
                      <span className="flex items-center gap-1">
                        <Clock className="size-3" />
                        <span className="hidden sm:inline">
                          {formatDate(voiceClone.created_at)}
                        </span>
                        <span className="sm:hidden">
                          {formatDate(voiceClone.created_at).replace(
                            /\d{4}$/,
                            "",
                          )}
                        </span>
                      </span>
                      <span className="flex items-center gap-1">
                        <FileAudio className="size-3" />
                        {voiceClone.total_files} file
                        {voiceClone.total_files !== 1 ? "s" : ""}
                      </span>
                      <span className="flex items-center gap-1">
                        <HardDrive className="size-3" />
                        {formatFileSize(voiceClone.total_size_bytes)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Delete Button with Confirmation Dialog */}
                <AlertDialog
                  open={dialogOpen === voiceClone.voice_id}
                  onOpenChange={(open) =>
                    setDialogOpen(open ? voiceClone.voice_id : null)
                  }
                >
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="shrink-0 text-muted-foreground hover:text-destructive"
                      disabled={
                        isDeleting && deletingVoiceId === voiceClone.voice_id
                      }
                      aria-label={`Delete voice clone "${voiceClone.name}"`}
                    >
                      {isDeleting && deletingVoiceId === voiceClone.voice_id ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Trash2 className="size-4" />
                      )}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete Voice Clone</AlertDialogTitle>
                      <AlertDialogDescription>
                        Are you sure you want to delete &quot;{voiceClone.name}
                        &quot;? This action cannot be undone. The voice clone
                        will be permanently removed from your account.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => handleDelete(voiceClone)}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
