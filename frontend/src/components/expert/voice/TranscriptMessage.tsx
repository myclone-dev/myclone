"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Calendar,
  FileText,
  FileSpreadsheet,
  Presentation,
  ImageIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import MessageCitations from "@/components/chat/MessageCitations";
import type { MessageSource } from "@/types/expert";
import { decodeHtmlEntities } from "@/lib/utils";
import { formatFileSize } from "@/lib/queries/expert/chat";
import type { ContentOutputItem } from "@/types/contentOutput";
import { ContentOutputCard } from "../chat/ContentOutputCard";

interface Citation {
  index: number;
  url: string;
  title: string;
  content?: string;
  raw_source?: string;
  source_type?: string;
}

interface TranscriptAttachment {
  id: string;
  filename: string;
  fileType: string;
  fileSize: number;
  extractionStatus?: string;
}

interface TranscriptMessageProps {
  text: string;
  speaker: "user" | "assistant";
  timestamp: number;
  expertName: string;
  avatarUrl?: string;
  calendarUrl?: string;
  /** Custom display name for calendar booking button (e.g., "Solicitar cita") */
  calendarDisplayName?: string;
  citations?: Citation[];
  attachments?: TranscriptAttachment[];
  contentOutput?: ContentOutputItem;
  onViewContent?: (content: ContentOutputItem) => void;
}

// Memoized citations component to prevent re-rendering when text changes
const MemoizedCitations = React.memo(
  function MemoizedCitations({ citations }: { citations: Citation[] }) {
    // Convert citations to MessageSource format
    const sources: MessageSource[] = useMemo(() => {
      return citations.map((c) => {
        const url = c.url || "";

        // Determine source from raw_source or URL
        let source = c.raw_source || "";
        if (!source) {
          const isTwitter = /x\.com|twitter\.com/i.test(url);
          const isLinkedIn = /linkedin\.com/i.test(url);
          source = isTwitter
            ? "twitter_profile"
            : isLinkedIn
              ? "linkedin_profile"
              : "website_content";
        }

        // Determine type from source_type or infer from source
        let type: "social_media" | "website" | "document" | "other" = "other";
        if (c.source_type) {
          type = c.source_type as
            | "social_media"
            | "website"
            | "document"
            | "other";
        } else {
          // Infer type from source
          if (source === "twitter_profile" || source === "linkedin_profile") {
            type = "social_media";
          } else if (source === "website_content") {
            type = "website";
          } else if (source === "pdf_document") {
            type = "document";
          }
        }

        return {
          source,
          title: c.title || "Source",
          content: c.content || "",
          similarity: 0,
          source_url: url,
          type,
        };
      });
    }, [citations]);

    return (
      <div className="mt-2 transcript-citations">
        <MessageCitations sources={sources} position="below" />
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Only re-render if citations array reference or length changed
    if (prevProps.citations === nextProps.citations) return true;
    if (prevProps.citations.length !== nextProps.citations.length) return false;
    // Deep compare citations by URL and title (stable identifiers)
    return prevProps.citations.every(
      (c, i) =>
        c.url === nextProps.citations[i].url &&
        c.title === nextProps.citations[i].title,
    );
  },
);

// Helper function to get file icon based on type
function getFileIcon(fileType: string) {
  const type = fileType.toLowerCase();
  if (type === "pdf") {
    return <FileText className="h-3.5 w-3.5 text-red-500" />;
  }
  if (type === "doc" || type === "docx") {
    return <FileText className="h-3.5 w-3.5 text-blue-600" />;
  }
  if (type === "xls" || type === "xlsx") {
    return <FileSpreadsheet className="h-3.5 w-3.5 text-green-600" />;
  }
  if (type === "ppt" || type === "pptx") {
    return <Presentation className="h-3.5 w-3.5 text-orange-500" />;
  }
  if (["png", "jpg", "jpeg", "gif", "webp"].includes(type)) {
    return <ImageIcon className="h-3.5 w-3.5 text-blue-500" />;
  }
  return <FileText className="h-3.5 w-3.5 text-gray-500" />;
}

function TranscriptMessageComponent({
  text,
  speaker,
  timestamp,
  expertName,
  avatarUrl,
  calendarUrl,
  calendarDisplayName,
  citations,
  attachments,
  contentOutput,
  onViewContent,
}: TranscriptMessageProps) {
  const { t } = useTranslation();
  const isUser = speaker === "user";

  // Decode HTML entities
  const decodedText = decodeHtmlEntities(text);

  const formatTime = (ts: number) => {
    return new Date(ts).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {/* Expert Avatar */}
      {!isUser && (
        <div className="shrink-0 mt-1">
          <Avatar className="w-8 h-8">
            <AvatarImage src={avatarUrl || undefined} alt={expertName} />
            <AvatarFallback className="bg-linear-to-br from-amber-500 to-orange-600 text-white text-xs">
              {expertName?.charAt(0) || "A"}
            </AvatarFallback>
          </Avatar>
        </div>
      )}

      <div className={`${isUser ? "max-w-[85%]" : "max-w-[calc(100%-3rem)]"}`}>
        <div
          data-message-type={isUser ? "user" : "bot"}
          className={`rounded-2xl px-4 py-2.5 shadow-sm embed-message-bubble ${
            isUser
              ? "bg-linear-to-r from-blue-500 to-blue-600 text-white ml-auto embed-user-message"
              : "bg-white border border-gray-200 text-gray-900 embed-bot-message"
          }`}
        >
          {/* Attachments Display */}
          {isUser && attachments && attachments.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {attachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="flex items-center gap-1.5 rounded-md bg-white/20 px-2 py-1"
                >
                  {getFileIcon(attachment.fileType)}
                  <span className="max-w-24 truncate text-xs">
                    {attachment.filename}
                  </span>
                  <span className="text-[10px] opacity-70">
                    {formatFileSize(attachment.fileSize)}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="text-sm leading-relaxed max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Customize rendering with explicit styles (no prose dependency)
                p: ({ children }) => (
                  <p className="whitespace-pre-wrap break-words my-1.5">
                    {children}
                  </p>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold">{children}</strong>
                ),
                em: ({ children }) => <em className="italic">{children}</em>,
                code: ({ children }) => (
                  <code className="bg-black/10 px-1.5 py-0.5 rounded text-xs font-mono">
                    {children}
                  </code>
                ),
                pre: ({ children }) => (
                  <pre className="bg-black/10 p-3 rounded-lg text-xs overflow-x-auto my-2 font-mono">
                    {children}
                  </pre>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-5 my-2 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-5 my-2 space-y-1">
                    {children}
                  </ol>
                ),
                li: ({ children }) => <li className="pl-1">{children}</li>,
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 underline hover:no-underline"
                  >
                    {children}
                  </a>
                ),
                h1: ({ children }) => (
                  <h1 className="text-lg font-bold mt-3 mb-2">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-base font-bold mt-3 mb-2">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-sm font-bold mt-2 mb-1">{children}</h3>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-gray-300 pl-4 my-2 italic text-gray-600">
                    {children}
                  </blockquote>
                ),
                hr: () => <hr className="my-3 border-gray-200" />,
                table: ({ children }) => (
                  <div className="overflow-x-auto my-2">
                    <table className="min-w-full border-collapse text-xs">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="border border-gray-300 px-2 py-1 bg-gray-100 font-semibold text-left">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="border border-gray-300 px-2 py-1">
                    {children}
                  </td>
                ),
              }}
            >
              {decodedText}
            </ReactMarkdown>
          </div>

          {/* Citations - memoized to prevent re-rendering on text updates */}
          {!isUser && citations && citations.length > 0 && (
            <MemoizedCitations citations={citations} />
          )}

          {/* Content Output Card */}
          {!isUser && contentOutput && onViewContent && (
            <ContentOutputCard content={contentOutput} onView={onViewContent} />
          )}

          {/* Calendar Link */}
          {!isUser && calendarUrl && (
            <div className="mt-2">
              <a
                href={calendarUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-3 py-2 bg-linear-to-r from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 border border-blue-200 rounded-lg transition-all duration-200 group"
              >
                <Calendar className="w-4 h-4 text-blue-600 group-hover:text-blue-700" />
                <span className="text-sm font-medium text-blue-700 group-hover:text-blue-800">
                  {calendarDisplayName || t("calendar.bookCall")}
                </span>
              </a>
            </div>
          )}
        </div>

        <div
          className={`flex items-center gap-2 mt-1 px-1 ${
            isUser ? "justify-end" : "justify-start"
          }`}
        >
          <span className="text-[10px] text-gray-400 font-medium">
            {formatTime(timestamp)}
          </span>
        </div>
      </div>
    </div>
  );
}

export const TranscriptMessage = React.memo(TranscriptMessageComponent);
