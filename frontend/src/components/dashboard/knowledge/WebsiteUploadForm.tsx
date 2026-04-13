"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/ui/numeric-input";
import { useWebsiteUpload } from "@/lib/queries/knowledge";

interface WebsiteUploadFormProps {
  userId: string;
  onSuccess?: () => void;
}

export function WebsiteUploadForm({
  userId,
  onSuccess,
}: WebsiteUploadFormProps) {
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [maxPages, setMaxPages] = useState(10);
  const { mutate: uploadWebsite, isPending } = useWebsiteUpload();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!websiteUrl.trim()) return;

    // Automatically prepend https:// if no protocol is provided
    let formattedUrl = websiteUrl.trim();
    if (!formattedUrl.match(/^https?:\/\//i)) {
      formattedUrl = `https://${formattedUrl}`;
    }

    uploadWebsite(
      {
        user_id: userId,
        website_url: formattedUrl,
        max_pages: maxPages,
      },
      {
        onSuccess: () => {
          setWebsiteUrl("");
          setMaxPages(10);
          onSuccess?.();
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        type="text"
        placeholder="https://yourwebsite.com"
        value={websiteUrl}
        onChange={(e) => setWebsiteUrl(e.target.value)}
        required
      />
      <div className="space-y-2">
        <NumericInput
          value={maxPages}
          onChange={(value) => setMaxPages(value ?? 10)}
          min={1}
          max={100}
          placeholder="Max pages (default: 10)"
        />
        <p className="text-xs text-muted-foreground">
          Recommended: 10-20 pages for best results
        </p>
      </div>
      <Button type="submit" disabled={isPending} className="w-full ">
        {isPending ? "Importing..." : "Import"}
      </Button>
    </form>
  );
}
