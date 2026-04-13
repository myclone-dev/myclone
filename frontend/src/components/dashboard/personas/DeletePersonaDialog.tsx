"use client";

import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useDeletePersona } from "@/lib/queries/persona";
import { toast } from "sonner";

interface DeletePersonaDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  personaId: string;
  personaName: string;
}

export function DeletePersonaDialog({
  open,
  onOpenChange,
  personaId,
  personaName,
}: DeletePersonaDialogProps) {
  const deletePersona = useDeletePersona();

  const handleDelete = () => {
    deletePersona.mutate(personaId, {
      onSuccess: (data) => {
        toast.success("Persona deleted", {
          description: data.message,
        });
        onOpenChange(false);
      },
      onError: (error: Error) => {
        toast.error("Failed to delete persona", {
          description: error.message,
        });
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="size-5 text-red-600" />
            Delete Persona
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to delete <strong>{personaName}</strong>? This
            action cannot be undone.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 cursor-pointer"
              onClick={() => onOpenChange(false)}
              disabled={deletePersona.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              className="flex-1 cursor-pointer"
              onClick={handleDelete}
              disabled={deletePersona.isPending}
            >
              {deletePersona.isPending ? "Deleting..." : "Delete"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
