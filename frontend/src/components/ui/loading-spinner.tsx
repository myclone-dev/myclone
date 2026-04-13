import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

const sizeClasses = {
  sm: "w-4 h-4 border-2",
  md: "w-8 h-8 border-3",
  lg: "w-12 h-12 border-4",
};

export function LoadingSpinner({
  className,
  size = "md",
}: LoadingSpinnerProps) {
  return (
    <div
      className={cn(
        "inline-block rounded-full border-solid border-current border-t-transparent animate-spin",
        sizeClasses[size],
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  );
}

export function LoadingDots({ className }: { className?: string }) {
  return (
    <div className={cn("flex gap-1", className)}>
      <div className="w-2 h-2 bg-violet-600 rounded-full animate-bounce [animation-delay:-0.3s]" />
      <div className="w-2 h-2 bg-violet-600 rounded-full animate-bounce [animation-delay:-0.15s]" />
      <div className="w-2 h-2 bg-violet-600 rounded-full animate-bounce" />
    </div>
  );
}

export function LoadingPulse({ className }: { className?: string }) {
  return (
    <div className={cn("flex gap-2", className)}>
      <div className="w-3 h-3 bg-violet-600 rounded-full animate-pulse" />
      <div className="w-3 h-3 bg-violet-600 rounded-full animate-pulse [animation-delay:0.2s]" />
      <div className="w-3 h-3 bg-violet-600 rounded-full animate-pulse [animation-delay:0.4s]" />
    </div>
  );
}
