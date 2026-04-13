import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

interface SaveButtonsProps {
  hasChanges: boolean;
  isSaving: boolean;
  onSave: () => void;
  onDiscard: () => void;
}

export function SaveButtons({
  hasChanges,
  isSaving,
  onSave,
  onDiscard,
}: SaveButtonsProps) {
  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={onDiscard}
        disabled={!hasChanges || isSaving}
        className="hidden sm:flex hover:bg-red-50 hover:text-red-700 hover:border-red-300"
      >
        Discard
      </Button>
      <Button size="sm" onClick={onSave} disabled={!hasChanges || isSaving}>
        {isSaving && <Loader2 className="size-4 mr-2 animate-spin" />}
        {isSaving ? "Saving..." : "Save"}
      </Button>
    </div>
  );
}
