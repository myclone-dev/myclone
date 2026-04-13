"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLinkedInUpload } from "@/lib/queries/knowledge";

interface LinkedInUploadFormProps {
  userId: string;
  onSuccess?: () => void;
}

export function LinkedInUploadForm({
  userId,
  onSuccess,
}: LinkedInUploadFormProps) {
  const [linkedinUrl, setLinkedinUrl] = useState("https://linkedin.com/in/");
  const { mutate: uploadLinkedIn, isPending } = useLinkedInUpload();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!linkedinUrl.trim()) return;

    uploadLinkedIn(
      { user_id: userId, linkedin_url: linkedinUrl },
      {
        onSuccess: () => {
          setLinkedinUrl("https://linkedin.com/in/");
          onSuccess?.();
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        type="url"
        placeholder="https://linkedin.com/in/username"
        value={linkedinUrl}
        onChange={(e) => setLinkedinUrl(e.target.value)}
        required
      />
      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Importing..." : "Import"}
      </Button>
    </form>
  );
}
