"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useUserMe } from "@/lib/queries/users";
import { useUserPersonas } from "@/lib/queries/persona";
import { useCreateWorkflow, usePublishWorkflow } from "@/lib/queries/workflows";
import type {
  WorkflowType,
  WorkflowStep,
  ResultCategory,
  TriggerConfig,
} from "@/lib/queries/workflows";
import { Step1BasicInfo } from "@/components/workflows/wizard/Step1BasicInfo";
import { Step2Questions } from "@/components/workflows/wizard/Step2Questions";
import { Step3Categories } from "@/components/workflows/wizard/Step3Categories";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

/**
 * Create Workflow Wizard
 * 3-step process: Basic Info → Questions → Categories (if scored)
 */
export default function NewWorkflowPage() {
  const router = useRouter();
  const { data: user } = useUserMe();
  const { data: personasData } = useUserPersonas(user?.id || "");
  const personas = personasData?.personas || [];

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

  const createWorkflowMutation = useCreateWorkflow();
  const publishWorkflowMutation = usePublishWorkflow();

  // Combined loading state for both mutations
  const isPublishing =
    createWorkflowMutation.isPending || publishWorkflowMutation.isPending;

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
      handleSaveAndPublish(data.steps, null);
    }
  };

  const handleStep3Finish = (data: { categories: ResultCategory[] }) => {
    setCategories(data.categories);
    handleSaveAndPublish(steps, data.categories);
  };

  const handleSaveAndPublish = async (
    workflowSteps: WorkflowStep[],
    resultCategories: ResultCategory[] | null,
  ) => {
    if (!workflowType) return;

    try {
      // Create workflow
      const workflow = await createWorkflowMutation.mutateAsync({
        persona_id: personaId,
        workflow_type: workflowType,
        title,
        description: description || null,
        opening_message: null,
        workflow_objective: workflowObjective,
        workflow_config: {
          steps: workflowSteps,
        },
        result_config:
          workflowType === "scored" && resultCategories
            ? {
                scoring_type: "sum",
                categories: resultCategories,
              }
            : null,
        trigger_config: triggerConfig,
      });

      // Publish immediately
      await publishWorkflowMutation.mutateAsync(workflow.id);

      toast.success("Workflow created and published!", {
        description: `${title} is now live`,
      });

      router.push("/dashboard/workflows");
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      toast.error("Failed to create workflow", {
        description: errorMessage,
      });
    }
  };

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
          <h1 className="text-2xl font-bold">Create Workflow</h1>
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

      {/* Step Content */}
      <div className="bg-card border rounded-lg p-6">
        {currentStep === 1 && (
          <Step1BasicInfo
            personas={personas}
            initialData={{
              personaId,
              title,
              description,
              workflowType: workflowType || undefined,
              workflowObjective: workflowObjective || undefined,
              triggerConfig: triggerConfig || undefined,
            }}
            onNext={handleStep1Next}
          />
        )}

        {currentStep === 2 && (
          <Step2Questions
            initialSteps={steps}
            workflowType={workflowType!}
            onNext={handleStep2Next}
            onBack={() => setCurrentStep(1)}
            isLoading={isPublishing}
          />
        )}

        {currentStep === 3 && workflowType === "scored" && (
          <Step3Categories
            steps={steps}
            initialCategories={categories}
            onFinish={handleStep3Finish}
            onBack={() => setCurrentStep(2)}
            isLoading={isPublishing}
          />
        )}
      </div>
    </div>
  );
}
