"use client";

import { motion } from "motion/react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Mic, Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { useVoiceClones, type VoiceClone } from "@/lib/queries/voice-clone";

interface VoiceTabProps {
  voiceId: string | undefined;
  onChange: (voiceId: string) => void;
  voiceEnabled: boolean;
  onVoiceEnabledChange: (enabled: boolean) => void;
}

/**
 * Voice Tab
 * Allows enabling/disabling voice agent and selection of voice clone
 */
export function VoiceTab({
  voiceId,
  onChange,
  voiceEnabled,
  onVoiceEnabledChange,
}: VoiceTabProps) {
  const { data: user } = useUserMe();
  const { data: voiceClones, isLoading, error } = useVoiceClones(user?.id);

  const hasVoices = voiceClones && voiceClones.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="space-y-4"
    >
      {/* Voice Agent Toggle */}
      <Card>
        <CardContent className="px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="voice-enabled" className="text-sm font-medium">
                Enable Voice Agent
              </Label>
              <p className="text-xs text-muted-foreground">
                When enabled, visitors can talk to your persona using voice
                chat. When disabled, only text chat is available.
              </p>
            </div>
            <Switch
              id="voice-enabled"
              checked={voiceEnabled}
              onCheckedChange={onVoiceEnabledChange}
            />
          </div>
        </CardContent>
      </Card>

      {/* Voice Clone Selection - only shown when voice is enabled */}
      {voiceEnabled && (
        <Card className={cn(!voiceEnabled && "opacity-50 pointer-events-none")}>
          {hasVoices && (
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Mic className="size-4" />
                Select Voice
              </CardTitle>
              <CardDescription>
                Choose between the default AI voice or your custom voice clone
                {voiceClones.length > 1 ? "s" : ""}.
              </CardDescription>
            </CardHeader>
          )}
          <CardContent className="px-4 py-3">
            {isLoading ? (
              /* Loading state */
              <div className="flex items-center justify-center py-8">
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              /* Error state */
              <div className="text-center py-8">
                <p className="text-sm text-destructive">
                  Failed to load voice clones
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {error.message}
                </p>
              </div>
            ) : hasVoices ? (
              /* Show selectable list: Default + Custom voices */
              <div className="space-y-2">
                {/* Default Voice Card */}
                <div
                  onClick={() => onChange(undefined as unknown as string)}
                  className={cn(
                    "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all",
                    !voiceId
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border hover:border-primary/50 hover:bg-muted/50",
                  )}
                >
                  <div
                    className={cn(
                      "flex size-10 shrink-0 items-center justify-center rounded-full",
                      !voiceId ? "bg-primary/10" : "bg-muted",
                    )}
                  >
                    <Mic
                      className={cn(
                        "size-5",
                        !voiceId ? "text-primary" : "text-muted-foreground",
                      )}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      Default Voice
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Standard AI voice
                    </p>
                  </div>
                  {!voiceId && (
                    <Check className="size-5 text-primary shrink-0" />
                  )}
                </div>

                {/* User's Voice Clones */}
                {voiceClones.map((voice: VoiceClone) => (
                  <div
                    key={voice.voice_id}
                    onClick={() => onChange(voice.voice_id)}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all",
                      voiceId === voice.voice_id
                        ? "border-primary bg-primary/5 shadow-sm"
                        : "border-border hover:border-primary/50 hover:bg-muted/50",
                    )}
                  >
                    <div
                      className={cn(
                        "flex size-10 shrink-0 items-center justify-center rounded-full",
                        voiceId === voice.voice_id
                          ? "bg-primary/10"
                          : "bg-muted",
                      )}
                    >
                      <Mic
                        className={cn(
                          "size-5",
                          voiceId === voice.voice_id
                            ? "text-primary"
                            : "text-muted-foreground",
                        )}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {voice.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {voice.description || "Voice clone"}
                      </p>
                    </div>
                    {voiceId === voice.voice_id && (
                      <Check className="size-5 text-primary shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            ) : (
              /* No voices: Show empty state */
              <div className="text-center py-8 text-muted-foreground">
                <Mic className="size-12 mx-auto mb-3 opacity-50" />
                <p>No voice clones available</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
}
