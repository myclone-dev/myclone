"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { WorkflowTemplate } from "@/lib/queries/workflows";
import type { PersonaWithKnowledgeResponse } from "@/lib/queries/persona";
import { useEnableTemplate } from "@/lib/queries/workflows";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { getTierDisplayName } from "@/lib/utils/tierMapping";
import { Badge } from "@/components/ui/badge";

interface EnableTemplateDialogProps {
  template: WorkflowTemplate | null;
  personas: PersonaWithKnowledgeResponse[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Dialog to enable a workflow template for a specific persona
 */
export function EnableTemplateDialog({
  template,
  personas,
  open,
  onOpenChange,
}: EnableTemplateDialogProps) {
  const router = useRouter();
  const [selectedPersonaId, setSelectedPersonaId] = useState<string>("");
  const [autoPublish, setAutoPublish] = useState(true);

  const enableTemplateMutation = useEnableTemplate();

  const handleEnable = async () => {
    if (!template || !selectedPersonaId) {
      toast.error("Please select a persona");
      return;
    }

    try {
      const workflow = await enableTemplateMutation.mutateAsync({
        persona_id: selectedPersonaId,
        template_id: template.id,
        auto_publish: autoPublish,
      });

      toast.success("Template enabled successfully!", {
        description: autoPublish
          ? `${template.template_name} is now live`
          : `${template.template_name} has been added as a draft`,
        action: {
          label: "View Workflow",
          onClick: () =>
            router.push(`/dashboard/workflows/${workflow.id}/edit`),
        },
      });

      onOpenChange(false);
      setSelectedPersonaId("");
      setAutoPublish(true);

      // Redirect to workflows list
      router.push("/dashboard/workflows");
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      toast.error("Failed to enable template", {
        description: errorMessage,
      });
    }
  };

  const selectedPersona = personas.find((p) => p.id === selectedPersonaId);

  // Infer question count
  const questionCount = template
    ? (() => {
        const config = template.workflow_config;
        if ("steps" in config && Array.isArray(config.steps)) {
          return config.steps.length;
        }
        if ("required_fields" in config || "optional_fields" in config) {
          const required = Array.isArray(config.required_fields)
            ? config.required_fields.length
            : 0;
          const optional = Array.isArray(config.optional_fields)
            ? config.optional_fields.length
            : 0;
          return required + optional;
        }
        return 0;
      })()
    : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Enable Template</DialogTitle>
          <DialogDescription>
            Add this template to one of your personas
          </DialogDescription>
        </DialogHeader>

        {template && (
          <div className="space-y-6 py-4">
            {/* Template Info */}
            <div className="rounded-lg border bg-muted/50 p-4 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold">{template.template_name}</h3>
                <Badge variant="outline" className="shrink-0">
                  {getTierDisplayName(template.minimum_plan_tier_id)}
                </Badge>
              </div>
              {template.description && (
                <p className="text-sm text-muted-foreground">
                  {template.description}
                </p>
              )}
              <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2">
                {questionCount && questionCount > 0 && (
                  <span>
                    <span className="font-medium text-foreground">
                      {questionCount}
                    </span>{" "}
                    {questionCount === 1 ? "question" : "questions"}
                  </span>
                )}
                <span className="capitalize">{template.workflow_type}</span>
              </div>
            </div>

            {/* Persona Selection */}
            <div className="space-y-2">
              <Label htmlFor="persona">
                Select Persona <span className="text-destructive">*</span>
              </Label>
              <Select
                value={selectedPersonaId}
                onValueChange={setSelectedPersonaId}
              >
                <SelectTrigger id="persona">
                  <SelectValue placeholder="Choose a persona" />
                </SelectTrigger>
                <SelectContent>
                  {personas.length === 0 ? (
                    <div className="p-2 text-sm text-muted-foreground text-center">
                      No personas available
                    </div>
                  ) : (
                    personas.map((persona) => (
                      <SelectItem key={persona.id} value={persona.id}>
                        {persona.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              {selectedPersona && (
                <p className="text-xs text-muted-foreground">
                  This workflow will be added to {selectedPersona.name}
                </p>
              )}
            </div>

            {/* Auto-Publish Option */}
            <div className="flex items-start space-x-3 rounded-md border p-4">
              <Checkbox
                id="auto-publish"
                checked={autoPublish}
                onCheckedChange={(checked) =>
                  setAutoPublish(checked as boolean)
                }
              />
              <div className="flex-1 space-y-1">
                <Label
                  htmlFor="auto-publish"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                >
                  Publish immediately
                </Label>
                <p className="text-xs text-muted-foreground">
                  {autoPublish
                    ? "The workflow will be active and ready to use right away"
                    : "The workflow will be saved as a draft for you to review and customize"}
                </p>
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              onOpenChange(false);
              setSelectedPersonaId("");
              setAutoPublish(true);
            }}
            disabled={enableTemplateMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleEnable}
            disabled={!selectedPersonaId || enableTemplateMutation.isPending}
          >
            {enableTemplateMutation.isPending
              ? "Enabling..."
              : "Enable Template"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
