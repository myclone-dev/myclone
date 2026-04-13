import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

interface NavigationGuardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: () => void;
  onDiscard: () => void;
  isSaving?: boolean;
}

export function NavigationGuard({
  open,
  onOpenChange,
  onSave,
  onDiscard,
  isSaving = false,
}: NavigationGuardProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>You have unsaved changes</AlertDialogTitle>
          <AlertDialogDescription>
            Do you want to save your changes before leaving? Your changes will
            be lost if you don't save them.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSaving}>Cancel</AlertDialogCancel>
          <Button variant="outline" onClick={onDiscard} disabled={isSaving}>
            Discard Changes
          </Button>
          <AlertDialogAction onClick={onSave} disabled={isSaving}>
            {isSaving && <Loader2 className="size-4 mr-2 animate-spin" />}
            {isSaving ? "Saving..." : "Save Changes"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
