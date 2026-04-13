"use client";

import { useState } from "react";
import { useUserMe } from "@/lib/queries/users";
import { useUserPersonas } from "@/lib/queries/persona";
import { useWorkflows, useDeleteWorkflow } from "@/lib/queries/workflows";
import { useUserSubscription } from "@/lib/queries/tier";
import { WorkflowCard } from "@/components/workflows/WorkflowCard";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Workflow as WorkflowIcon, Plus, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
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
import { DuplicateWorkflowDialog } from "@/components/workflows/DuplicateWorkflowDialog";
import { WorkflowCreationChoiceDialog } from "@/components/workflows/WorkflowCreationChoiceDialog";

/**
 * Workflows List Page
 * Shows all workflows across all personas with filtering
 */
export default function WorkflowsPage() {
  const { data: user, isLoading: userLoading } = useUserMe();
  const { data: personasData } = useUserPersonas(user?.id || "");
  const { data: subscription } = useUserSubscription();
  const personas = personasData?.personas || [];

  // Enterprise tier is tier_id === 3
  const isEnterprise = subscription?.tier_id === 3;

  const [selectedPersonaId, setSelectedPersonaId] = useState<string>("all");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [creationChoiceDialogOpen, setCreationChoiceDialogOpen] =
    useState(false);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(
    null,
  );

  const { data: workflowsData, isLoading: workflowsLoading } = useWorkflows({
    persona_id: selectedPersonaId === "all" ? undefined : selectedPersonaId,
  });

  const deleteWorkflowMutation = useDeleteWorkflow();

  const handleDelete = (workflowId: string) => {
    setSelectedWorkflowId(workflowId);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (!selectedWorkflowId) return;

    deleteWorkflowMutation.mutate(selectedWorkflowId, {
      onSuccess: () => {
        toast.success("Workflow deleted successfully");
        setDeleteDialogOpen(false);
        setSelectedWorkflowId(null);
      },
      onError: (error: Error) => {
        toast.error("Failed to delete workflow", {
          description: error.message,
        });
      },
    });
  };

  const handleDuplicate = (workflowId: string) => {
    setSelectedWorkflowId(workflowId);
    setDuplicateDialogOpen(true);
  };

  if (userLoading) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="space-y-6 animate-pulse">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-64 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const workflows = workflowsData?.workflows || [];

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2 sm:gap-3">
            <WorkflowIcon className="size-6 sm:size-8 text-yellow-bright shrink-0" />
            <span>Workflows</span>
            <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-amber-700 border border-amber-300">
              Beta
            </span>
          </h1>
          <p className="text-sm sm:text-base text-muted-foreground">
            Create questionnaires and collect structured data from your
            conversations
          </p>
        </div>
        <Button
          onClick={() => setCreationChoiceDialogOpen(true)}
          className="shrink-0"
        >
          <Plus className="size-4 mr-2" />
          New Workflow
        </Button>
      </div>

      {/* Beta Warning Banner */}
      <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
        <AlertTriangle className="size-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-sm font-medium text-amber-800">
            This feature is in beta
          </p>
          <p className="text-sm text-amber-700">
            Workflows is still under development and may not work as expected.
            We&apos;re actively improving this feature based on your feedback.
          </p>
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-4">
        <label className="text-sm font-medium">Filter by Persona:</label>
        <Select value={selectedPersonaId} onValueChange={setSelectedPersonaId}>
          <SelectTrigger className="w-[250px]">
            <SelectValue placeholder="All Personas" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Personas</SelectItem>
            {personas.map((persona) => (
              <SelectItem key={persona.id} value={persona.id}>
                {persona.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Workflows Grid */}
      {workflowsLoading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-64 bg-muted rounded-lg animate-pulse" />
          ))}
        </div>
      ) : workflows.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <div className="mb-4 flex size-20 items-center justify-center rounded-full bg-yellow-light">
            <WorkflowIcon className="size-10 text-yellow-bright" />
          </div>
          <h3 className="mb-2 text-lg font-semibold">No workflows yet</h3>
          <p className="mb-6 text-sm text-muted-foreground max-w-md">
            Create your first workflow to start collecting structured
            information from your conversations. Build quizzes, intake forms, or
            assessments.
          </p>
          <Button onClick={() => setCreationChoiceDialogOpen(true)}>
            <Plus className="size-4 mr-2" />
            Create Your First Workflow
          </Button>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {workflows.map((workflow) => {
            const persona = personas.find((p) => p.id === workflow.persona_id);
            return (
              <WorkflowCard
                key={workflow.id}
                workflow={workflow}
                personaName={persona?.name}
                completionCount={workflow.completed_sessions}
                completionRate={workflow.completion_rate}
                onDuplicate={handleDuplicate}
                onDelete={handleDelete}
              />
            );
          })}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Workflow?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this workflow and all associated
              data. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteWorkflowMutation.isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Duplicate Workflow Dialog */}
      {selectedWorkflowId && (
        <DuplicateWorkflowDialog
          open={duplicateDialogOpen}
          onOpenChange={setDuplicateDialogOpen}
          workflowId={selectedWorkflowId}
          personas={personas}
        />
      )}

      {/* Creation Choice Dialog */}
      <WorkflowCreationChoiceDialog
        open={creationChoiceDialogOpen}
        onOpenChange={setCreationChoiceDialogOpen}
        isEnterprise={isEnterprise}
      />
    </div>
  );
}
