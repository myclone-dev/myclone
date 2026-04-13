import { cn } from "@/lib/utils";

interface PageLoaderProps {
  text?: string;
  variant?: "default" | "minimal" | "dots";
  className?: string;
}

/**
 * Modern minimalist page loader
 * For full-page loading states
 */
export function PageLoader({
  text = "Loading...",
  variant = "default",
  className,
}: PageLoaderProps) {
  return (
    <div
      className={cn(
        "min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-100 via-gray-50 to-orange-50",
        className,
      )}
    >
      <div className="flex flex-col items-center gap-6">
        {variant === "default" && <SpinnerLoader />}
        {variant === "minimal" && <MinimalLoader />}
        {variant === "dots" && <DotsLoader />}
        {text && (
          <p className="text-sm font-medium text-slate-600 animate-pulse">
            {text}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * Elegant circular spinner
 */
function SpinnerLoader() {
  return (
    <div className="relative w-16 h-16">
      {/* Outer ring */}
      <div className="absolute inset-0 rounded-full border-4 border-orange-200" />
      {/* Spinning arc */}
      <div
        className="absolute inset-0 rounded-full border-4 border-transparent border-t-ai-brown animate-spin"
        style={{ animationDuration: "0.8s" }}
      />
    </div>
  );
}

/**
 * Minimal pulsing circle
 */
function MinimalLoader() {
  return (
    <div className="flex gap-2">
      <div
        className="w-3 h-3 rounded-full bg-ai-brown animate-pulse"
        style={{ animationDelay: "0s" }}
      />
      <div
        className="w-3 h-3 rounded-full bg-ai-brown animate-pulse"
        style={{ animationDelay: "0.2s" }}
      />
      <div
        className="w-3 h-3 rounded-full bg-ai-brown animate-pulse"
        style={{ animationDelay: "0.4s" }}
      />
    </div>
  );
}

/**
 * Bouncing dots
 */
function DotsLoader() {
  return (
    <div className="flex gap-2">
      <div
        className="w-3 h-3 rounded-full bg-ai-brown animate-bounce"
        style={{ animationDelay: "0s" }}
      />
      <div
        className="w-3 h-3 rounded-full bg-ai-brown animate-bounce"
        style={{ animationDelay: "0.1s" }}
      />
      <div
        className="w-3 h-3 rounded-full bg-ai-brown animate-bounce"
        style={{ animationDelay: "0.2s" }}
      />
    </div>
  );
}

/**
 * Compact inline loader (for smaller areas)
 */
export function InlineLoader({ text }: { text?: string }) {
  return (
    <div className="flex items-center gap-3 py-8">
      <div className="w-8 h-8 rounded-full border-3 border-orange-200 border-t-ai-brown animate-spin" />
      {text && <span className="text-sm text-slate-600">{text}</span>}
    </div>
  );
}
