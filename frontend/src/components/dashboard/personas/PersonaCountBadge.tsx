import { Badge } from "@/components/ui/badge";

interface PersonaCountBadgeProps {
  current: number;
  max: number;
  /** Whether the user has reached or exceeded their limit */
  isAtLimit?: boolean;
  /** Additional className for styling */
  className?: string;
}

/**
 * Reusable badge component displaying persona count
 * Shows current/max format for limited plans, or just count for unlimited
 */
export function PersonaCountBadge({
  current,
  max,
  isAtLimit = false,
  className = "",
}: PersonaCountBadgeProps) {
  // Unlimited plan (-1 limit)
  if (max === -1) {
    return (
      <Badge variant="secondary" className={`text-xs ${className}`}>
        {current} personas (unlimited)
      </Badge>
    );
  }

  // Limited plan
  return (
    <Badge
      variant={isAtLimit ? "destructive" : "secondary"}
      className={`text-xs ${className}`}
    >
      {current}/{max} personas
    </Badge>
  );
}
