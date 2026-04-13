"use client";

import { cn } from "@/lib/utils";

interface TypingIndicatorProps {
  className?: string;
  variant?: "dots" | "wave" | "pulse";
}

export function TypingIndicator({
  className,
  variant = "wave",
}: TypingIndicatorProps) {
  if (variant === "dots") {
    return (
      <div className={cn("flex items-center gap-1", className)}>
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
      </div>
    );
  }

  if (variant === "pulse") {
    return (
      <div className={cn("flex items-center gap-1.5", className)}>
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-pulse [animation-delay:0.2s]" />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-pulse [animation-delay:0.4s]" />
      </div>
    );
  }

  // Wave variant (default) - smooth scaling animation
  return (
    <div className={cn("flex items-center gap-1", className)}>
      <span className="w-2 h-2 bg-gray-400 rounded-full animate-[wave_1.2s_ease-in-out_infinite]" />
      <span className="w-2 h-2 bg-gray-400 rounded-full animate-[wave_1.2s_ease-in-out_infinite_0.2s]" />
      <span className="w-2 h-2 bg-gray-400 rounded-full animate-[wave_1.2s_ease-in-out_infinite_0.4s]" />
    </div>
  );
}

// Streaming cursor for when content is being received
export function StreamingCursor({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block w-0.5 h-4 bg-blue-500 ml-0.5 animate-[blink_1s_ease-in-out_infinite] rounded-full",
        className,
      )}
    />
  );
}
