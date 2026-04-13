"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { AssistantBubble } from "./AssistantBubble";
import { AssistantPanel } from "./AssistantPanel";
import type { AssistantWidgetProps } from "./types";

/** Pages where the assistant widget should be hidden */
const HIDDEN_ON_PATHS = ["/dashboard/workflows/visual-builder"];

/**
 * Assistant Widget
 * Floating helper that provides voice and text assistance for persona creation
 * Uses the same VoiceInterface UI as the expert/agent page
 */
export function AssistantWidget({ className }: AssistantWidgetProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const pathname = usePathname();

  // Hide widget on certain pages (visual builder needs full screen)
  const isHidden = HIDDEN_ON_PATHS.some((path) => pathname?.startsWith(path));

  // Handle bubble click - toggle expanded state
  const handleBubbleClick = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  // Handle close from panel header
  const handleClose = useCallback(() => {
    setIsExpanded(false);
  }, []);

  // Handle escape key to close
  useEffect(() => {
    // Skip event listener setup if widget is hidden
    if (isHidden) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && isExpanded) {
        handleClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isExpanded, handleClose, isHidden]);

  // Don't render anything on hidden pages (must be after all hooks)
  if (isHidden) {
    return null;
  }

  return (
    <div
      className={cn(
        // Fixed position in bottom-right corner
        "fixed bottom-6 right-6 z-50",
        // Flex container for stacking panel above bubble
        "flex flex-col items-end gap-3",
        className,
      )}
    >
      {/* Panel (expanded state) */}
      <AnimatePresence>
        {isExpanded && <AssistantPanel onClose={handleClose} />}
      </AnimatePresence>

      {/* Floating Bubble */}
      <AssistantBubble onClick={handleBubbleClick} isExpanded={isExpanded} />
    </div>
  );
}

// Re-export types for external use
export type { AssistantWidgetProps } from "./types";
