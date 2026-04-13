import { Sparkles } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

interface AvatarWithAIBadgeProps {
  src?: string;
  alt: string;
  fallbackText: string;
  className?: string;
  badgePosition?: "top-right" | "bottom-right";
}

/**
 * Avatar component with AI sparkle badge overlay
 * Displays a profile avatar with a small AI indicator badge
 */
export function AvatarWithAIBadge({
  src,
  alt,
  fallbackText,
  className,
  badgePosition = "bottom-right",
}: AvatarWithAIBadgeProps) {
  return (
    <div className="relative inline-block">
      <Avatar
        className={cn("w-36 h-36 ring-4 ring-white shadow-xl", className)}
      >
        <AvatarImage src={src} alt={alt} className="object-top" />
        <AvatarFallback className="bg-gradient-to-br from-amber-400 to-orange-500 text-white text-3xl font-semibold">
          {fallbackText}
        </AvatarFallback>
      </Avatar>

      {/* AI Badge - Sparkle Icon */}
      <div
        className={cn(
          "absolute flex items-center justify-center w-9 h-9 rounded-full shadow-lg ring-2 ring-white",
          "bg-gradient-to-br from-amber-400 to-orange-500",
          badgePosition === "bottom-right" && "bottom-0 right-0",
          badgePosition === "top-right" && "top-0 right-0",
        )}
        title="AI Clone"
      >
        <Sparkles className="w-5 h-5 text-white" fill="white" />
      </div>
    </div>
  );
}
