"use client";

import { useState } from "react";
import { Youtube, Loader2, AlertCircle, Lock, Crown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useYouTubeUpload } from "@/lib/queries/knowledge/useUploadMutations";
import { useTierLimitCheck } from "@/lib/queries/tier";

interface YouTubeUploadFormProps {
  userId: string;
  personaId?: string;
}

export function YouTubeUploadForm({
  userId,
  personaId,
}: YouTubeUploadFormProps) {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const { mutate: uploadYouTube, isPending } = useYouTubeUpload();
  const { usage, hasReachedLimit, canAccessYouTube, isFreeTier } =
    useTierLimitCheck();

  const youtubeAccess = canAccessYouTube();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!youtubeUrl.trim() || !youtubeAccess.allowed) return;

    uploadYouTube(
      {
        youtube_url: youtubeUrl.trim(),
        user_id: userId,
        persona_id: personaId,
      },
      {
        onSuccess: () => {
          setYoutubeUrl("");
        },
      },
    );
  };

  const isValidYouTubeUrl = (url: string) => {
    if (!url) return true; // Don't show error for empty
    const youtubeRegex =
      /^(https?:\/\/)?(www\.|m\.)?(youtube\.com\/(watch\?v=|v\/|embed\/|shorts\/)|youtu\.be\/)[\w-]+(&[\w=-]+)*/;
    return youtubeRegex.test(url);
  };

  const isValid = isValidYouTubeUrl(youtubeUrl);
  const limitReached = hasReachedLimit("youtube");

  // Show premium upsell for free tier users
  if (isFreeTier) {
    return (
      <div className="space-y-4">
        {/* Premium Feature Banner */}
        <div className="relative overflow-hidden rounded-lg border-2 border-dashed border-yellow-300 bg-linear-to-br from-yellow-50 to-orange-50 p-6">
          <div className="absolute -right-4 -top-4 size-24 rounded-full bg-yellow-200/30 blur-2xl" />
          <div className="absolute -bottom-4 -left-4 size-24 rounded-full bg-orange-200/30 blur-2xl" />

          <div className="relative space-y-4">
            {/* Icon and Badge */}
            <div className="flex items-center gap-3">
              <div className="flex size-12 items-center justify-center rounded-xl bg-linear-to-br from-yellow-400 to-orange-400 shadow-lg">
                <Crown className="size-6 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-slate-900">Pro Feature</h3>
                  <span className="rounded-full bg-linear-to-r from-yellow-400 to-orange-400 px-2 py-0.5 text-xs font-medium text-white">
                    PRO
                  </span>
                </div>
                <p className="text-sm text-slate-600">
                  YouTube import is available on Pro and above
                </p>
              </div>
            </div>

            {/* Feature Description */}
            <div className="rounded-lg bg-white/60 p-4">
              <p className="text-sm text-slate-700">
                Import transcripts from YouTube videos to train your AI clone.
                Extract valuable content from interviews, podcasts, tutorials,
                and more.
              </p>
            </div>

            {/* Locked Input Preview */}
            <div className="space-y-2 opacity-50">
              <Label
                htmlFor="youtube-url-disabled"
                className="flex items-center gap-2 text-slate-500"
              >
                <Youtube className="size-4" />
                YouTube Video URL
                <Lock className="size-3" />
              </Label>
              <Input
                id="youtube-url-disabled"
                type="url"
                placeholder="https://www.youtube.com/watch?v=..."
                disabled
                className="cursor-not-allowed bg-slate-100"
              />
            </div>

            {/* Upgrade CTA */}
            <Button
              className="w-full bg-linear-to-r from-yellow-500 to-orange-500 text-white hover:from-yellow-600 hover:to-orange-600"
              onClick={() => {
                // Navigate to pricing/upgrade page
                window.location.href = "/pricing";
              }}
            >
              <Crown className="mr-2 size-4" />
              Upgrade to Pro
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {limitReached && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>
            YouTube video limit reached ({usage?.youtube.videos.limit} videos).
            Please upgrade your plan to import more videos.
          </AlertDescription>
        </Alert>
      )}

      {usage && usage.youtube.videos.percentage >= 80 && !limitReached && (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertDescription>
            You&apos;ve used {usage.youtube.videos.percentage}% of your YouTube
            video limit ({usage.youtube.videos.used}/
            {usage.youtube.videos.limit} videos). Consider upgrading your plan.
          </AlertDescription>
        </Alert>
      )}

      {usage && (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertDescription>
            Video length limit: {usage.youtube.max_video_duration_minutes}{" "}
            minutes • Total duration remaining:{" "}
            {(
              usage.youtube.duration.limit_hours -
              usage.youtube.duration.used_hours
            ).toFixed(1)}{" "}
            hours
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Label htmlFor="youtube-url" className="flex items-center gap-2">
          <Youtube className="size-4" />
          YouTube Video URL
        </Label>
        <Input
          id="youtube-url"
          type="url"
          placeholder="https://www.youtube.com/watch?v=..."
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          disabled={isPending}
          className={!isValid ? "border-red-500" : ""}
        />
        {!isValid && youtubeUrl && (
          <p className="text-sm text-red-500">
            Please enter a valid YouTube URL
          </p>
        )}
        <p className="text-sm text-muted-foreground">
          We&apos;ll extract the transcript and add it to your knowledge base
        </p>
      </div>

      <Button
        type="submit"
        disabled={isPending || !youtubeUrl.trim() || !isValid || limitReached}
        className="w-full"
      >
        {isPending ? (
          <>
            <Loader2 className="mr-2 size-4 animate-spin" />
            Processing...
          </>
        ) : limitReached ? (
          "Limit Reached"
        ) : (
          <>
            <Youtube className="mr-2 size-4" />
            Add YouTube Video
          </>
        )}
      </Button>
    </form>
  );
}
