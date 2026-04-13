import { Loader2 } from "lucide-react";

interface SectionHeaderProps {
  title: string;
  description: string;
  isSaving?: boolean;
}

export function SectionHeader({
  title,
  description,
  isSaving,
}: SectionHeaderProps) {
  return (
    <div className="flex items-start justify-between">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">{title}</h2>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      {isSaving && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Saving...
        </div>
      )}
    </div>
  );
}
