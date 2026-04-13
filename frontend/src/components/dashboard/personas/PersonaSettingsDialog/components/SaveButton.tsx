"use client";

import { Button } from "@/components/ui/button";
import { Save, Loader2 } from "lucide-react";

interface SaveButtonProps {
  onClick: () => void;
  isSaving: boolean;
  disabled?: boolean;
}

/**
 * Unified Save Button for PersonaSettings Dialog
 * Shows loading state during save operations
 */
export function SaveButton({ onClick, isSaving, disabled }: SaveButtonProps) {
  return (
    <Button
      onClick={onClick}
      disabled={isSaving || disabled}
      size="lg"
      className="gap-2"
    >
      {isSaving ? (
        <>
          <Loader2 className="size-4 animate-spin" />
          Saving...
        </>
      ) : (
        <>
          <Save className="size-4" />
          Save Changes
        </>
      )}
    </Button>
  );
}
