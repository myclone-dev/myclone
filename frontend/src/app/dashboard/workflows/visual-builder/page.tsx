"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Save, FlaskConical, Crown } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { NodeEditor } from "@/components/workflows/visual-builder";
import { useUIStore } from "@/store/ui.store";
import { useUserMe } from "@/lib/queries/users";
import { useUserPersonas } from "@/lib/queries/persona";
import { useCreateWorkflow, usePublishWorkflow } from "@/lib/queries/workflows";
import type { Workflow, WorkflowType } from "@/lib/queries/workflows";

/**
 * Visual Workflow Builder Page
 * Enterprise-only, Early Alpha feature for node-based workflow creation
 */
export default function VisualBuilderPage() {
  const router = useRouter();
  const setSidebarCollapsed = useUIStore((state) => state.setSidebarCollapsed);
  const { data: user } = useUserMe();

  // Auto-collapse sidebar for full-screen canvas experience
  useEffect(() => {
    setSidebarCollapsed(true);
  }, [setSidebarCollapsed]);
  const { data: personasData } = useUserPersonas(user?.id || "");
  const personas = personasData?.personas || [];

  const createWorkflowMutation = useCreateWorkflow();
  const publishWorkflowMutation = usePublishWorkflow();

  // Form state
  const [title, setTitle] = useState("Untitled Workflow");
  const [personaId, setPersonaId] = useState<string>("");
  const [workflowType, setWorkflowType] = useState<WorkflowType>("simple");
  const [workflowData, setWorkflowData] = useState<Partial<Workflow>>({
    workflow_config: { steps: [] },
    opening_message: "Hi! How can I help you today?",
  });

  const isSaving =
    createWorkflowMutation.isPending || publishWorkflowMutation.isPending;

  const handleWorkflowChange = useCallback((updated: Partial<Workflow>) => {
    setWorkflowData(updated);
  }, []);

  const handleSave = async () => {
    if (!personaId) {
      toast.error("Please select a persona");
      return;
    }

    if (!title.trim()) {
      toast.error("Please enter a workflow title");
      return;
    }

    const steps = workflowData.workflow_config?.steps || [];
    if (steps.length === 0) {
      toast.error("Please add at least one question");
      return;
    }

    // Validate all questions have text
    const emptyQuestions = steps.filter((s) => !s.question_text?.trim());
    if (emptyQuestions.length > 0) {
      toast.error(
        `${emptyQuestions.length} question(s) are missing text. Click on them to edit.`,
      );
      return;
    }

    try {
      const workflow = await createWorkflowMutation.mutateAsync({
        persona_id: personaId,
        workflow_type: workflowType,
        title: title.trim(),
        description: null,
        opening_message: workflowData.opening_message || null,
        workflow_objective: null,
        workflow_config: workflowData.workflow_config || { steps: [] },
        result_config: null,
        trigger_config: {
          promotion_mode: "contextual",
          max_attempts: 3,
          cooldown_turns: 5,
        },
      });

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

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col -m-6">
      {/* Header */}
      <header className="h-14 border-b border-border bg-card flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/dashboard/workflows">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>

          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-64 h-8 font-semibold"
            placeholder="Workflow title..."
          />

          <Badge
            variant="outline"
            className="text-xs border-purple-300 text-purple-600 bg-purple-50"
          >
            <FlaskConical className="size-3 mr-1" />
            Early Alpha
          </Badge>
          <Badge
            variant="outline"
            className="text-xs border-amber-300 text-amber-600 bg-amber-50"
          >
            <Crown className="size-3 mr-1" />
            Enterprise
          </Badge>
        </div>

        <div className="flex items-center gap-3">
          {/* Persona Selector */}
          <Select value={personaId} onValueChange={setPersonaId}>
            <SelectTrigger className="w-48 h-8">
              <SelectValue placeholder="Select persona..." />
            </SelectTrigger>
            <SelectContent>
              {personas.map((persona) => (
                <SelectItem key={persona.id} value={persona.id}>
                  {persona.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Workflow Type Selector */}
          <Select
            value={workflowType}
            onValueChange={(v) => setWorkflowType(v as WorkflowType)}
          >
            <SelectTrigger className="w-32 h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="simple">Simple</SelectItem>
              <SelectItem value="scored">Scored</SelectItem>
            </SelectContent>
          </Select>

          <Button size="sm" onClick={handleSave} disabled={isSaving}>
            <Save className="h-4 w-4 mr-1" />
            {isSaving ? "Saving..." : "Save & Publish"}
          </Button>
        </div>
      </header>

      {/* Canvas */}
      <div className="flex-1 overflow-hidden">
        <NodeEditor
          workflow={workflowData as Workflow | null}
          onWorkflowChange={handleWorkflowChange}
        />
      </div>
    </div>
  );
}
