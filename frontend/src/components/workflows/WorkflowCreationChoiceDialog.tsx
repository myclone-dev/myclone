"use client";

import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Sparkles,
  GitBranch,
  Crown,
  FlaskConical,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface WorkflowCreationChoiceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Whether the user has enterprise access for node-based editor */
  isEnterprise?: boolean;
}

/**
 * Dialog to choose between using a template, creating a custom workflow,
 * or using the visual node-based editor (Enterprise only, Early Alpha)
 * Shown when user clicks "New Workflow" button
 */
export function WorkflowCreationChoiceDialog({
  open,
  onOpenChange,
  isEnterprise = false,
}: WorkflowCreationChoiceDialogProps) {
  const router = useRouter();

  const handleUseTemplate = () => {
    onOpenChange(false);
    router.push("/dashboard/workflows/templates");
  };

  const handleCreateCustom = () => {
    onOpenChange(false);
    router.push("/dashboard/workflows/new");
  };

  const handleNodeBasedEditor = () => {
    onOpenChange(false);
    router.push("/dashboard/workflows/visual-builder");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[900px]">
        <DialogHeader>
          <DialogTitle>Create a Workflow</DialogTitle>
          <DialogDescription>
            Choose how you want to create your workflow
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-3 py-4">
          {/* Use Template Option */}
          <button
            onClick={handleUseTemplate}
            className="group relative flex flex-col items-center gap-4 rounded-lg border-2 border-muted bg-card p-6 text-center transition-all hover:border-yellow-bright hover:bg-yellow-light/30 focus:outline-none focus:ring-2 focus:ring-yellow-bright focus:ring-offset-2"
          >
            <div className="flex size-12 items-center justify-center rounded-full bg-yellow-light text-yellow-bright group-hover:bg-yellow-bright group-hover:text-white transition-colors">
              <Sparkles className="size-6" />
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold text-lg">Use Template</h3>
              <p className="text-sm text-muted-foreground">
                Start with a pre-built template designed for common workflows
              </p>
            </div>
            <span className="absolute top-3 right-3 text-xs font-medium text-yellow-bright bg-yellow-light px-2 py-1 rounded">
              Recommended
            </span>
          </button>

          {/* Create Custom Option */}
          <button
            onClick={handleCreateCustom}
            className="group flex flex-col items-center gap-4 rounded-lg border-2 border-muted bg-card p-6 text-center transition-all hover:border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-2"
          >
            <div className="flex size-12 items-center justify-center rounded-full bg-gray-100 text-gray-600 group-hover:bg-gray-200 transition-colors">
              <FileText className="size-6" />
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold text-lg">Custom Workflow</h3>
              <p className="text-sm text-muted-foreground">
                Build from scratch with full control over every detail
              </p>
            </div>
          </button>

          {/* Node-Based Visual Editor (Enterprise Only) */}
          <button
            onClick={isEnterprise ? handleNodeBasedEditor : undefined}
            disabled={!isEnterprise}
            className={`group relative flex flex-col items-center gap-4 rounded-lg border-2 p-6 text-center transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 ${
              isEnterprise
                ? "border-muted bg-card hover:border-purple-400 hover:bg-purple-50 focus:ring-purple-400"
                : "border-muted/50 bg-muted/20 cursor-not-allowed opacity-60"
            }`}
          >
            <div
              className={`flex size-12 items-center justify-center rounded-full transition-colors ${
                isEnterprise
                  ? "bg-purple-100 text-purple-600 group-hover:bg-purple-500 group-hover:text-white"
                  : "bg-gray-100 text-gray-400"
              }`}
            >
              <GitBranch className="size-6" />
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold text-lg flex items-center justify-center gap-2">
                Visual Builder
                {!isEnterprise && <Crown className="size-4 text-amber-500" />}
              </h3>
              <p className="text-sm text-muted-foreground">
                Drag-and-drop node editor with branching logic
              </p>
            </div>

            {/* Alpha + Enterprise badges */}
            <div className="absolute top-3 right-3 flex flex-col gap-1">
              <Badge
                variant="outline"
                className="text-[10px] px-1.5 py-0.5 border-purple-300 text-purple-600 bg-purple-50"
              >
                <FlaskConical className="size-3 mr-1" />
                Early Alpha
              </Badge>
              {!isEnterprise && (
                <Badge
                  variant="outline"
                  className="text-[10px] px-1.5 py-0.5 border-amber-300 text-amber-600 bg-amber-50"
                >
                  <Crown className="size-3 mr-1" />
                  Enterprise
                </Badge>
              )}
            </div>
          </button>
        </div>

        <div className="flex justify-end pt-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
