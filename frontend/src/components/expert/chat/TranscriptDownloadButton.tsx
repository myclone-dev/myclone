"use client";

import { useState } from "react";
import { Download, FileText, File, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  downloadTranscriptAsMarkdown,
  downloadTranscriptAsPdf,
  downloadTranscriptAsText,
} from "@/lib/utils/transcriptExport";
import type { Message } from "@/types/expert";

interface TranscriptDownloadButtonProps {
  /** Chat messages to export */
  messages: Message[];
  /** Name of the expert */
  expertName: string;
  /** Username for filename */
  username: string;
  /** Optional persona name for metadata */
  personaName?: string;
  /** Variant of the button */
  variant?: "default" | "outline" | "ghost";
  /** Size of the button */
  size?: "default" | "sm" | "lg" | "icon";
  /** Additional class names */
  className?: string;
  /** Whether the button is disabled */
  disabled?: boolean;
}

/**
 * Button component with dropdown for downloading chat transcript
 * in different formats (Markdown, PDF, Text)
 */
export function TranscriptDownloadButton({
  messages,
  expertName,
  username,
  personaName,
  variant = "outline",
  size = "sm",
  className = "",
  disabled = false,
}: TranscriptDownloadButtonProps) {
  const [isOpen, setIsOpen] = useState(false);

  const metadata = {
    personaName,
    sessionDate: new Date(),
  };

  const handleDownloadMarkdown = () => {
    downloadTranscriptAsMarkdown(messages, expertName, username, metadata);
    setIsOpen(false);
  };

  const handleDownloadPdf = () => {
    downloadTranscriptAsPdf(messages, expertName, username, metadata);
    setIsOpen(false);
  };

  const handleDownloadText = () => {
    downloadTranscriptAsText(messages, expertName, username, metadata);
    setIsOpen(false);
  };

  // Don't show if no messages
  if (messages.length === 0) {
    return null;
  }

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant={variant}
          size={size}
          disabled={disabled}
          className={`flex items-center gap-2 ${className}`}
        >
          <Download className="w-4 h-4" />
          <span className="hidden sm:inline">Download Transcript</span>
          <span className="sm:hidden">Download</span>
          <ChevronDown className="w-3 h-3 ml-1" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44 p-1">
        <DropdownMenuItem
          onClick={handleDownloadMarkdown}
          className="flex items-center gap-2.5 px-3 py-2 cursor-pointer rounded-md hover:bg-gray-100 focus:bg-gray-100"
        >
          <FileText className="w-4 h-4 text-blue-600 shrink-0" />
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-medium text-gray-700">Markdown</span>
            <span className="text-xs text-gray-400">.md file</span>
          </div>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={handleDownloadPdf}
          className="flex items-center gap-2.5 px-3 py-2 cursor-pointer rounded-md hover:bg-gray-100 focus:bg-gray-100"
        >
          <File className="w-4 h-4 text-red-500 shrink-0" />
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-medium text-gray-700">PDF</span>
            <span className="text-xs text-gray-400">Print to PDF</span>
          </div>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={handleDownloadText}
          className="flex items-center gap-2.5 px-3 py-2 cursor-pointer rounded-md hover:bg-gray-100 focus:bg-gray-100"
        >
          <FileText className="w-4 h-4 text-gray-500 shrink-0" />
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-medium text-gray-700">
              Plain Text
            </span>
            <span className="text-xs text-gray-400">.txt file</span>
          </div>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
