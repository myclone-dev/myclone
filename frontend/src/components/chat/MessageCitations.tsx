"use client";

import React, { useState } from "react";
import {
  Globe,
  FileText,
  ChevronRight,
  ExternalLink,
  Youtube,
  Mic,
  Video,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export interface Source {
  source: string;
  title: string;
  content: string;
  context?: string; // AI-generated summary for documents/audio/video, or title for YouTube
  similarity?: number;
  source_url: string;
  type: "social_media" | "website" | "document" | "other";
  verification_note?: string;
}

interface MessageCitationsProps {
  sources: Source[];
  className?: string;
  position?: "inline" | "below";
}

const getSourceIcon = (source: Source) => {
  // Twitter/X
  if (
    source.source === "twitter_profile" ||
    source.source_url.includes("x.com") ||
    source.source_url.includes("twitter.com")
  ) {
    return (
      <svg
        className="w-4 h-4"
        fill="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
    );
  }

  // LinkedIn
  if (
    source.source === "linkedin_profile" ||
    source.source === "linkedin_experience" ||
    source.source === "linkedin_post" ||
    source.source_url.includes("linkedin.com")
  ) {
    return (
      <svg
        className="w-4 h-4"
        fill="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
      </svg>
    );
  }

  // YouTube
  if (
    source.source === "youtube" ||
    source.source === "youtube_video" ||
    source.source_url.includes("youtube.com") ||
    source.source_url.includes("youtu.be")
  ) {
    return <Youtube className="w-4 h-4" />;
  }

  // Audio
  if (source.source === "audio" || source.source === "audio_transcript") {
    return <Mic className="w-4 h-4" />;
  }

  // Video
  if (source.source === "video" || source.source === "video_transcript") {
    return <Video className="w-4 h-4" />;
  }

  // Website - check explicitly before document fallback
  if (source.source === "website_page" || source.source === "website_content") {
    return <Globe className="w-4 h-4" />;
  }

  // Document (PDF only - after website check)
  if (source.source === "pdf_document" || source.source === "pdf") {
    return <FileText className="w-4 h-4" />;
  }

  // Default: Website/Globe
  return <Globe className="w-4 h-4" />;
};

const cleanAndPreviewContent = (
  source: Source,
  maxLength: number = 50,
): string => {
  // Priority 1: Use context field (AI-generated summary for documents, title for YouTube)
  if (source.context && source.context.trim()) {
    let content = source.context.trim();
    // Clean up whitespace
    content = content.replace(/\s+/g, " ").replace(/\n+/g, " ");
    // Truncate if needed
    if (content.length <= maxLength) return content;
    return content.substring(0, maxLength).trim() + "...";
  }

  // Priority 2: Fall back to content or title
  let content = source.content || source.title || "";

  // Special handling for website content
  if (source.type === "document" && source.source === "website_content") {
    // Extract website title if available
    const titleMatch = content.match(/Website Title:\s*([^\n]+)/i);
    if (titleMatch) {
      return titleMatch[1].trim();
    }
  }

  // Remove dates in brackets like [2025-08-07], [2025-08-18], etc.
  content = content.replace(/\[\d{4}-\d{2}-\d{2}\]/g, "");

  // Remove "LinkedIn Post", "X (Twitter) Profile", etc. prefixes
  content = content.replace(
    /^(LinkedIn Post|X \(Twitter\) Profile|Twitter Profile|Website Title:|Website Content:)\s*:?\s*/i,
    "",
  );

  // Remove engagement info like (Likes: 1), (Engagement: 185), etc.
  content = content.replace(
    /\((?:Likes|Engagement|Retweets?|Comments?):\s*\d+\)/gi,
    "",
  );

  // Clean up extra whitespace and newlines
  content = content.trim().replace(/\s+/g, " ").replace(/\n+/g, " ");

  // If still too long, truncate and add ellipsis
  if (content.length <= maxLength) return content;
  return content.substring(0, maxLength).trim() + "...";
};

const getSourceColor = (source: Source): string => {
  // Twitter/X
  if (
    source.source === "twitter_profile" ||
    source.source_url.includes("x.com") ||
    source.source_url.includes("twitter.com")
  ) {
    return "text-gray-900 bg-gray-100 hover:bg-gray-200 border-gray-200";
  }

  // LinkedIn
  if (
    source.source === "linkedin_profile" ||
    source.source === "linkedin_experience" ||
    source.source === "linkedin_post" ||
    source.source_url.includes("linkedin.com")
  ) {
    return "text-blue-700 bg-blue-50 hover:bg-blue-100 border-blue-200";
  }

  // YouTube
  if (
    source.source === "youtube" ||
    source.source === "youtube_video" ||
    source.source_url.includes("youtube.com") ||
    source.source_url.includes("youtu.be")
  ) {
    return "text-red-700 bg-red-50 hover:bg-red-100 border-red-200";
  }

  // Audio
  if (source.source === "audio" || source.source === "audio_transcript") {
    return "text-green-700 bg-green-50 hover:bg-green-100 border-green-200";
  }

  // Video
  if (source.source === "video" || source.source === "video_transcript") {
    return "text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border-indigo-200";
  }

  // Website - check explicitly before document fallback
  if (source.source === "website_page" || source.source === "website_content") {
    return "text-orange-700 bg-orange-50 hover:bg-orange-100 border-orange-200";
  }

  // Document (PDF only)
  if (source.source === "pdf_document" || source.source === "pdf") {
    return "text-purple-700 bg-purple-50 hover:bg-purple-100 border-purple-200";
  }

  // Default: Website
  return "text-orange-700 bg-orange-50 hover:bg-orange-100 border-orange-200";
};

const CitationCard: React.FC<{ source: Source; index: number }> = ({
  source,
  index,
}) => {
  const shortContent = cleanAndPreviewContent(source, 120);
  const hasValidUrl = source.source_url && source.source_url.trim() !== "";

  const getSourceDisplayName = () => {
    // For documents with context, extract a meaningful title
    if (source.type === "document" && source.context) {
      // Check if it's audio/video/PDF based on source field
      if (source.source === "audio" || source.source === "audio_transcript") {
        return "Audio Document";
      }
      if (source.source === "video" || source.source === "video_transcript") {
        return "Video Document";
      }
      if (source.source === "pdf_document" || source.source === "pdf") {
        return "PDF Document";
      }
    }

    // Social media sources
    if (source.source === "twitter_profile") return "Twitter Profile";
    if (source.source === "linkedin_post") return "LinkedIn Post";
    if (
      source.source === "linkedin_profile" ||
      source.source === "linkedin_experience"
    )
      return "LinkedIn Experience";

    // Website sources
    if (source.source === "website_content" || source.source === "website_page")
      return "Website";

    // YouTube (uses context for title)
    if (
      source.source === "youtube" ||
      source.source === "youtube_video" ||
      source.source_url.includes("youtube.com") ||
      source.source_url.includes("youtu.be")
    )
      return "YouTube Video";

    // Fallback for audio/video/pdf without context
    if (source.source === "audio" || source.source === "audio_transcript")
      return "Audio Transcript";
    if (source.source === "video" || source.source === "video_transcript")
      return "Video Transcript";
    if (source.source === "pdf_document" || source.source === "pdf")
      return "PDF Document";

    return source.title || "Source";
  };

  const sourceDisplayName = getSourceDisplayName();

  const CardContent = () => (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={`group relative flex items-center gap-3 p-3 rounded-lg border transition-all duration-200 ${hasValidUrl ? "cursor-pointer" : "cursor-default"} ${getSourceColor(source)}`}
    >
      {/* Icon */}
      <div className="flex-shrink-0">{getSourceIcon(source)}</div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-900 line-clamp-1 mb-1">
          {sourceDisplayName}
          {!hasValidUrl && (
            <span className="text-xs text-gray-500 ml-2">(No URL)</span>
          )}
        </div>
        <div className="text-xs text-gray-600 line-clamp-2">{shortContent}</div>
        {source.similarity !== undefined && source.similarity > 0 && (
          <div className="text-xs text-gray-500 mt-1">
            {Math.round(source.similarity * 100)}% relevance
          </div>
        )}
      </div>

      {/* External link icon for clickable sources */}
      {hasValidUrl && (
        <div className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          <ExternalLink className="w-4 h-4 text-gray-400" />
        </div>
      )}
    </motion.div>
  );

  // If has source URL, make the whole card clickable
  if (hasValidUrl) {
    return (
      <a
        href={source.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="block hover:no-underline"
      >
        <CardContent />
      </a>
    );
  }

  return <CardContent />;
};

const InlineCitations: React.FC<{ sources: Source[] }> = ({ sources }) => {
  const [showAll, setShowAll] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const displaySources = showAll ? sources : sources.slice(0, 6);

  return (
    <div className="flex flex-wrap items-center gap-2 mt-3 max-w-full overflow-hidden">
      <span className="text-xs text-gray-500 font-medium flex-shrink-0">
        Sources:
      </span>
      {displaySources.map((source, index) => {
        const hasValidUrl =
          source.source_url && source.source_url.trim() !== "";
        const isHovered = hoveredIndex === index;
        const previewText = cleanAndPreviewContent(source, 50);

        const CitationBadge = (
          <div
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs transition-colors duration-200 ${getSourceColor(source)} ${hasValidUrl ? "cursor-pointer" : "cursor-default"}`}
            title={
              hasValidUrl ? source.title : `${source.title} (No URL available)`
            }
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <span className="flex-shrink-0">{getSourceIcon(source)}</span>
            {/* Always show preview text to prevent resize flickering */}
            <span
              className={`whitespace-nowrap overflow-hidden transition-all duration-200 ${
                isHovered ? "max-w-[200px] opacity-100" : "max-w-20 opacity-90"
              }`}
              style={{ textOverflow: "ellipsis" }}
            >
              {previewText}
            </span>
            {hasValidUrl && (
              <ExternalLink
                className={`w-3 h-3 shrink-0 transition-opacity duration-200 ${
                  isHovered ? "opacity-70" : "opacity-0"
                }`}
              />
            )}
          </div>
        );

        if (hasValidUrl) {
          return (
            <a
              key={index}
              href={source.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:no-underline"
            >
              {CitationBadge}
            </a>
          );
        }

        return <div key={index}>{CitationBadge}</div>;
      })}
      {sources.length > 6 && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          className="text-xs text-gray-600 hover:text-gray-800 font-medium flex-shrink-0"
        >
          +{sources.length - 6} more
        </button>
      )}
    </div>
  );
};

const MessageCitations: React.FC<MessageCitationsProps> = ({
  sources,
  className = "",
  position = "below",
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Remove duplicate sources based on source_url and content
  // For sources without URLs, deduplicate by content + title
  const uniqueSources = sources.reduce((acc: Source[], source) => {
    const isDuplicate = acc.find((s) => {
      // If both have URLs, compare URLs
      if (s.source_url && source.source_url) {
        return s.source_url === source.source_url;
      }
      // If no URLs, compare by content and title to avoid collapsing different sources
      return (
        s.content === source.content &&
        s.title === source.title &&
        s.source === source.source
      );
    });

    if (!isDuplicate) {
      acc.push(source);
    }
    return acc;
  }, []);

  if (uniqueSources.length === 0) return null;

  if (position === "inline") {
    return <InlineCitations sources={uniqueSources} />;
  }

  // Below position - expandable citation cards
  return (
    <div className={`mt-4 max-w-full ${className}`}>
      {/* Toggle button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors mb-3"
      >
        <ChevronRight
          className={`w-4 h-4 transition-transform ${
            isExpanded ? "rotate-90" : ""
          }`}
        />
        {uniqueSources.length}{" "}
        {uniqueSources.length === 1 ? "Source" : "Sources"}
      </button>

      {/* Citation cards */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="grid gap-2 overflow-hidden max-w-full"
          >
            {uniqueSources.map((source, index) => (
              <CitationCard
                key={source.source_url}
                source={source}
                index={index}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default MessageCitations;
