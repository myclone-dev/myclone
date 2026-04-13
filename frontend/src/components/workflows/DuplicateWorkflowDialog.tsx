"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { useDuplicateWorkflow } from "@/lib/queries/workflows";
import { toast } from "sonner";

interface DuplicateWorkflowDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workflowId: string;
  personas: Array<{ id: string; name: string }>;
}

export function DuplicateWorkflowDialog({
  open,
  onOpenChange,
  workflowId,
  personas,
}: DuplicateWorkflowDialogProps) {
  const [targetPersonaId, setTargetPersonaId] = useState<string>("");
  const duplicateMutation = useDuplicateWorkflow();

  const handleDuplicate = () => {
    if (!targetPersonaId) {
      toast.error("Please select a persona");
      return;
    }

    duplicateMutation.mutate(
      { workflowId, targetPersonaId },
      {
        onSuccess: (data) => {
          toast.success("Workflow duplicated successfully", {
            description: `Created "${data.title}" for selected persona`,
          });
          onOpenChange(false);
          setTargetPersonaId("");
        },
        onError: (error: Error) => {
          toast.error("Failed to duplicate workflow", {
            description: error.message,
          });
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Duplicate Workflow</DialogTitle>
          <DialogDescription>
            Create a copy of this workflow for another persona
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Copy to Persona:</label>
            <Select value={targetPersonaId} onValueChange={setTargetPersonaId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a persona" />
              </SelectTrigger>
              <SelectContent>
                {personas.map((persona) => (
                  <SelectItem key={persona.id} value={persona.id}>
                    {persona.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleDuplicate}
            disabled={!targetPersonaId || duplicateMutation.isPending}
          >
            {duplicateMutation.isPending
              ? "Duplicating..."
              : "Duplicate Workflow"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
