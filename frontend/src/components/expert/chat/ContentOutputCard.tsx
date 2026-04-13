"use client";

import { FileText, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";
import type { ContentOutputItem } from "@/types/contentOutput";

interface ContentOutputCardProps {
  content: ContentOutputItem;
  onView: (content: ContentOutputItem) => void;
}

export function ContentOutputCard({ content, onView }: ContentOutputCardProps) {
  const { t } = useTranslation();

  // Strip markdown headings and show first ~150 chars as preview
  const preview = content.body
    .replace(/^#+\s+/gm, "")
    .trim()
    .slice(0, 150);
  const hasMore = content.body.length > 150;

  return (
    <div className="mt-2 rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 bg-gray-50">
        <FileText className="h-3.5 w-3.5 text-ai-gold shrink-0" />
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          {content.content_type}
        </span>
      </div>
      <div className="px-3 py-2.5">
        <p className="text-sm font-semibold text-gray-900 leading-snug mb-1">
          {content.title}
        </p>
        <p className="text-xs text-gray-500 leading-relaxed line-clamp-3">
          {preview}
          {hasMore ? "…" : ""}
        </p>
      </div>
      <div className="px-3 pb-2.5">
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs gap-1 border-ai-gold/40 text-gray-700 hover:bg-yellow-light"
          onClick={() => onView(content)}
        >
          {t("contentOutput.viewFull")}
          <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
