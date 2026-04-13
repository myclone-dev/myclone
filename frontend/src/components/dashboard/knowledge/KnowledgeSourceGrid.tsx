"use client";

import { useState } from "react";
import {
  Linkedin,
  Twitter,
  Globe,
  FileText,
  Plus,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Sparkles,
  Music,
  Video,
  Youtube,
  TextCursorInput,
  Crown,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import type { ScrapingJob } from "@/lib/queries/knowledge";
import { useKnowledgeLibrary } from "@/lib/queries/knowledge";
import { useTierLimitCheck } from "@/lib/queries/tier";
import { LinkedInUploadForm } from "./LinkedInUploadForm";
import { TwitterUploadForm } from "./TwitterUploadForm";
import { WebsiteUploadForm } from "./WebsiteUploadForm";
import { DocumentUploadForm } from "./DocumentUploadForm";
import { AudioUploadForm } from "./AudioUploadForm";
import { VideoUploadForm } from "./VideoUploadForm";
import { YouTubeUploadForm } from "./YoutubeUploadForm";
import { RawTextUploadForm } from "./RawTextUploadForm";

interface KnowledgeSourceGridProps {
  userId: string;
  jobs: ScrapingJob[];
}

type SourceType =
  | "linkedin"
  | "twitter"
  | "website"
  | "documents"
  | "text"
  | "audio"
  | "video"
  | "youtube"
  | null;

export function KnowledgeSourceGrid({
  userId,
  jobs,
}: KnowledgeSourceGridProps) {
  const [selectedSource, setSelectedSource] = useState<SourceType>(null);
  const { data: library } = useKnowledgeLibrary(userId);
  const { isFreeTier } = useTierLimitCheck();

  const sources = [
    {
      type: "linkedin" as const,
      title: "LinkedIn",
      description: "Professional profile, posts & experience",
      icon: Linkedin,
      iconColor: "text-linkedin",
      bgColor: "bg-linkedin/10",
      proOnly: false,
    },
    {
      type: "twitter" as const,
      title: "Twitter / X",
      description: "Tweets and social presence",
      icon: Twitter,
      iconColor: "text-twitter",
      bgColor: "bg-twitter/10",
      proOnly: false,
    },
    {
      type: "website" as const,
      title: "Website",
      description: "Blog posts, articles & portfolio",
      icon: Globe,
      iconColor: "text-website",
      bgColor: "bg-website/10",
      proOnly: false,
    },
    {
      type: "documents" as const,
      title: "Documents",
      description: "PDF, Word, PowerPoint, Excel & more",
      icon: FileText,
      iconColor: "text-document",
      bgColor: "bg-document/10",
      proOnly: false,
    },
    {
      type: "text" as const,
      title: "Text",
      description: "Paste meeting notes, transcripts directly",
      icon: TextCursorInput,
      iconColor: "text-purple-600",
      bgColor: "bg-purple-100",
      proOnly: false,
    },
    {
      type: "audio" as const,
      title: "Audio",
      description: "MP3, WAV, and M4A files",
      icon: Music,
      iconColor: "text-emerald-600",
      bgColor: "bg-emerald-100",
      proOnly: false,
    },
    {
      type: "video" as const,
      title: "Video",
      description: "MP4, MOV, AVI, or MKV files",
      icon: Video,
      iconColor: "text-blue-600",
      bgColor: "bg-blue-100",
      proOnly: false,
    },
    {
      type: "youtube" as const,
      title: "YouTube",
      description: "Video transcripts from YouTube",
      icon: Youtube,
      iconColor: "text-youtube",
      bgColor: "bg-youtube/10",
      proOnly: true, // YouTube is Pro+ only
    },
  ];

  // Get count of sources from the knowledge library
  const getSourceCount = (type: string): number => {
    if (!library) return 0;

    switch (type) {
      case "linkedin":
        return library.linkedin.length;
      case "twitter":
        return library.twitter.length;
      case "website":
        return library.websites.length;
      case "documents":
        // Documents include all document types (PDF, DOCX, etc.) excluding raw text
        return library.documents.filter(
          (d) => !(d as { is_raw_text_input?: boolean }).is_raw_text_input,
        ).length;
      case "text":
        // Text sources are documents with is_raw_text_input flag
        // For now, count txt files as potential raw text inputs
        return library.documents.filter((d) => d.document_type === "txt")
          .length;
      case "youtube":
        return library.youtube.length;
      case "audio":
      case "video":
        // Audio/video are stored as documents with specific types
        // For now, we'll check if there are any documents with audio/video extensions
        // This could be improved with backend support for media categorization
        return 0; // Will rely on job status for now
      default:
        return 0;
    }
  };

  const getSourceStatus = (type: string) => {
    // First check if there are active jobs (processing)
    let sourceJobs;
    if (type === "documents" || type === "text") {
      // Both documents and text use pdf source type in jobs
      sourceJobs = jobs.filter(
        (j) => j.source_type === "pdf" || j.file_type === "pdf",
      );
    } else if (type === "audio") {
      sourceJobs = jobs.filter(
        (j) => j.source_type === "audio" || j.file_type === "audio",
      );
    } else if (type === "video") {
      sourceJobs = jobs.filter(
        (j) => j.source_type === "video" || j.file_type === "video",
      );
    } else {
      sourceJobs = jobs.filter((j) => j.source_type === type);
    }

    const activeJobs = sourceJobs.filter(
      (j) =>
        j.status === "processing" ||
        j.status === "pending" ||
        j.status === "queued",
    );

    if (activeJobs.length > 0) return "processing";

    // Check actual source count from knowledge library
    const count = getSourceCount(type);
    if (count > 0) return "connected";

    // For audio/video, fall back to job history since they're not in knowledge library yet
    if (type === "audio" || type === "video") {
      const completedJobs = sourceJobs.filter((j) => j.status === "completed");
      if (completedJobs.length > 0) return "connected";
    }

    return "not-connected";
  };

  const getActionConfig = (type: string, status: string) => {
    if (status === "connected") {
      if (type === "linkedin" || type === "twitter") {
        return { text: "Refresh", icon: RefreshCw };
      }
      return { text: "Add More", icon: Plus };
    }
    return { text: "Connect", icon: Sparkles };
  };

  return (
    <>
      {/* Mobile: Horizontal scroll with compact cards */}
      <div className="sm:hidden">
        <div className="flex gap-3 overflow-x-auto pb-3 -mx-4 px-4 snap-x snap-mandatory scrollbar-hide">
          {sources.map((source) => {
            const Icon = source.icon;
            const status = getSourceStatus(source.type);
            const count = getSourceCount(source.type);
            const isProLocked = source.proOnly && isFreeTier;

            const actionConfig = getActionConfig(source.type, status);
            const ActionIcon = actionConfig.icon;

            return (
              <button
                key={source.type}
                onClick={() => setSelectedSource(source.type)}
                className={`group relative flex flex-col items-center justify-center rounded-xl border-2 p-3 text-center transition-all snap-start shrink-0 w-[140px] ${
                  isProLocked
                    ? "border-dashed border-yellow-300 bg-linear-to-br from-yellow-50/50 to-orange-50/50"
                    : status === "connected"
                      ? "border-solid border-green-200 bg-linear-to-br from-green-50 to-green-50/30"
                      : "border-dashed border-border active:border-solid active:border-primary active:bg-primary/5"
                }`}
              >
                {/* Pro Badge for locked features */}
                {isProLocked && (
                  <div className="absolute right-1.5 top-1.5">
                    <Badge className="h-5 gap-0.5 bg-linear-to-r from-yellow-400 to-orange-400 text-white border-0 font-semibold text-[10px] px-1.5">
                      <Crown className="size-2.5" />
                      PRO
                    </Badge>
                  </div>
                )}
                {/* Status Indicator */}
                {!isProLocked && status === "connected" && (
                  <div className="absolute right-1.5 top-1.5">
                    {source.type === "documents" && count > 0 ? (
                      <Badge
                        variant="secondary"
                        className="h-5 gap-0.5 bg-green-100 text-green-700 border-green-200 font-semibold text-[10px] px-1.5"
                      >
                        <CheckCircle2 className="size-2.5" />
                        {count}
                      </Badge>
                    ) : (
                      <div className="flex size-4 items-center justify-center rounded-full bg-green-100">
                        <CheckCircle2 className="size-2.5 text-green-600" />
                      </div>
                    )}
                  </div>
                )}
                {!isProLocked && status === "processing" && (
                  <div className="absolute right-1.5 top-1.5">
                    <div className="flex size-4 items-center justify-center rounded-full bg-muted">
                      <Loader2 className="size-2.5 animate-spin text-muted-foreground" />
                    </div>
                  </div>
                )}

                {/* Icon */}
                <div
                  className={`mb-2 flex size-10 items-center justify-center rounded-xl ${source.bgColor} ${isProLocked ? "opacity-60" : ""}`}
                >
                  <Icon className={`size-5 ${source.iconColor}`} />
                </div>

                {/* Content */}
                <h3
                  className={`text-xs font-semibold mb-0.5 line-clamp-1 ${isProLocked ? "text-slate-600" : ""}`}
                >
                  {source.title}
                </h3>
                <p className="text-[10px] leading-tight text-muted-foreground mb-2 line-clamp-2 min-h-6">
                  {source.description}
                </p>

                {/* CTA */}
                <div
                  className={`flex items-center gap-1 text-[10px] font-medium ${
                    isProLocked
                      ? "text-yellow-600"
                      : status === "connected"
                        ? "text-green-700"
                        : "text-ai-brown"
                  }`}
                >
                  {isProLocked ? (
                    <>
                      <Crown className="size-2.5" />
                      Upgrade
                    </>
                  ) : (
                    <>
                      <ActionIcon className="size-2.5" />
                      {actionConfig.text}
                    </>
                  )}
                </div>
              </button>
            );
          })}
        </div>
        <p className="text-[10px] text-muted-foreground text-center mt-1">
          Scroll to see more sources →
        </p>
      </div>

      {/* Desktop: Grid layout */}
      <div className="hidden sm:grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {sources.map((source) => {
          const Icon = source.icon;
          const status = getSourceStatus(source.type);
          const count = getSourceCount(source.type);
          const isProLocked = source.proOnly && isFreeTier;

          const actionConfig = getActionConfig(source.type, status);
          const ActionIcon = actionConfig.icon;

          return (
            <button
              key={source.type}
              onClick={() => setSelectedSource(source.type)}
              className={`group relative flex flex-col items-center justify-center rounded-xl border-2 p-6 md:p-8 text-center transition-all duration-300 hover:scale-[1.02] hover:shadow-lg ${
                isProLocked
                  ? "border-dashed border-yellow-300 bg-linear-to-br from-yellow-50/50 to-orange-50/50 hover:from-yellow-50 hover:to-orange-50/70"
                  : status === "connected"
                    ? "border-solid border-green-200 bg-linear-to-br from-green-50 to-green-50/30 hover:from-green-100 hover:to-green-50"
                    : "border-dashed border-border hover:border-solid hover:border-primary hover:bg-linear-to-br hover:from-primary/5 hover:to-primary/10"
              }`}
            >
              {/* Pro Badge for locked features */}
              {isProLocked && (
                <div className="absolute right-3 top-3">
                  <Badge className="h-6 gap-1 bg-linear-to-r from-yellow-400 to-orange-400 text-white border-0 font-semibold">
                    <Crown className="size-3" />
                    PRO
                  </Badge>
                </div>
              )}
              {/* Status Indicator with Count (count only for documents) */}
              {!isProLocked && status === "connected" && (
                <div className="absolute right-3 top-3">
                  {source.type === "documents" && count > 0 ? (
                    <Badge
                      variant="secondary"
                      className="h-6 gap-1 bg-green-100 text-green-700 border-green-200 font-semibold"
                    >
                      <CheckCircle2 className="size-3" />
                      {count}
                    </Badge>
                  ) : (
                    <div className="flex size-6 items-center justify-center rounded-full bg-green-100">
                      <CheckCircle2 className="size-4 text-green-600" />
                    </div>
                  )}
                </div>
              )}
              {!isProLocked && status === "processing" && (
                <div className="absolute right-3 top-3">
                  <div className="flex size-6 items-center justify-center rounded-full bg-muted">
                    <Loader2 className="size-4 animate-spin text-muted-foreground" />
                  </div>
                </div>
              )}

              {/* Icon */}
              <div
                className={`mb-4 flex size-14 md:size-16 items-center justify-center rounded-2xl transition-transform group-hover:scale-110 ${source.bgColor} ${isProLocked ? "opacity-60" : ""}`}
              >
                <Icon className={`size-7 md:size-8 ${source.iconColor}`} />
              </div>

              {/* Content */}
              <h3
                className={`mb-2 text-lg font-semibold ${isProLocked ? "text-slate-600" : ""}`}
              >
                {source.title}
              </h3>
              <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
                {source.description}
              </p>

              {/* CTA */}
              <div
                className={`flex items-center gap-2 text-sm font-medium transition-colors ${
                  isProLocked
                    ? "text-yellow-600 group-hover:text-yellow-700"
                    : status === "connected"
                      ? "text-green-700 group-hover:text-green-800"
                      : "text-ai-brown group-hover:text-ai-brown/80"
                }`}
              >
                {isProLocked ? (
                  <>
                    <Crown className="size-4" />
                    Upgrade to Pro
                  </>
                ) : (
                  <>
                    <ActionIcon className="size-4" />
                    {actionConfig.text}
                  </>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Upload Dialog */}
      <Dialog
        open={selectedSource !== null}
        onOpenChange={(open) => !open && setSelectedSource(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {selectedSource === "linkedin" && "Import from LinkedIn"}
              {selectedSource === "twitter" && "Import from Twitter"}
              {selectedSource === "website" && "Import from Website"}
              {selectedSource === "documents" && "Upload Documents"}
              {selectedSource === "text" && "Add Text Content"}
              {selectedSource === "audio" && "Upload Audio Files"}
              {selectedSource === "video" && "Upload Video Files"}
              {selectedSource === "youtube" && "Import from YouTube"}
            </DialogTitle>
            <DialogDescription>
              {selectedSource === "linkedin" &&
                "Enter your LinkedIn profile URL to import your professional data"}
              {selectedSource === "twitter" &&
                "Enter your Twitter username to import your tweets"}
              {selectedSource === "website" &&
                "Enter your website URL to scrape content"}
              {selectedSource === "documents" &&
                "Upload PDF, Word, PowerPoint, Excel, text, or markdown files to add to your knowledge base"}
              {selectedSource === "text" &&
                "Paste meeting notes, transcripts, or any text content directly without creating a file"}
              {selectedSource === "audio" &&
                "Upload MP3, WAV, or M4A audio files to add to your knowledge base"}
              {selectedSource === "video" &&
                "Upload MP4, MOV, AVI, or MKV video files to add to your knowledge base"}
              {selectedSource === "youtube" &&
                "Enter a YouTube video URL to extract its transcript"}
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4">
            {selectedSource === "linkedin" && (
              <LinkedInUploadForm
                userId={userId}
                onSuccess={() => setSelectedSource(null)}
              />
            )}
            {selectedSource === "twitter" && (
              <TwitterUploadForm
                userId={userId}
                onSuccess={() => setSelectedSource(null)}
              />
            )}
            {selectedSource === "website" && (
              <WebsiteUploadForm
                userId={userId}
                onSuccess={() => setSelectedSource(null)}
              />
            )}
            {selectedSource === "documents" && (
              <DocumentUploadForm
                userId={userId}
                onSuccess={() => setSelectedSource(null)}
              />
            )}
            {selectedSource === "text" && (
              <RawTextUploadForm
                userId={userId}
                onSuccess={() => setSelectedSource(null)}
              />
            )}
            {selectedSource === "audio" && (
              <AudioUploadForm
                userId={userId}
                onSuccess={() => setSelectedSource(null)}
              />
            )}
            {selectedSource === "video" && (
              <VideoUploadForm
                userId={userId}
                onSuccess={() => setSelectedSource(null)}
              />
            )}
            {selectedSource === "youtube" && (
              <YouTubeUploadForm userId={userId} />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
