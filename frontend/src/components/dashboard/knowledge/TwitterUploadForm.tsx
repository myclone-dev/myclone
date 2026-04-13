"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTwitterUpload } from "@/lib/queries/knowledge";

interface TwitterUploadFormProps {
  userId: string;
  onSuccess?: () => void;
}

/**
 * Extract Twitter/X username from URL or plain username
 * Supports: https://twitter.com/username, https://x.com/username, @username, username
 */
function extractTwitterUsername(input: string): string {
  const trimmed = input.trim();

  // Check if it's a URL
  const urlPattern =
    /^https?:\/\/(?:www\.)?(?:twitter\.com|x\.com)\/([A-Za-z0-9_]{1,15})\/?(?:\?.*)?$/;
  const urlMatch = trimmed.match(urlPattern);
  if (urlMatch) {
    return urlMatch[1];
  }

  // Remove @ if present and return username
  return trimmed.replace(/^@/, "");
}

export function TwitterUploadForm({
  userId,
  onSuccess,
}: TwitterUploadFormProps) {
  const [twitterUrl, setTwitterUrl] = useState("https://x.com/");
  const { mutate: uploadTwitter, isPending } = useTwitterUpload();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!twitterUrl.trim()) return;

    // Extract username from URL or plain input
    const cleanUsername = extractTwitterUsername(twitterUrl);

    if (!cleanUsername || cleanUsername.length === 0) {
      return;
    }

    uploadTwitter(
      { user_id: userId, twitter_username: cleanUsername },
      {
        onSuccess: () => {
          setTwitterUrl("https://x.com/");
          onSuccess?.();
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        type="url"
        placeholder="https://x.com/username"
        value={twitterUrl}
        onChange={(e) => setTwitterUrl(e.target.value)}
        required
      />
      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Importing..." : "Import"}
      </Button>
    </form>
  );
}
