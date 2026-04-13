"use client";

import { useState } from "react";
import { FileText, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useRawTextUpload } from "@/lib/queries/knowledge";
import { useTierLimitCheck } from "@/lib/queries/tier";

interface RawTextUploadFormProps {
  userId: string;
  onSuccess?: () => void;
}

const MIN_CONTENT_LENGTH = 10;
const MAX_TITLE_LENGTH = 255;

export function RawTextUploadForm({
  userId,
  onSuccess,
}: RawTextUploadFormProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { mutate: uploadRawText, isPending } = useRawTextUpload();
  const { canUploadDocument, usage, hasReachedLimit } = useTierLimitCheck();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate title
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setError("Please enter a title for your content");
      return;
    }
    if (trimmedTitle.length > MAX_TITLE_LENGTH) {
      setError(`Title must be ${MAX_TITLE_LENGTH} characters or less`);
      return;
    }

    // Validate content
    const trimmedContent = content.trim();
    if (!trimmedContent) {
      setError("Please enter some text content");
      return;
    }
    if (trimmedContent.length < MIN_CONTENT_LENGTH) {
      setError(`Content must be at least ${MIN_CONTENT_LENGTH} characters`);
      return;
    }

    // Check tier limits (estimate size as UTF-8 bytes)
    const contentSizeBytes = new TextEncoder().encode(trimmedContent).length;
    const contentSizeMB = contentSizeBytes / 1024 / 1024;
    const limitCheck = canUploadDocument(contentSizeMB);
    if (!limitCheck.allowed) {
      setError(limitCheck.reason || "Upload not allowed due to tier limits");
      return;
    }

    uploadRawText(
      {
        title: trimmedTitle,
        content: trimmedContent,
        userId,
      },
      {
        onSuccess: (data) => {
          if (data.success) {
            setTitle("");
            setContent("");
            setError(null);
            onSuccess?.();
          }
        },
        onError: (err) => {
          setError(err.message || "Failed to add text content");
        },
      },
    );
  };

  const contentLength = content.length;
  const contentSizeKB = new TextEncoder().encode(content).length / 1024;

  // Show limit reached warning
  const limitReached = hasReachedLimit("documents");

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {limitReached && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>
            Document limit reached ({usage?.documents.files.limit} files).
            Please upgrade your plan to add more content.
          </AlertDescription>
        </Alert>
      )}

      {usage && usage.documents.files.percentage >= 80 && !limitReached && (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertDescription>
            You&apos;ve used {usage.documents.files.percentage}% of your
            document limit ({usage.documents.files.used}/
            {usage.documents.files.limit} files). Consider upgrading your plan.
          </AlertDescription>
        </Alert>
      )}

      {/* Title Input */}
      <div className="space-y-2">
        <Label htmlFor="title">Title</Label>
        <Input
          id="title"
          placeholder="e.g., Meeting Notes - January 2024"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          disabled={isPending || limitReached}
          maxLength={MAX_TITLE_LENGTH}
        />
        <p className="text-xs text-muted-foreground">
          A descriptive title helps you find this content later
        </p>
      </div>

      {/* Content Textarea */}
      <div className="space-y-2">
        <Label htmlFor="content">Content</Label>
        <Textarea
          id="content"
          placeholder="Paste your meeting notes, transcripts, or any text content here..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={isPending || limitReached}
          className="min-h-[200px] max-h-[300px] resize-y overflow-y-auto whitespace-pre-wrap wrap-break-word field-sizing-fixed"
        />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {contentLength.toLocaleString()} characters
            {contentSizeKB > 1 && ` (${contentSizeKB.toFixed(1)} KB)`}
          </span>
          <span>Minimum {MIN_CONTENT_LENGTH} characters</span>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Info Box */}
      <div className="rounded-lg border bg-muted/50 p-4">
        <div className="flex items-start gap-3">
          <FileText className="size-5 text-muted-foreground mt-0.5" />
          <div className="text-sm text-muted-foreground">
            <p className="font-medium text-foreground mb-1">
              Paste text directly
            </p>
            <p>
              Perfect for meeting notes, call transcripts, research notes, or
              any text content. No need to create a file first.
            </p>
          </div>
        </div>
      </div>

      {/* Submit Button */}
      <Button
        type="submit"
        disabled={
          !title.trim() ||
          content.length < MIN_CONTENT_LENGTH ||
          isPending ||
          limitReached
        }
        className="w-full"
      >
        {isPending ? (
          <>
            <Loader2 className="mr-2 size-4 animate-spin" />
            Adding content...
          </>
        ) : limitReached ? (
          "Limit Reached"
        ) : (
          "Add Text Content"
        )}
      </Button>
    </form>
  );
}
