"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Download, Check, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";
import { downloadFile } from "@/lib/utils/transcriptExport";
import type { ContentOutputItem } from "@/types/contentOutput";

interface ContentOutputViewerProps {
  content: ContentOutputItem | null;
  onClose: () => void;
}

export function ContentOutputViewer({
  content,
  onClose,
}: ContentOutputViewerProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  if (!content) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content.body);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const slug = content.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .slice(0, 50);
    const filename = `${slug}-${new Date().toISOString().split("T")[0]}.md`;
    downloadFile(content.body, filename, "text/markdown");
  };

  return (
    <Dialog
      open={!!content}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className="w-[90vw] sm:w-[70vw] max-w-[90vw] sm:max-w-[70vw] h-[70vh] flex flex-col gap-0 p-0"
        showCloseButton={false}
      >
        {/* Header */}
        <DialogHeader className="px-6 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wide block mb-1">
                {content.content_type}
              </span>
              <DialogTitle className="text-base font-semibold text-gray-900 leading-snug">
                {content.title}
              </DialogTitle>
              {content.persona_name && (
                <p className="text-xs text-gray-500 mt-0.5">
                  {content.persona_name}
                  {content.persona_role ? ` — ${content.persona_role}` : ""}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0 mt-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={handleCopy}
                title={t("contentOutput.copyMarkdown")}
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-600" />
                ) : (
                  <Copy className="h-4 w-4 text-gray-500" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={handleDownload}
                title={t("contentOutput.downloadMd")}
              >
                <Download className="h-4 w-4 text-gray-500" />
              </Button>

              {/* Separator + Close */}
              <div className="w-px h-5 bg-gray-200 mx-2" />
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={onClose}
              >
                <X className="h-4 w-4 text-gray-500" />
              </Button>
            </div>
          </div>
        </DialogHeader>

        {/* Body - scrollable markdown */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="text-sm text-gray-800 leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => (
                  <h1 className="text-xl font-bold mt-4 mb-2 text-gray-900">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-lg font-bold mt-4 mb-2 text-gray-900">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-base font-semibold mt-3 mb-1.5 text-gray-900">
                    {children}
                  </h3>
                ),
                p: ({ children }) => (
                  <p className="mb-3 whitespace-pre-wrap">{children}</p>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold">{children}</strong>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-5 mb-3 space-y-1">
                    {children}
                  </ol>
                ),
                li: ({ children }) => <li className="pl-1">{children}</li>,
                code: ({ children }) => (
                  <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono text-gray-800">
                    {children}
                  </code>
                ),
                pre: ({ children }) => (
                  <pre className="bg-gray-100 rounded-lg p-4 overflow-x-auto text-xs font-mono mb-3">
                    {children}
                  </pre>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-ai-gold pl-4 italic text-gray-600 mb-3">
                    {children}
                  </blockquote>
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
                hr: () => <hr className="my-4 border-gray-200" />,
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
              {content.body}
            </ReactMarkdown>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
