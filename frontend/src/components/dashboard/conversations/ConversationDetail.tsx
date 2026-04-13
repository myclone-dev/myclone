"use client";

import { useRef, useState, useEffect } from "react";
import {
  ArrowLeft,
  User,
  MessageSquare,
  Mic,
  Clock,
  FileText,
  Image as ImageIcon,
  ExternalLink,
  Download,
  FileDown,
  FileSpreadsheet,
  Presentation,
  ChevronsUp,
  ChevronsDown,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useConversation,
  useConversationSummary,
  type ConversationMessageAttachment,
} from "@/lib/queries/conversations";
import { useUserMe } from "@/lib/queries/users";
import { useUserPersonas } from "@/lib/queries/persona";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import MessageCitations from "@/components/chat/MessageCitations";
import { ConversationSummaryCard } from "./ConversationSummaryCard";
import { RecordingPlayer } from "./RecordingPlayer";
import { cn, decodeHtmlEntities } from "@/lib/utils";
import {
  downloadConversationAsMarkdown,
  downloadConversationAsPdf,
} from "@/lib/utils/conversationExport";
import { getAttachmentCategory } from "@/lib/queries/expert/chat";

interface Source {
  source: string;
  title: string;
  content: string;
  similarity?: number;
  source_url: string;
  type: "social_media" | "website" | "document" | "other";
  verification_note?: string;
}

interface ConversationMessage {
  speaker?: string;
  role?: string;
  type?: string;
  text?: string;
  content?: string;
  message?: string;
  timestamp?: string;
  sources?: Source[];
  // Attachment support for PDFs and images
  attachments?: ConversationMessageAttachment[];
  // New fields for special chat with attachments
  hidden?: boolean; // If true, don't render this message in UI
  content_type?: string; // "text" | "pdf"
  url?: string; // URL for attachments (e.g., S3 URL for PDFs)
}

// Helper function to format file size
function formatFileSize(bytes?: number): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// Get icon for attachment based on file type category
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

// Attachment component for displaying file attachments in messages
// Shows image preview for images, chip link for documents
function AttachmentDisplay({
  attachment,
}: {
  attachment: ConversationMessageAttachment;
}) {
  const isImage = ["png", "jpg", "jpeg"].includes(attachment.file_type);

  // For images, show the actual image with a link wrapper
  if (isImage && attachment.s3_url) {
    return (
      <a
        href={attachment.s3_url}
        target="_blank"
        rel="noopener noreferrer"
        className="block max-w-xs overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm transition-shadow hover:shadow-md"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={attachment.s3_url}
          alt={attachment.filename}
          className="max-h-48 w-full object-contain"
          loading="lazy"
        />
        <div className="flex items-center gap-1.5 border-t border-gray-100 bg-gray-50 px-2 py-1 text-xs text-gray-600">
          <ImageIcon className="h-3 w-3 text-blue-500" />
          <span className="max-w-32 truncate">{attachment.filename}</span>
          {attachment.file_size && (
            <span className="text-gray-400">
              ({formatFileSize(attachment.file_size)})
            </span>
          )}
          <ExternalLink className="ml-auto h-3 w-3 text-gray-400" />
        </div>
      </a>
    );
  }

  // For documents (PDF, Word, Excel, PowerPoint), show a chip link
  return (
    <a
      href={attachment.s3_url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white/80 px-2 py-1 text-xs text-gray-700 transition-colors hover:bg-gray-100"
    >
      {getAttachmentIcon(attachment.file_type)}
      <span className="max-w-24 truncate">{attachment.filename}</span>
      {attachment.file_size && (
        <span className="text-gray-400">
          ({formatFileSize(attachment.file_size)})
        </span>
      )}
      <ExternalLink className="h-3 w-3 text-gray-400" />
    </a>
  );
}

interface ConversationDetailProps {
  conversationId: string;
  onBack?: () => void;
  hideSummary?: boolean;
}

/**
 * Parse and clean message text that contains inline source information
 * This is a temporary fix - ideally the backend should return properly structured data
 *
 * Format being parsed:
 * "Message text
 *
 * Name
 * Name
 * Invalid Date
 * Additional information relevant to the user's next message: [Source: type
 * Content: text]
 *
 * ---
 *
 * [Source: type
 * Content: text]
 * "
 */
function parseAndCleanMessage(text: string): {
  cleanText: string;
  sources: Source[];
} {
  if (!text) return { cleanText: "", sources: [] };

  const sources: Source[] = [];
  let cleanText = text;

  // Step 1: Extract all source blocks
  // Pattern: [Source: type\nContent: text]
  const sourceBlockPattern = /\[Source:\s*([^\n]+)\s*Content:\s*([^\]]+)\]/gi;

  let match;
  while ((match = sourceBlockPattern.exec(text)) !== null) {
    const sourceType = match[1].trim();
    const content = match[2].trim();

    sources.push({
      source: sourceType,
      title: `${sourceType.charAt(0).toUpperCase() + sourceType.slice(1)}`,
      content:
        content.length > 200 ? content.substring(0, 200) + "..." : content,
      source_url: "",
      type:
        sourceType === "audio" || sourceType === "video"
          ? "document"
          : sourceType.includes("website")
            ? "website"
            : "other",
    });
  }

  // Step 2: Remove the entire "Additional information..." blocks
  cleanText = cleanText.replace(
    /Additional information relevant to the user's next message:\s*\[Source:[^\]]+\]/gi,
    "",
  );

  // Step 3: Remove standalone source blocks
  cleanText = cleanText.replace(/\[Source:[^\]]+\]/gi, "");

  // Step 4: Remove markdown separators
  cleanText = cleanText.replace(/\n*---\n*/g, "\n\n");

  // Step 5: Remove duplicate name + "Invalid Date" artifacts
  // Pattern: Name\nName\nInvalid Date
  cleanText = cleanText.replace(/\n+([A-Za-z\s]+)\n\1\nInvalid Date\n*/gi, "");

  // Step 6: Clean up excessive whitespace
  cleanText = cleanText.replace(/\n{3,}/g, "\n\n").trim();

  return { cleanText, sources };
}

export function ConversationDetail({
  conversationId,
  onBack,
  hideSummary = false,
}: ConversationDetailProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButtons, setShowScrollButtons] = useState(false);
  const [isAtTop, setIsAtTop] = useState(true);
  const [isAtBottom, setIsAtBottom] = useState(false);

  const {
    data: conversation,
    isLoading,
    error,
  } = useConversation(conversationId);

  const { data: user } = useUserMe();
  const { data: personasData } = useUserPersonas(user?.id || "");

  // Fetch conversation summary (auth via cookies)
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
  } = useConversationSummary(conversationId);

  // Find the persona for this conversation
  const persona = personasData?.personas?.find(
    (p) => p.id === conversation?.persona_id,
  );

  // Handle scroll position tracking for jump buttons
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const scrollable = scrollHeight > clientHeight + 100; // Only show if there's meaningful scroll

      setShowScrollButtons(scrollable);
      setIsAtTop(scrollTop < 50);
      setIsAtBottom(scrollTop + clientHeight >= scrollHeight - 50);
    };

    container.addEventListener("scroll", handleScroll);
    // Initial check
    handleScroll();

    return () => container.removeEventListener("scroll", handleScroll);
  }, [conversation?.messages]);

  const scrollToTop = () => {
    scrollContainerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  };

  const scrollToBottom = () => {
    scrollContainerRef.current?.scrollTo({
      top: scrollContainerRef.current.scrollHeight,
      behavior: "smooth",
    });
  };

  if (isLoading) {
    return (
      <div className="flex flex-col h-[calc(100vh-8rem)]">
        <div className="h-16 animate-pulse bg-muted/50 mb-4 border-b" />
        <div className="flex-1 space-y-4 max-w-3xl mx-auto w-full px-4 py-6">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className={`flex gap-3 ${i % 2 === 0 ? "flex-row-reverse" : ""}`}
            >
              <div className="size-8 animate-pulse rounded-full bg-muted/50" />
              <div
                className={`h-16 w-64 animate-pulse rounded-lg bg-muted/50`}
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <p className="text-red-600">Failed to load conversation</p>
        <p className="mt-2 text-sm text-muted-foreground">
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
        {onBack && (
          <Button variant="outline" onClick={onBack} className="mt-4">
            <ArrowLeft className="mr-2 size-4" />
            Back to conversations
          </Button>
        )}
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <p className="text-muted-foreground">Conversation not found</p>
        {onBack && (
          <Button variant="outline" onClick={onBack} className="mt-4">
            <ArrowLeft className="mr-2 size-4" />
            Back to conversations
          </Button>
        )}
      </div>
    );
  }

  const isVoice = conversation.conversation_type === "voice";
  const TypeIcon = isVoice ? Mic : MessageSquare;

  // Use max-height when embedded (no onBack), fixed height when standalone
  const containerClass = onBack
    ? "flex flex-col h-[calc(100vh-8rem)] overflow-hidden bg-background border rounded-lg"
    : "flex flex-col max-h-[600px] overflow-hidden bg-background";

  return (
    <div className={containerClass}>
      {/* Header */}
      <div className="flex-shrink-0 border-b bg-muted/30">
        <div className="flex items-center justify-between px-3 py-3 sm:px-6 sm:py-4">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0 flex-1">
            {onBack && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onBack}
                className="shrink-0 h-8 w-8 sm:h-10 sm:w-10"
              >
                <ArrowLeft className="size-4 sm:size-5" />
              </Button>
            )}

            {/* User Avatar */}
            <Avatar className="size-9 sm:size-11 ring-2 ring-background shrink-0">
              <AvatarFallback className="bg-primary/10">
                <User className="size-4 sm:size-5 text-primary" />
              </AvatarFallback>
            </Avatar>

            {/* User Info */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 sm:gap-2 mb-0.5 sm:mb-1">
                <h2 className="text-sm sm:text-base font-semibold truncate">
                  {conversation.user_fullname ||
                    conversation.user_email ||
                    "Anonymous Visitor"}
                </h2>
                <Badge
                  variant={isVoice ? "default" : "secondary"}
                  className="text-[10px] sm:text-xs shrink-0 px-1.5 sm:px-2"
                >
                  <TypeIcon className="size-2.5 sm:size-3 mr-0.5 sm:mr-1" />
                  <span className="hidden sm:inline">
                    {conversation.conversation_type}
                  </span>
                  <span className="sm:hidden">
                    {isVoice ? "voice" : "text"}
                  </span>
                </Badge>
              </div>
              <div className="flex items-center gap-2 sm:gap-3 text-[10px] sm:text-xs text-muted-foreground">
                <span className="flex items-center gap-0.5 sm:gap-1">
                  <MessageSquare className="size-2.5 sm:size-3" />
                  <span className="hidden sm:inline">
                    {conversation.message_count} messages
                  </span>
                  <span className="sm:hidden">
                    {conversation.message_count} msg
                  </span>
                </span>
                <span className="hidden sm:inline">•</span>
                <span className="flex items-center gap-0.5 sm:gap-1">
                  <Clock className="size-2.5 sm:size-3" />
                  <span className="hidden sm:inline">
                    {new Date(conversation.created_at).toLocaleDateString(
                      "en-US",
                      {
                        month: "short",
                        day: "numeric",
                        hour: "numeric",
                        minute: "2-digit",
                      },
                    )}
                  </span>
                  <span className="sm:hidden">
                    {new Date(conversation.created_at).toLocaleDateString(
                      "en-US",
                      {
                        month: "short",
                        day: "numeric",
                      },
                    )}
                  </span>
                </span>
                {conversation.user_email && (
                  <>
                    <span className="hidden sm:inline">•</span>
                    <span className="truncate hidden sm:inline">
                      {conversation.user_email}
                    </span>
                  </>
                )}
                {conversation.user_phone && (
                  <>
                    <span className="hidden sm:inline">•</span>
                    <span className="truncate hidden sm:inline">
                      {conversation.user_phone}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Download Button - Better spacing on mobile */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0 sm:w-auto sm:px-3 shrink-0 ml-2"
                aria-label="Download conversation"
              >
                <Download className="size-4 sm:mr-1.5" />
                <span className="hidden sm:inline">Download</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                className="focus:bg-gray-100"
                onClick={() =>
                  downloadConversationAsPdf(
                    conversation,
                    summary,
                    persona?.name,
                  )
                }
              >
                <FileText className="mr-2 size-4 text-red-500" />
                Download as PDF
              </DropdownMenuItem>
              <DropdownMenuItem
                className="focus:bg-gray-100"
                onClick={() =>
                  downloadConversationAsMarkdown(
                    conversation,
                    summary,
                    persona?.name,
                  )
                }
              >
                <FileDown className="mr-2 size-4 text-blue-500" />
                Download as Markdown
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Voice Recording Player - Only for voice conversations */}
      {isVoice && (
        <div className="flex-shrink-0 border-b">
          <RecordingPlayer
            recordingUrl={conversation.recording_url}
            recordingStatus={conversation.recording_status}
            durationSeconds={conversation.recording_duration_seconds}
            conversationId={conversationId}
          />
        </div>
      )}

      {/* Messages - Scrollable Area */}
      <div className="flex-1 overflow-y-auto relative" ref={scrollContainerRef}>
        {/* Floating scroll buttons - Mobile only */}
        {showScrollButtons && (
          <div className="fixed bottom-20 right-4 z-10 flex flex-col gap-2 sm:hidden">
            {!isAtTop && (
              <Button
                variant="secondary"
                size="icon"
                onClick={scrollToTop}
                className="h-10 w-10 rounded-full shadow-lg border bg-background/95 backdrop-blur-sm"
                aria-label="Scroll to top"
              >
                <ChevronsUp className="size-5" />
              </Button>
            )}
            {!isAtBottom && (
              <Button
                variant="secondary"
                size="icon"
                onClick={scrollToBottom}
                className="h-10 w-10 rounded-full shadow-lg border bg-background/95 backdrop-blur-sm"
                aria-label="Scroll to bottom"
              >
                <ChevronsDown className="size-5" />
              </Button>
            )}
          </div>
        )}

        <div className="max-w-4xl mx-auto px-3 py-4 sm:px-6 sm:py-8 space-y-4 sm:space-y-5">
          {/* AI Summary Section - Only show if not hidden by parent */}
          {!hideSummary && (
            <ConversationSummaryCard
              summary={summary || null}
              isLoading={summaryLoading}
              error={summaryError}
              defaultExpanded={false}
            />
          )}
          {conversation.messages && conversation.messages.length > 0 ? (
            conversation.messages
              .filter((message: ConversationMessage) => !message.hidden)
              .map((message: ConversationMessage, index: number) => {
                // Handle different message formats
                const speaker =
                  message.speaker || message.role || message.type || "user";
                const isUser =
                  speaker === "user" ||
                  speaker === "human" ||
                  speaker === "USER";

                // Get message text from various possible fields
                const rawMessageText =
                  message.text ||
                  message.content ||
                  message.message ||
                  JSON.stringify(message);

                // Parse inline sources and clean the text
                const { cleanText: messageText, sources: parsedSources } =
                  parseAndCleanMessage(rawMessageText);

                // Decode HTML entities
                const decodedMessageText = decodeHtmlEntities(messageText);

                // Merge parsed sources with existing sources (if any)
                const allSources = [
                  ...(message.sources || []),
                  ...parsedSources,
                ];

                return (
                  <div
                    key={index}
                    className={`flex gap-2 sm:gap-4 ${isUser ? "flex-row-reverse" : "flex-row"}`}
                  >
                    {/* Avatar */}
                    <Avatar className="size-8 sm:size-10 flex-shrink-0 ring-2 ring-background shadow-sm">
                      {isUser ? (
                        <AvatarFallback className="bg-primary/10">
                          <User className="size-4 sm:size-5 text-primary" />
                        </AvatarFallback>
                      ) : (
                        <>
                          <AvatarImage
                            src={user?.avatar || ""}
                            alt={persona?.name || "AI"}
                          />
                          <AvatarFallback className="bg-primary text-primary-foreground text-[10px] sm:text-xs font-semibold">
                            {persona?.name?.[0]?.toUpperCase() || "AI"}
                          </AvatarFallback>
                        </>
                      )}
                    </Avatar>

                    {/* Message Content */}
                    <div
                      className={`flex-1 space-y-1 sm:space-y-1.5 max-w-[85%] sm:max-w-[70%] ${isUser ? "items-end" : "items-start"} flex flex-col`}
                    >
                      {/* Message Header */}
                      <div
                        className={`flex items-baseline gap-1.5 sm:gap-2 ${isUser ? "flex-row-reverse" : "flex-row"}`}
                      >
                        <span
                          className={cn(
                            "text-[10px] sm:text-xs font-semibold px-1.5 sm:px-2 py-0.5 rounded",
                            isUser ? "" : "bg-black text-yellow-bright",
                          )}
                        >
                          {isUser ? "Visitor" : persona?.name || "AI Clone"}
                        </span>
                        {message.timestamp && (
                          <span className="text-[10px] sm:text-xs text-muted-foreground">
                            {new Date(message.timestamp).toLocaleTimeString(
                              "en-US",
                              {
                                hour: "numeric",
                                minute: "2-digit",
                              },
                            )}
                          </span>
                        )}
                      </div>

                      {/* Message Bubble */}
                      <div
                        className={`rounded-2xl px-3 py-2 sm:px-4 sm:py-3 shadow-sm ${
                          isUser
                            ? "bg-primary text-primary-foreground rounded-tr-sm"
                            : "bg-card border rounded-tl-sm"
                        }`}
                      >
                        {/* Attachments - displayed at top of message */}
                        {message.attachments &&
                          message.attachments.length > 0 && (
                            <div className="mb-2 flex flex-wrap gap-2">
                              {message.attachments.map((attachment) => (
                                <AttachmentDisplay
                                  key={attachment.id}
                                  attachment={attachment}
                                />
                              ))}
                            </div>
                          )}

                        <div className="text-xs sm:text-sm leading-relaxed prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              // Customize rendering to work with our styles
                              p: ({ children }) => (
                                <p className="whitespace-pre-wrap">
                                  {children}
                                </p>
                              ),
                              strong: ({ children }) => (
                                <strong className="font-bold">
                                  {children}
                                </strong>
                              ),
                              em: ({ children }) => (
                                <em className="italic">{children}</em>
                              ),
                              code: ({ children }) => (
                                <code className="bg-black/10 px-1.5 py-0.5 rounded text-xs font-mono">
                                  {children}
                                </code>
                              ),
                              pre: ({ children }) => (
                                <pre className="bg-black/10 p-2 rounded text-xs overflow-x-auto my-2">
                                  {children}
                                </pre>
                              ),
                              ul: ({ children }) => (
                                <ul className="list-disc pl-4 my-1">
                                  {children}
                                </ul>
                              ),
                              ol: ({ children }) => (
                                <ol className="list-decimal pl-4 my-1">
                                  {children}
                                </ol>
                              ),
                              li: ({ children }) => (
                                <li className="my-0.5">{children}</li>
                              ),
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
                            }}
                          >
                            {decodedMessageText}
                          </ReactMarkdown>
                        </div>

                        {/* Citations - only for AI messages */}
                        {!isUser && allSources.length > 0 && (
                          <div className="mt-2">
                            <MessageCitations
                              sources={allSources}
                              position="inline"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <div className="rounded-full bg-muted/50 p-6 mb-4">
                <MessageSquare className="size-12 opacity-40" />
              </div>
              <p className="text-base font-medium">No messages yet</p>
              <p className="text-sm text-muted-foreground/80 mt-1">
                This conversation hasn&apos;t started
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
