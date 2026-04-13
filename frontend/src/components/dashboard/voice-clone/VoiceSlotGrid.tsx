"use client";

import { useState } from "react";
import {
  Mic,
  Upload,
  Music2,
  Trash2,
  Loader2,
  Plus,
  CheckCircle2,
} from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  useDeleteVoiceClone,
  type VoiceClone,
} from "@/lib/queries/voice-clone";

interface VoiceSlotGridProps {
  voiceClones: VoiceClone[];
  voiceCloneLimit: number;
  isUnlimited: boolean;
  onRecordClick: () => void;
  onUploadClick: () => void;
}

function formatDate(dateString: string) {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Simple single voice card for Free/Pro tiers (1 slot)
function SingleVoiceCard({
  voice,
  onRecordClick,
  onUploadClick,
}: {
  voice: VoiceClone | null;
  onRecordClick: () => void;
  onUploadClick: () => void;
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const { mutate: deleteVoiceClone, isPending: isDeleting } =
    useDeleteVoiceClone();

  const handleDelete = () => {
    if (!voice) return;
    setDialogOpen(false);

    deleteVoiceClone(
      { voice_id: voice.voice_id },
      {
        onSuccess: () => {
          toast.success("Voice clone deleted", {
            description: `"${voice.name}" has been permanently deleted.`,
          });
        },
        onError: (error) => {
          toast.error("Failed to delete voice clone", {
            description: error.message,
          });
        },
      },
    );
  };

  if (voice) {
    // Has voice - show filled state
    return (
      <div className="rounded-xl border-2 border-green-200 bg-gradient-to-br from-green-50 to-white p-6">
        <div className="flex items-start gap-4">
          <div className="flex size-14 shrink-0 items-center justify-center rounded-xl bg-green-100">
            <Music2 className="size-7 text-green-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-lg font-semibold truncate">{voice.name}</h3>
              <Badge
                variant="secondary"
                className="shrink-0 bg-green-100 text-green-700 border-0 gap-1"
              >
                <CheckCircle2 className="size-3" />
                Active
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              Created {formatDate(voice.created_at)}
            </p>
            <AlertDialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <AlertDialogTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-muted-foreground hover:text-destructive hover:border-destructive hover:bg-destructive/10"
                  disabled={isDeleting}
                >
                  {isDeleting ? (
                    <Loader2 className="size-4 animate-spin mr-2" />
                  ) : (
                    <Trash2 className="size-4 mr-2" />
                  )}
                  {isDeleting ? "Deleting..." : "Delete Voice"}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete Voice Clone</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to delete &quot;{voice.name}&quot;?
                    This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDelete}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </div>
    );
  }

  // No voice - show empty state with actions
  return (
    <div className="rounded-xl border-2 border-dashed border-muted bg-card p-6 transition-all hover:border-primary/50 hover:bg-primary/5">
      <div className="flex items-start gap-4">
        <div className="flex size-14 shrink-0 items-center justify-center rounded-xl bg-primary/10">
          <Plus className="size-7 text-primary" />
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold mb-1">
            Create Your Voice Clone
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Record a sample or upload an audio file to clone your voice
          </p>
          <div className="flex gap-2">
            <Button variant="default" className="gap-2" onClick={onRecordClick}>
              <Mic className="size-4" />
              Record Voice
            </Button>
            <Button variant="outline" className="gap-2" onClick={onUploadClick}>
              <Upload className="size-4" />
              Upload Audio
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Multi-slot list item for Business tier
function MultiSlotVoiceItem({
  voice,
  slotNumber,
  onRecordClick,
  onUploadClick,
}: {
  voice: VoiceClone | null;
  slotNumber: number;
  onRecordClick: () => void;
  onUploadClick: () => void;
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const { mutate: deleteVoiceClone, isPending: isDeleting } =
    useDeleteVoiceClone();

  const handleDelete = () => {
    if (!voice) return;
    setDialogOpen(false);

    deleteVoiceClone(
      { voice_id: voice.voice_id },
      {
        onSuccess: () => {
          toast.success("Voice clone deleted", {
            description: `"${voice.name}" has been permanently deleted.`,
          });
        },
        onError: (error) => {
          toast.error("Failed to delete voice clone", {
            description: error.message,
          });
        },
      },
    );
  };

  if (voice) {
    // Filled slot
    return (
      <div className="flex items-center gap-4 rounded-xl border bg-card p-4 transition-all hover:shadow-sm">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-green-100 text-sm font-semibold text-green-700">
          {slotNumber}
        </div>
        <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-green-50">
          <Music2 className="size-6 text-green-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold truncate">{voice.name}</h3>
            <Badge
              variant="secondary"
              className="shrink-0 bg-green-100 text-green-700 border-0 gap-1"
            >
              <CheckCircle2 className="size-3" />
              Active
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Created {formatDate(voice.created_at)}
          </p>
        </div>
        <AlertDialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <AlertDialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0 size-9 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
              disabled={isDeleting}
            >
              {isDeleting ? (
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
                Are you sure you want to delete &quot;{voice.name}&quot;? This
                action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDelete}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }

  // Empty slot
  return (
    <div className="flex items-center gap-4 rounded-xl border border-dashed bg-card p-4 transition-all hover:border-primary/50 hover:bg-primary/5">
      <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
        {slotNumber}
      </div>
      <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
        <Plus className="size-6 text-primary" />
      </div>
      <div className="flex-1">
        <h3 className="font-medium">Add Voice Clone</h3>
        <p className="text-sm text-muted-foreground">
          Record or upload your voice
        </p>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button
          variant="default"
          size="sm"
          className="gap-1.5"
          onClick={onRecordClick}
        >
          <Mic className="size-4" />
          Record
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5"
          onClick={onUploadClick}
        >
          <Upload className="size-4" />
          Upload
        </Button>
      </div>
    </div>
  );
}

// Unlimited tier - simple list with add button
function UnlimitedVoiceList({
  voiceClones,
  onRecordClick,
  onUploadClick,
}: {
  voiceClones: VoiceClone[];
  onRecordClick: () => void;
  onUploadClick: () => void;
}) {
  const [dialogOpen, setDialogOpen] = useState<string | null>(null);
  const { mutate: deleteVoiceClone, isPending: isDeleting } =
    useDeleteVoiceClone();

  const handleDelete = (voice: VoiceClone) => {
    setDialogOpen(null);

    deleteVoiceClone(
      { voice_id: voice.voice_id },
      {
        onSuccess: () => {
          toast.success("Voice clone deleted", {
            description: `"${voice.name}" has been permanently deleted.`,
          });
        },
        onError: (error) => {
          toast.error("Failed to delete voice clone", {
            description: error.message,
          });
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Your Voice Clones</h2>
          <p className="text-sm text-muted-foreground">
            {voiceClones.length} voice clone
            {voiceClones.length !== 1 ? "s" : ""} created
          </p>
        </div>
        <Badge variant="secondary" className="text-xs font-medium">
          Unlimited
        </Badge>
      </div>

      <div className="space-y-3">
        {voiceClones.map((voice) => (
          <div
            key={voice.id}
            className="flex items-center gap-4 rounded-xl border bg-card p-4 transition-all hover:shadow-sm"
          >
            <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-green-50">
              <Music2 className="size-6 text-green-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold truncate">{voice.name}</h3>
                <Badge
                  variant="secondary"
                  className="shrink-0 bg-green-100 text-green-700 border-0 gap-1"
                >
                  <CheckCircle2 className="size-3" />
                  Active
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Created {formatDate(voice.created_at)}
              </p>
            </div>
            <AlertDialog
              open={dialogOpen === voice.id}
              onOpenChange={(open) => setDialogOpen(open ? voice.id : null)}
            >
              <AlertDialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0 size-9 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  disabled={isDeleting}
                >
                  {isDeleting && dialogOpen === voice.id ? (
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
                    Are you sure you want to delete &quot;{voice.name}&quot;?
                    This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => handleDelete(voice)}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        ))}

        {/* Add new voice */}
        <div className="flex items-center gap-4 rounded-xl border border-dashed bg-card p-4 transition-all hover:border-primary/50 hover:bg-primary/5">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
            <Plus className="size-6 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="font-medium">Add Another Voice Clone</h3>
            <p className="text-sm text-muted-foreground">
              Create additional voice clones for different personas
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button
              variant="default"
              size="sm"
              className="gap-1.5"
              onClick={onRecordClick}
            >
              <Mic className="size-4" />
              Record
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={onUploadClick}
            >
              <Upload className="size-4" />
              Upload
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function VoiceSlotGrid({
  voiceClones,
  voiceCloneLimit,
  isUnlimited,
  onRecordClick,
  onUploadClick,
}: VoiceSlotGridProps) {
  const currentCount = voiceClones.length;

  // Unlimited tier (Enterprise) - simple list with add button
  if (isUnlimited) {
    return (
      <UnlimitedVoiceList
        voiceClones={voiceClones}
        onRecordClick={onRecordClick}
        onUploadClick={onUploadClick}
      />
    );
  }

  // Single slot tiers (Free/Pro) - clean single card UI
  if (voiceCloneLimit === 1) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Your Voice Clone</h2>
          <p className="text-sm text-muted-foreground">
            {currentCount === 0
              ? "Create your personalized voice clone"
              : "Your custom voice is ready to use"}
          </p>
        </div>
        <SingleVoiceCard
          voice={voiceClones[0] || null}
          onRecordClick={onRecordClick}
          onUploadClick={onUploadClick}
        />
      </div>
    );
  }

  // Multi-slot tiers (Business: 3 slots) - list view with slot numbers
  const slots = [];
  for (let i = 0; i < voiceCloneLimit; i++) {
    slots.push(voiceClones[i] || null);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Your Voice Clones</h2>
          <p className="text-sm text-muted-foreground">
            {currentCount} of {voiceCloneLimit} slots used
          </p>
        </div>
        <Badge variant="outline" className="text-xs font-medium">
          {voiceCloneLimit - currentCount} slot
          {voiceCloneLimit - currentCount !== 1 ? "s" : ""} available
        </Badge>
      </div>

      <div className="space-y-3">
        {slots.map((voice, index) => (
          <MultiSlotVoiceItem
            key={voice?.id || `empty-${index}`}
            voice={voice}
            slotNumber={index + 1}
            onRecordClick={onRecordClick}
            onUploadClick={onUploadClick}
          />
        ))}
      </div>
    </div>
  );
}
