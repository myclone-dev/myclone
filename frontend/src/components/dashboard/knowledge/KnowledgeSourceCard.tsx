"use client";

import { useState } from "react";
import {
  Linkedin,
  Twitter,
  Globe,
  FileText,
  Youtube,
  Trash2,
  Users,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { useDeleteKnowledgeSource } from "@/lib/queries/knowledge";
import type { KnowledgeSource } from "@/lib/queries/knowledge";

interface KnowledgeSourceCardProps {
  source: KnowledgeSource;
}

const sourceConfig = {
  linkedin: {
    icon: Linkedin,
    color: "text-[#0A66C2]",
    bg: "bg-[#0A66C2]/10",
    label: "LinkedIn",
  },
  twitter: {
    icon: Twitter,
    color: "text-[#1DA1F2]",
    bg: "bg-[#1DA1F2]/10",
    label: "Twitter",
  },
  website: {
    icon: Globe,
    color: "text-ai-brown",
    bg: "bg-orange-100",
    label: "Website",
  },
  document: {
    icon: FileText,
    color: "text-red-600",
    bg: "bg-red-100",
    label: "Document",
  },
  youtube: {
    icon: Youtube,
    color: "text-red-600",
    bg: "bg-red-100",
    label: "YouTube",
  },
};

export function KnowledgeSourceCard({ source }: KnowledgeSourceCardProps) {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const deleteSource = useDeleteKnowledgeSource();

  const config = sourceConfig[source.type];
  const Icon = config.icon;

  const handleDelete = async () => {
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
      });

      toast.success(result.message || "Knowledge source deleted successfully", {
        description:
          result.personas_affected > 0
            ? `Detached from ${result.personas_affected} persona(s)`
            : undefined,
      });
      setDeleteDialogOpen(false);
    } catch (error) {
      const err = error as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      const errorMessage =
        err.response?.data?.detail || err.message || "Unknown error";

      trackDashboardOperation("knowledge_source_delete", "error", {
        sourceType: source.type,
        sourceId: source.id,
        error: errorMessage,
      });

      toast.error("Failed to delete knowledge source", {
        description: errorMessage,
      });
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getMetadataText = () => {
    switch (source.type) {
      case "linkedin":
        return `${source.posts_count} posts, ${source.experiences_count} experiences, ${source.skills_count} skills`;
      case "twitter":
        return `${source.tweets_count} tweets, ${source.followers_count.toLocaleString()} followers`;
      case "website":
        return `${source.pages_crawled} pages crawled`;
      case "document":
        return `${source.document_type.toUpperCase()}${source.page_count ? `, ${source.page_count} pages` : ""}`;
      case "youtube":
        return source.duration_seconds
          ? `${Math.floor(source.duration_seconds / 60)} minutes`
          : "";
      default:
        return "";
    }
  };

  return (
    <>
      <Card className="overflow-hidden transition-all hover:shadow-md">
        <CardHeader className={`${config.bg} pb-4`}>
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`flex size-12 items-center justify-center rounded-lg bg-white shadow-sm`}
              >
                <Icon className={`size-6 ${config.color}`} />
              </div>
              <div>
                <CardTitle className="text-lg line-clamp-1">
                  {source.display_name}
                </CardTitle>
                <Badge variant="outline" className="mt-1">
                  {config.label}
                </Badge>
              </div>
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-4 space-y-3">
          {/* Metadata */}
          {source.type === "linkedin" && source.headline && (
            <p className="text-sm text-muted-foreground line-clamp-2">
              {source.headline}
            </p>
          )}
          {source.type === "twitter" && source.bio && (
            <p className="text-sm text-muted-foreground line-clamp-2">
              {source.bio}
            </p>
          )}
          {source.type === "website" && source.description && (
            <p className="text-sm text-muted-foreground line-clamp-2">
              {source.description}
            </p>
          )}
          {source.type === "document" && (
            <p className="text-sm text-muted-foreground">{source.filename}</p>
          )}
          {source.type === "youtube" && source.description && (
            <p className="text-sm text-muted-foreground line-clamp-2">
              {source.description}
            </p>
          )}

          {/* Stats */}
          <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Users className="size-3" />
              <span>
                {source.used_by_personas_count}{" "}
                {source.used_by_personas_count === 1 ? "persona" : "personas"}
              </span>
            </div>
          </div>

          {/* Additional Info */}
          <div className="pt-2 border-t space-y-1 text-xs text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>{getMetadataText()}</span>
            </div>
            <div className="flex items-center gap-1">
              <Calendar className="size-3" />
              <span>Added {formatDate(source.created_at)}</span>
            </div>
          </div>
        </CardContent>

        <CardFooter className="pt-0">
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={() => setDeleteDialogOpen(true)}
          >
            <Trash2 className="size-4 mr-2" />
            Delete Source
          </Button>
        </CardFooter>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertCircle className="size-5 text-destructive" />
              Delete Knowledge Source?
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>
                This will permanently delete{" "}
                <strong>{source.display_name}</strong> and all its data.
              </p>
              {source.used_by_personas_count > 0 && (
                <p className="text-destructive font-medium">
                  ⚠️ This source is currently used by{" "}
                  {source.used_by_personas_count} persona(s). It will be
                  detached from all of them.
                </p>
              )}
              <p className="font-semibold pt-2">
                This action cannot be undone.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteSource.isPending}
            >
              {deleteSource.isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
