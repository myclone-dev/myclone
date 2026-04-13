"use client";

import { useState, useRef } from "react";
import { useKnowledgeLibrary } from "@/lib/queries/knowledge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Database,
  Linkedin,
  Twitter,
  Globe,
  FileText,
  Youtube,
  Trash2,
  AlertCircle,
  ChevronDown,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { useDeleteKnowledgeSource } from "@/lib/queries/knowledge";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { cn } from "@/lib/utils";
import type { KnowledgeSource, SourceType } from "@/lib/queries/knowledge";

interface KnowledgeLibraryViewProps {
  userId: string;
}

const sourceConfig = {
  linkedin: {
    icon: Linkedin,
    color: "text-linkedin",
    bg: "bg-linkedin/10",
    hoverBg: "hover:bg-linkedin/20",
    label: "LinkedIn",
  },
  twitter: {
    icon: Twitter,
    color: "text-twitter",
    bg: "bg-twitter/10",
    hoverBg: "hover:bg-twitter/20",
    label: "Twitter",
  },
  website: {
    icon: Globe,
    color: "text-website",
    bg: "bg-website/10",
    hoverBg: "hover:bg-website/20",
    label: "Website",
  },
  document: {
    icon: FileText,
    color: "text-document",
    bg: "bg-document/10",
    hoverBg: "hover:bg-document/20",
    label: "Document",
  },
  youtube: {
    icon: Youtube,
    color: "text-youtube",
    bg: "bg-youtube/10",
    hoverBg: "hover:bg-youtube/20",
    label: "YouTube",
  },
};

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function getSourceMeta(source: KnowledgeSource): string {
  switch (source.type) {
    case "linkedin":
      return `${source.posts_count} posts`;
    case "twitter":
      return `${source.tweets_count} tweets`;
    case "website":
      return `${source.pages_crawled} pages`;
    case "document":
      return source.document_type.toUpperCase();
    case "youtube":
      return source.duration_seconds
        ? `${Math.floor(source.duration_seconds / 60)}m`
        : "Video";
    default:
      return "";
  }
}

interface KnowledgeSourceRowProps {
  source: KnowledgeSource;
}

function KnowledgeSourceRow({ source }: KnowledgeSourceRowProps) {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [swipeOffset, setSwipeOffset] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);
  const touchStartX = useRef(0);
  const touchStartY = useRef(0);
  const isSwipingHorizontal = useRef<boolean | null>(null);
  const deleteSource = useDeleteKnowledgeSource();

  const config = sourceConfig[source.type];
  const Icon = config.icon;

  // Swipe threshold in pixels - DELETE_THRESHOLD determines when delete action triggers
  const DELETE_THRESHOLD = 120;

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    touchStartY.current = e.touches[0].clientY;
    isSwipingHorizontal.current = null;
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    const currentX = e.touches[0].clientX;
    const currentY = e.touches[0].clientY;
    const diffX = touchStartX.current - currentX;
    const diffY = Math.abs(touchStartY.current - currentY);

    // Determine swipe direction on first significant movement
    if (
      isSwipingHorizontal.current === null &&
      (Math.abs(diffX) > 10 || diffY > 10)
    ) {
      isSwipingHorizontal.current = Math.abs(diffX) > diffY;
    }

    // Only handle horizontal swipes (left swipe to reveal delete)
    if (isSwipingHorizontal.current && diffX > 0) {
      setSwipeOffset(Math.min(diffX, DELETE_THRESHOLD));
    }
  };

  const handleTouchEnd = () => {
    if (swipeOffset > DELETE_THRESHOLD - 20) {
      // Trigger delete dialog
      setDeleteDialogOpen(true);
    }
    // Reset swipe
    setSwipeOffset(0);
    isSwipingHorizontal.current = null;
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    trackDashboardOperation("knowledge_source_delete", "started", {
      sourceType: source.type,
      sourceId: source.id,
      sourceName: source.display_name,
    });

    try {
      const result = await deleteSource.mutateAsync({
        sourceType: source.type,
        sourceId: source.id,
      });

      trackDashboardOperation("knowledge_source_delete", "success", {
        sourceType: source.type,
        sourceId: source.id,
        embeddingsDeleted: result.embeddings_deleted,
        personasAffected: result.personas_affected,
      });

      toast.success(result.message || "Knowledge source deleted", {
        description:
          result.personas_affected > 0
            ? `Removed from ${result.personas_affected} persona(s)`
            : undefined,
      });
      setDeleteDialogOpen(false);
    } catch (error) {
      const err = error as {
        response?: { data?: { detail?: string } };
        message?: string;
      };

      trackDashboardOperation("knowledge_source_delete", "error", {
        sourceType: source.type,
        sourceId: source.id,
        error: err.response?.data?.detail || err.message,
      });

      toast.error("Failed to delete", {
        description: err.response?.data?.detail || err.message,
      });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <div className="relative overflow-hidden">
        {/* Delete action background (revealed on swipe) - Mobile only */}
        <div
          className={cn(
            "absolute inset-y-0 right-0 flex items-center justify-end bg-destructive px-4 md:hidden",
            swipeOffset > 0 ? "opacity-100" : "opacity-0",
          )}
          style={{ width: swipeOffset }}
        >
          <Trash2 className="size-5 text-white" />
        </div>

        {/* Main row content */}
        <div
          className={cn(
            "group flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-muted/50 transition-all",
            "sm:gap-3 sm:px-3 sm:py-2.5",
          )}
          style={{
            transform: `translateX(-${swipeOffset}px)`,
            transition: swipeOffset === 0 ? "transform 0.2s ease-out" : "none",
          }}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        >
          {/* Icon - Smaller on mobile */}
          <div
            className={cn(
              "flex shrink-0 items-center justify-center rounded-md",
              "size-7 sm:size-8",
              config.bg,
            )}
          >
            <Icon className={cn("size-3.5 sm:size-4", config.color)} />
          </div>

          {/* Name & Meta */}
          <div className="flex-1 min-w-0">
            <p className="font-medium text-xs sm:text-sm truncate leading-tight">
              {source.display_name}
            </p>
            <p className="text-[10px] sm:text-xs text-muted-foreground">
              {getSourceMeta(source)}
            </p>
          </div>

          {/* Date - Hidden on mobile */}
          <span className="text-xs text-muted-foreground hidden md:block">
            {formatDate(source.created_at)}
          </span>

          {/* Delete Button - Larger touch target, hidden on mobile (use swipe instead) */}
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              "shrink-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10",
              "hidden sm:flex size-8",
            )}
            onClick={() => setDeleteDialogOpen(true)}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertCircle className="size-5 text-destructive" />
              Delete Knowledge Source?
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <p>
                  This will permanently delete{" "}
                  <strong className="text-foreground">
                    {source.display_name}
                  </strong>{" "}
                  and all its data.
                </p>
                {source.used_by_personas_count > 0 && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                    <AlertCircle className="size-4 mt-0.5 shrink-0" />
                    <span>
                      This source is used by {source.used_by_personas_count}{" "}
                      persona(s) and will be detached from all of them.
                    </span>
                  </div>
                )}
                <p className="text-xs font-medium text-foreground">
                  This action cannot be undone.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteSource.isPending || isDeleting}
            >
              {deleteSource.isPending || isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export function KnowledgeLibraryView({ userId }: KnowledgeLibraryViewProps) {
  const { data: library, isLoading } = useKnowledgeLibrary(userId);
  const [isExpanded, setIsExpanded] = useState(false); // Collapsed by default

  if (isLoading) {
    return <Skeleton className="h-20 rounded-xl" />;
  }

  // Empty state - show encouraging message
  if (!library || library.total_sources === 0) {
    return (
      <div className="rounded-xl border border-dashed bg-gradient-to-br from-muted/30 to-muted/10 p-6">
        <div className="flex items-center gap-4">
          <div className="flex size-12 items-center justify-center rounded-full bg-primary/10">
            <Sparkles className="size-6 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold">Build Your Knowledge Base</h3>
            <p className="text-sm text-muted-foreground">
              Add your first data source below to train your AI clone
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Group by type for display
  const sourcesByType: Record<SourceType, KnowledgeSource[]> = {
    linkedin: library.linkedin,
    twitter: library.twitter,
    website: library.websites,
    document: library.documents,
    youtube: library.youtube,
  };

  return (
    <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
      <div className="rounded-xl border bg-card overflow-hidden">
        {/* Stats Header - Always Visible */}
        <CollapsibleTrigger asChild>
          <button className="w-full p-3 sm:p-4 flex items-center gap-3 sm:gap-4 hover:bg-muted/30 transition-colors text-left">
            {/* Main Stats */}
            <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-0">
              <div className="flex size-8 sm:size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <Database className="size-4 sm:size-5 text-primary" />
              </div>
              <div className="min-w-0">
                <span className="font-semibold text-sm sm:text-base">
                  {library.total_sources} Source
                  {library.total_sources !== 1 ? "s" : ""}
                </span>
                <p className="text-[10px] sm:text-xs text-muted-foreground truncate">
                  Click to manage your knowledge sources
                </p>
              </div>
            </div>

            {/* Source Type Pills - Hidden on mobile */}
            <div className="hidden md:flex items-center gap-1.5 justify-end mr-2">
              {library.linkedin.length > 0 && (
                <div
                  className={`flex items-center gap-1 px-2 py-1 rounded-md ${sourceConfig.linkedin.bg}`}
                >
                  <Linkedin
                    className={`size-3.5 ${sourceConfig.linkedin.color}`}
                  />
                  <span className="text-xs font-medium">
                    {library.linkedin.length}
                  </span>
                </div>
              )}
              {library.twitter.length > 0 && (
                <div
                  className={`flex items-center gap-1 px-2 py-1 rounded-md ${sourceConfig.twitter.bg}`}
                >
                  <Twitter
                    className={`size-3.5 ${sourceConfig.twitter.color}`}
                  />
                  <span className="text-xs font-medium">
                    {library.twitter.length}
                  </span>
                </div>
              )}
              {library.websites.length > 0 && (
                <div
                  className={`flex items-center gap-1 px-2 py-1 rounded-md ${sourceConfig.website.bg}`}
                >
                  <Globe className={`size-3.5 ${sourceConfig.website.color}`} />
                  <span className="text-xs font-medium">
                    {library.websites.length}
                  </span>
                </div>
              )}
              {library.documents.length > 0 && (
                <div
                  className={`flex items-center gap-1 px-2 py-1 rounded-md ${sourceConfig.document.bg}`}
                >
                  <FileText
                    className={`size-3.5 ${sourceConfig.document.color}`}
                  />
                  <span className="text-xs font-medium">
                    {library.documents.length}
                  </span>
                </div>
              )}
              {library.youtube.length > 0 && (
                <div
                  className={`flex items-center gap-1 px-2 py-1 rounded-md ${sourceConfig.youtube.bg}`}
                >
                  <Youtube
                    className={`size-3.5 ${sourceConfig.youtube.color}`}
                  />
                  <span className="text-xs font-medium">
                    {library.youtube.length}
                  </span>
                </div>
              )}
            </div>

            {/* Expand/Collapse Chevron */}
            <ChevronDown
              className={cn(
                "size-4 sm:size-5 text-muted-foreground transition-transform duration-200 shrink-0",
                isExpanded && "rotate-180",
              )}
            />
          </button>
        </CollapsibleTrigger>

        {/* Expanded Management Panel */}
        <CollapsibleContent>
          <div className="border-t bg-muted/20">
            {/* Mobile swipe hint */}
            <p className="text-[10px] text-muted-foreground text-center py-1.5 bg-muted/30 sm:hidden">
              Swipe left on an item to delete
            </p>
            <div className="p-2 sm:p-4 space-y-3 sm:space-y-4 max-h-[300px] sm:max-h-[400px] overflow-y-auto">
              {/* Source Type Sections */}
              {(
                Object.entries(sourcesByType) as [
                  SourceType,
                  KnowledgeSource[],
                ][]
              )
                .filter(([, sources]) => sources.length > 0)
                .map(([type, sources]) => {
                  const config = sourceConfig[type];
                  const Icon = config.icon;

                  return (
                    <div key={type}>
                      {/* Section Header */}
                      <div className="flex items-center gap-2 mb-1.5 sm:mb-2 px-1">
                        <Icon
                          className={cn("size-3.5 sm:size-4", config.color)}
                        />
                        <span className="text-xs sm:text-sm font-medium">
                          {config.label}
                        </span>
                        <Badge
                          variant="secondary"
                          className="h-4 sm:h-5 text-[10px] sm:text-xs px-1.5"
                        >
                          {sources.length}
                        </Badge>
                      </div>

                      {/* Source Items */}
                      <div className="rounded-lg border bg-card divide-y">
                        {sources.map((source) => (
                          <KnowledgeSourceRow key={source.id} source={source} />
                        ))}
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
