"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  useWorkflow,
  useUpdateWorkflow,
  useRegenerateWorkflowObjective,
} from "@/lib/queries/workflows";
import type {
  WorkflowType,
  WorkflowStep,
  ResultCategory,
  TriggerConfig,
} from "@/lib/queries/workflows";
import { getDefaultTriggerConfig } from "@/lib/queries/workflows";
import { Step1BasicInfo } from "@/components/workflows/wizard/Step1BasicInfo";
import { Step2Questions } from "@/components/workflows/wizard/Step2Questions";
import { Step3Categories } from "@/components/workflows/wizard/Step3Categories";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Sparkles, RefreshCw } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

/**
 * Edit Workflow Page
 * Uses the same wizard components but pre-populated with existing data
 */
export default function EditWorkflowPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.workflowId as string;

  const { data: workflow, isLoading } = useWorkflow(workflowId);
  const updateWorkflowMutation = useUpdateWorkflow();
  const regenerateObjectiveMutation = useRegenerateWorkflowObjective();

  // Loading state for update mutation
  const isUpdating = updateWorkflowMutation.isPending;

  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);

  // Step 1 data
  const [personaId, setPersonaId] = useState<string>("");
  const [title, setTitle] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [workflowType, setWorkflowType] = useState<WorkflowType | null>(null);
  const [workflowObjective, setWorkflowObjective] = useState<string | null>(
    null,
  );
  const [triggerConfig, setTriggerConfig] = useState<TriggerConfig | null>(
    null,
  );

  // Step 2 data
  const [steps, setSteps] = useState<WorkflowStep[]>([]);

  // Step 3 data
  const [categories, setCategories] = useState<ResultCategory[]>([]);

  // Pre-populate form when workflow loads
  useEffect(() => {
    if (workflow) {
      setPersonaId(workflow.persona_id);
      setTitle(workflow.title);
      setDescription(workflow.description || "");
      setWorkflowType(workflow.workflow_type);
      setWorkflowObjective(workflow.workflow_objective);
      setSteps(workflow.workflow_config.steps);
      if (workflow.result_config) {
        setCategories(workflow.result_config.categories);
      }
      // Handle trigger config with smart defaults for old workflows
      setTriggerConfig(
        workflow.trigger_config ||
          getDefaultTriggerConfig(workflow.workflow_type),
      );
    }
  }, [workflow]);

  const handleStep1Next = (data: {
    personaId: string;
    title: string;
    description: string;
    workflowType: WorkflowType;
    workflowObjective: string | null;
    triggerConfig: TriggerConfig;
  }) => {
    setPersonaId(data.personaId);
    setTitle(data.title);
    setDescription(data.description);
    setWorkflowType(data.workflowType);
    setWorkflowObjective(data.workflowObjective);
    setTriggerConfig(data.triggerConfig);
    setCurrentStep(2);
  };

  const handleStep2Next = (data: { steps: WorkflowStep[] }) => {
    setSteps(data.steps);

    if (workflowType === "scored") {
      setCurrentStep(3);
    } else {
      // Simple workflow - save directly
      handleSave(data.steps, null);
    }
  };

  const handleStep3Finish = (data: { categories: ResultCategory[] }) => {
    setCategories(data.categories);
    handleSave(steps, data.categories);
  };

  const handleSave = async (
    workflowSteps: WorkflowStep[],
    resultCategories: ResultCategory[] | null,
  ) => {
    if (!workflowType) return;

    try {
      await updateWorkflowMutation.mutateAsync({
        workflowId,
        data: {
          title,
          description: description || undefined,
          workflow_objective: workflowObjective || undefined,
          workflow_config: {
            steps: workflowSteps,
          },
          result_config:
            workflowType === "scored" && resultCategories
              ? {
                  scoring_type: "sum",
                  categories: resultCategories,
                }
              : undefined,
          trigger_config: triggerConfig || undefined,
        },
      });

      toast.success("Workflow updated successfully!");
      router.push("/dashboard/workflows");
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      toast.error("Failed to update workflow", {
        description: errorMessage,
      });
    }
  };

  const handleRegenerateObjective = async () => {
    try {
      const updatedWorkflow =
        await regenerateObjectiveMutation.mutateAsync(workflowId);
      setWorkflowObjective(updatedWorkflow.workflow_objective);
      toast.success("Workflow objective regenerated successfully!");
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      toast.error("Failed to regenerate objective", {
        description: errorMessage,
      });
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="space-y-6 animate-pulse">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="h-96 bg-muted rounded-lg" />
        </div>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <p>Workflow not found</p>
      </div>
    );
  }

  const totalSteps = workflowType === "scored" ? 3 : 2;

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/dashboard/workflows">
            <ArrowLeft className="size-4 mr-2" />
            Back
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Edit Workflow</h1>
          <p className="text-sm text-muted-foreground">
            Step {currentStep} of {totalSteps}
          </p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="relative">
        <div className="overflow-hidden h-2 text-xs flex rounded bg-muted">
          <div
            style={{ width: `${(currentStep / totalSteps) * 100}%` }}
            className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-yellow-bright transition-all duration-300"
          />
        </div>
      </div>

      {/* AI Guidance Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Sparkles className="size-5 text-yellow-bright" />
              AI Guidance
            </CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRegenerateObjective}
              disabled={regenerateObjectiveMutation.isPending}
            >
              {regenerateObjectiveMutation.isPending ? (
                <>
                  <RefreshCw className="size-4 mr-2 animate-spin" />
                  Regenerating...
                </>
              ) : (
                <>
                  <RefreshCw className="size-4 mr-2" />
                  Regenerate
                </>
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {workflowObjective ? (
            <p className="text-sm text-muted-foreground leading-relaxed">
              {workflowObjective}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              No AI guidance set. Click &quot;Regenerate&quot; to create
              guidance for when to promote this workflow to users.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Step Content */}
      <div className="bg-card border rounded-lg p-6">
        {currentStep === 1 && (
          <Step1BasicInfo
            personas={[]} // Don't allow changing persona on edit
            initialData={{
              personaId,
              title,
              description,
              workflowType: workflowType || undefined,
              workflowObjective: workflowObjective || undefined,
              triggerConfig: triggerConfig || undefined,
            }}
            onNext={handleStep1Next}
            isEditMode
          />
        )}

        {currentStep === 2 && (
          <Step2Questions
            initialSteps={steps}
            workflowType={workflowType!}
            onNext={handleStep2Next}
            onBack={() => setCurrentStep(1)}
            isLoading={isUpdating}
          />
        )}

        {currentStep === 3 && workflowType === "scored" && (
          <Step3Categories
            steps={steps}
            initialCategories={categories}
            onFinish={handleStep3Finish}
            onBack={() => setCurrentStep(2)}
            isLoading={isUpdating}
          />
        )}
      </div>
    </div>
  );
}
