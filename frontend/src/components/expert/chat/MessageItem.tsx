"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  FileText,
  Image as ImageIcon,
  ExternalLink,
  FileSpreadsheet,
  Presentation,
  Calendar,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import MessageCitations from "@/components/chat/MessageCitations";
import type { Message, MessageAttachment } from "@/types/expert";
import type { ContentOutputItem } from "@/types/contentOutput";
import { decodeHtmlEntities } from "@/lib/utils";
import { TypingIndicator, StreamingCursor } from "./TypingIndicator";
import { ContentOutputCard } from "./ContentOutputCard";
import { getAttachmentCategory } from "@/lib/queries/expert/chat";

interface MessageItemProps {
  message: Message;
  /** Custom display name for calendar booking button (e.g., "Solicitar cita") */
  calendarDisplayName?: string;
  /** Called when user clicks "View Full Content" on a content output card */
  onViewContent?: (content: ContentOutputItem) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function getAttachmentIcon(fileType: string) {
  const category = getAttachmentCategory(fileType);
  switch (category) {
    case "pdf":
      return <FileText className="h-3.5 w-3.5 text-red-500" />;
    case "document":
      return <FileText className="h-3.5 w-3.5 text-blue-600" />;
    case "spreadsheet":
      return <FileSpreadsheet className="h-3.5 w-3.5 text-green-600" />;
    case "presentation":
      return <Presentation className="h-3.5 w-3.5 text-orange-500" />;
    case "image":
    default:
      return <ImageIcon className="h-3.5 w-3.5 text-blue-500" />;
  }
}

function AttachmentChip({ attachment }: { attachment: MessageAttachment }) {
  return (
    <a
      href={attachment.s3_url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white/80 px-2 py-1 text-xs text-gray-700 transition-colors hover:bg-gray-100"
    >
      {getAttachmentIcon(attachment.file_type)}
      <span className="max-w-24 truncate">{attachment.filename}</span>
      <span className="text-gray-400">
        ({formatFileSize(attachment.file_size)})
      </span>
      <ExternalLink className="h-3 w-3 text-gray-400" />
    </a>
  );
}

export function MessageItem({
  message,
  calendarDisplayName,
  onViewContent,
}: MessageItemProps) {
  const { t } = useTranslation();
  const isUser = message.sender === "user";

  // Decode HTML entities first
  const decodedContent = decodeHtmlEntities(message.content);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        data-message-type={isUser ? "user" : "bot"}
        className={`max-w-[80%] px-4 py-2.5 rounded-2xl shadow-sm embed-message-bubble ${
          isUser
            ? "bg-linear-to-r from-blue-500 to-blue-600 text-white embed-user-message"
            : "bg-white border border-gray-200 text-gray-800 embed-bot-message"
        }`}
      >
        {/* Attachments - displayed at top of message */}
        {message.attachments && message.attachments.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {message.attachments.map((attachment) => (
              <AttachmentChip key={attachment.id} attachment={attachment} />
            ))}
          </div>
        )}

        <div
          className={`text-sm leading-relaxed ${
            isUser
              ? "**:text-white [&_a]:text-white [&_a]:underline [&_code]:bg-white/20 [&_pre]:bg-white/20"
              : "[&_a]:text-blue-600 [&_code]:bg-black/10 [&_pre]:bg-black/10"
          }`}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Customize rendering to work with our styles
              p: ({ children }) => (
                <p className="whitespace-pre-wrap my-1">{children}</p>
              ),
              strong: ({ children }) => (
                <strong className="font-bold">{children}</strong>
              ),
              em: ({ children }) => <em className="italic">{children}</em>,
              code: ({ children }) => (
                <code className="px-1.5 py-0.5 rounded text-xs font-mono">
                  {children}
                </code>
              ),
              pre: ({ children }) => (
                <pre className="p-2 rounded text-xs overflow-x-auto my-2">
                  {children}
                </pre>
              ),
              ul: ({ children }) => (
                <ul className="list-disc pl-4 my-1 space-y-0.5">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal pl-4 my-1 space-y-0.5">
                  {children}
                </ol>
              ),
              li: ({ children }) => <li className="my-0.5">{children}</li>,
              a: ({ href, children }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:no-underline"
                >
                  {children}
                </a>
              ),
              h1: ({ children }) => (
                <h1 className="text-lg font-bold my-2">{children}</h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-base font-bold my-2">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-sm font-bold my-1">{children}</h3>
              ),
              blockquote: ({ children }) => (
                <blockquote className="border-l-2 border-current/30 pl-3 my-2 italic">
                  {children}
                </blockquote>
              ),
            }}
          >
            {decodedContent}
          </ReactMarkdown>
        </div>
        {message.isStreaming && !message.content && (
          <TypingIndicator variant="wave" className="py-1" />
        )}
        {message.isStreaming && message.content && <StreamingCursor />}

        <p className="text-xs opacity-70 mt-1.5">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>

        {/* Citations - only for expert messages */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <MessageCitations sources={message.sources} position="inline" />
        )}

        {/* Content output card - only for expert messages with content */}
        {!isUser && message.contentOutput && onViewContent && (
          <ContentOutputCard
            content={message.contentOutput}
            onView={onViewContent}
          />
        )}

        {/* Calendar link - only for expert messages with calendar URL */}
        {!isUser && message.calendarUrl && (
          <a
            href={message.calendarUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 mt-3 px-4 py-2.5 bg-gradient-to-r from-yellow-bright to-ai-gold text-gray-900 rounded-xl font-medium text-sm shadow-sm hover:shadow-md transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <Calendar className="h-4 w-4" />
            <span>{calendarDisplayName || t("calendar.scheduleMeeting")}</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}
