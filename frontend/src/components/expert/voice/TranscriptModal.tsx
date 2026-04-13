"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { X, MessageSquare, Download, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import MessageCitations from "@/components/chat/MessageCitations";
import type { MessageSource } from "@/types/expert";
import { decodeHtmlEntities } from "@/lib/utils";

interface TranscriptMessage {
  id: string;
  text: string;
  speaker: "user" | "assistant";
  timestamp: number;
  isComplete: boolean;
  citations?: Array<{
    index: number;
    url: string;
    title: string;
    content?: string;
    raw_source?: string;
    source_type?: string;
  }>;
}

interface TranscriptModalProps {
  isOpen: boolean;
  onClose: () => void;
  transcriptMessages: TranscriptMessage[];
  expertName: string;
  avatarUrl?: string;
  onDownload?: () => void;
}

export function TranscriptModal({
  isOpen,
  onClose,
  transcriptMessages,
  expertName,
  avatarUrl,
  onDownload,
}: TranscriptModalProps) {
  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const citationCount = transcriptMessages.reduce(
    (count, msg) => count + (msg.citations?.length || 0),
    0,
  );

  // Convert citations to MessageSource format
  const convertCitations = (
    citations?: Array<{
      index: number;
      url: string;
      title: string;
      content?: string;
      raw_source?: string;
      source_type?: string;
    }>,
  ): MessageSource[] | undefined => {
    return citations?.map((c) => {
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
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[9999] flex items-center justify-center p-3 sm:p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="bg-white rounded-xl sm:rounded-2xl shadow-2xl max-w-2xl w-full max-h-[85vh] sm:max-h-[80vh] overflow-hidden border border-gray-100"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 sm:p-6 border-b border-gray-100 bg-gradient-to-r from-amber-50 to-orange-50">
              <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                <div className="w-8 h-8 sm:w-10 sm:h-10 bg-gradient-to-br from-amber-100 to-amber-200 rounded-lg sm:rounded-xl flex items-center justify-center flex-shrink-0">
                  <MessageSquare className="w-4 h-4 sm:w-5 sm:h-5 text-amber-700" />
                </div>
                <div className="min-w-0">
                  <h2 className="text-base sm:text-xl font-semibold text-gray-900 truncate">
                    Conversation Transcript
                  </h2>
                  <p className="text-xs sm:text-sm text-gray-600 truncate">
                    Your chat with {expertName}
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="w-8 h-8 sm:w-10 sm:h-10 hover:bg-amber-100/50 rounded-lg sm:rounded-xl flex items-center justify-center transition-colors flex-shrink-0"
              >
                <X className="w-4 h-4 sm:w-5 sm:h-5 text-gray-500" />
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto max-h-[50vh] p-4 sm:p-6">
              {transcriptMessages.length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  <MessageSquare className="w-16 h-16 mx-auto mb-4 text-gray-200" />
                  <p className="text-sm">No conversation to display</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {transcriptMessages.map((message, index) => {
                    const isUser = message.speaker === "user";
                    const sources = convertCitations(message.citations);

                    // Decode HTML entities
                    const decodedText = decodeHtmlEntities(message.text);

                    return (
                      <div
                        key={message.id || index}
                        className={`flex gap-4 ${isUser ? "justify-end" : "justify-start"}`}
                      >
                        {!isUser && (
                          <Avatar className="w-10 h-10 flex-shrink-0">
                            <AvatarImage
                              src={avatarUrl || undefined}
                              alt={expertName}
                            />
                            <AvatarFallback className="bg-gradient-to-br from-amber-50 to-amber-100 text-amber-700 border border-amber-200">
                              {expertName?.charAt(0) || "A"}
                            </AvatarFallback>
                          </Avatar>
                        )}

                        <div className="max-w-[75%]">
                          <div
                            data-message-type={isUser ? "user" : "bot"}
                            className={`rounded-2xl px-4 py-3 shadow-sm embed-message-bubble ${
                              isUser
                                ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-br-md embed-user-message"
                                : "bg-white text-gray-800 border border-gray-200 rounded-bl-md embed-bot-message"
                            }`}
                          >
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
                                    <strong className="font-semibold">
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
                                    <pre className="bg-black/10 p-3 rounded-lg text-xs overflow-x-auto my-2 font-mono">
                                      {children}
                                    </pre>
                                  ),
                                  ul: ({ children }) => (
                                    <ul className="list-disc pl-5 my-2 space-y-1">
                                      {children}
                                    </ul>
                                  ),
                                  ol: ({ children }) => (
                                    <ol className="list-decimal pl-5 my-2 space-y-1">
                                      {children}
                                    </ol>
                                  ),
                                  li: ({ children }) => (
                                    <li className="pl-1">{children}</li>
                                  ),
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
                                    <h1 className="text-lg font-bold mt-3 mb-2">
                                      {children}
                                    </h1>
                                  ),
                                  h2: ({ children }) => (
                                    <h2 className="text-base font-bold mt-3 mb-2">
                                      {children}
                                    </h2>
                                  ),
                                  h3: ({ children }) => (
                                    <h3 className="text-sm font-bold mt-2 mb-1">
                                      {children}
                                    </h3>
                                  ),
                                  blockquote: ({ children }) => (
                                    <blockquote className="border-l-4 border-gray-300 pl-4 my-2 italic text-gray-600">
                                      {children}
                                    </blockquote>
                                  ),
                                  hr: () => (
                                    <hr className="my-3 border-gray-200" />
                                  ),
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

                            {/* Citations */}
                            {!isUser && sources && sources.length > 0 && (
                              <div className="mt-3">
                                <MessageCitations
                                  sources={sources}
                                  position="below"
                                />
                              </div>
                            )}
                          </div>

                          <div
                            className={`flex items-center gap-2 mt-2 px-2 ${
                              isUser ? "justify-end" : "justify-start"
                            }`}
                          >
                            <span className="text-xs text-gray-600 font-medium flex items-center gap-1">
                              {isUser ? (
                                <>
                                  <User className="w-3 h-3" />
                                  <span>Me</span>
                                </>
                              ) : (
                                expertName
                              )}
                            </span>
                            <span className="text-xs text-gray-400">•</span>
                            <span className="text-xs text-gray-500">
                              {formatTime(message.timestamp)}
                            </span>
                          </div>
                        </div>

                        {isUser && (
                          <Avatar className="w-10 h-10 flex-shrink-0">
                            <AvatarFallback className="bg-gradient-to-br from-blue-100 to-blue-200 text-blue-700 border border-blue-300">
                              <User className="w-5 h-5" />
                            </AvatarFallback>
                          </Avatar>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between p-6 border-t border-gray-100 bg-gradient-to-r from-amber-50/30 to-orange-50/30">
              <div className="text-sm text-gray-600">
                {transcriptMessages.length} message
                {transcriptMessages.length !== 1 ? "s" : ""} in conversation
                {citationCount > 0 && (
                  <span className="ml-2 text-amber-700 font-medium">
                    • {citationCount} source{citationCount > 1 ? "s" : ""}{" "}
                    referenced
                  </span>
                )}
              </div>
              <div className="flex gap-3">
                {onDownload && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onDownload}
                    className="flex items-center gap-2 text-amber-700 hover:bg-amber-50 border-amber-300 hover:border-amber-400"
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onClose}
                  className="px-4 hover:bg-gray-100"
                >
                  Close
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
