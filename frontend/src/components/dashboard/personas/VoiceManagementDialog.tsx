"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Mic, Loader2 } from "lucide-react";
import { useVoiceClones } from "@/lib/queries/voice-clone";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { useUpdateVoiceSettings } from "@/lib/queries/persona";
import { toast } from "sonner";

interface VoiceManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  personaId: string;
  personaName: string; // persona_name (slug) for API calls
  personaDisplayName: string; // Display name for UI
  username: string;
  currentVoiceId?: string;
}

export function VoiceManagementDialog({
  open,
  onOpenChange,
  personaId,
  personaName: _personaName,
  personaDisplayName,
  username: _username,
  currentVoiceId,
}: VoiceManagementDialogProps) {
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>(
    currentVoiceId || "",
  );

  const { data: user } = useUserMe();
  const { data: voiceClones, isLoading: voiceClonesLoading } = useVoiceClones(
    user?.id,
  );
  const updateVoiceSettingsMutation = useUpdateVoiceSettings(personaId);

  // Update local state when currentVoiceId changes or dialog opens
  useEffect(() => {
    if (open) {
      setSelectedVoiceId(currentVoiceId || "");
    }
  }, [open, currentVoiceId]);

  const handleSave = () => {
    if (!selectedVoiceId) {
      toast.error("Please select a voice");
      return;
    }

    updateVoiceSettingsMutation.mutate(
      { voice_id: selectedVoiceId },
      {
        onSuccess: () => {
          toast.success("Voice updated successfully!");
          onOpenChange(false);
        },
        onError: (error: Error) => {
          toast.error("Failed to update voice", {
            description: error.message,
          });
        },
      },
    );
  };

  const handleRemoveVoice = () => {
    updateVoiceSettingsMutation.mutate(
      { voice_id: "" },
      {
        onSuccess: () => {
          toast.success("Voice removed, using default voice");
          onOpenChange(false);
        },
        onError: (error: Error) => {
          toast.error("Failed to remove voice", {
            description: error.message,
          });
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] shadow-2xl">
        <DialogHeader>
          <DialogTitle>Manage Voice</DialogTitle>
          <DialogDescription>
            Select which voice to use for {personaDisplayName}
          </DialogDescription>
        </DialogHeader>

        {voiceClonesLoading ? (
          <div className="space-y-3 py-4">
            {[1, 2].map((i) => (
              <Skeleton key={i} className="h-16 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="space-y-4 py-4">
            {/* Voice Selection */}
            <div className="space-y-2">
              <Select
                value={selectedVoiceId}
                onValueChange={setSelectedVoiceId}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select voice" />
                </SelectTrigger>
                <SelectContent>
                  {voiceClones && voiceClones.length > 0 ? (
                    voiceClones.map((voice) => (
                      <SelectItem key={voice.id} value={voice.voice_id}>
                        <div className="flex items-center gap-2">
                          <Mic className="size-4 text-ai-brown 600" />
                          <span>{voice.name}</span>
                        </div>
                      </SelectItem>
                    ))
                  ) : (
                    <SelectItem value="no-voices" disabled>
                      No voices created yet
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>

            {/* No Voices Message */}
            {(!voiceClones || voiceClones.length === 0) && (
              <div className="rounded-lg border border-dashed p-4 text-center">
                <Mic className="mx-auto mb-2 size-8 text-muted-foreground" />
                <p className="text-sm font-medium text-muted-foreground mb-1">
                  No voices yet
                </p>
                <p className="text-xs text-muted-foreground">
                  Visit Voice Clone page to create your voice
                </p>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={updateVoiceSettingsMutation.isPending}
          >
            Cancel
          </Button>
          {currentVoiceId && (
            <Button
              variant="outline"
              onClick={handleRemoveVoice}
              disabled={updateVoiceSettingsMutation.isPending}
              className="text-muted-foreground"
            >
              {updateVoiceSettingsMutation.isPending && (
                <Loader2 className="mr-2 size-4 animate-spin" />
              )}
              Use Default Voice
            </Button>
          )}
          <Button
            onClick={handleSave}
            disabled={
              !selectedVoiceId ||
              selectedVoiceId === currentVoiceId ||
              updateVoiceSettingsMutation.isPending
            }
          >
            {updateVoiceSettingsMutation.isPending && (
              <Loader2 className="mr-2 size-4 animate-spin" />
            )}
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
