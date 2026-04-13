"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/ui/numeric-input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type {
  WorkflowType,
  TriggerConfig,
  PromotionMode,
} from "@/lib/queries/workflows";
import { getDefaultTriggerConfig } from "@/lib/queries/workflows";
import {
  Workflow as WorkflowIcon,
  ClipboardList,
  ChevronDown,
  Zap,
} from "lucide-react";

interface Step1BasicInfoProps {
  personas: Array<{ id: string; name: string }>;
  initialData: {
    personaId?: string;
    title?: string;
    description?: string;
    workflowType?: WorkflowType;
    workflowObjective?: string;
    triggerConfig?: TriggerConfig | null;
  };
  onNext: (data: {
    personaId: string;
    title: string;
    description: string;
    workflowType: WorkflowType;
    workflowObjective: string | null;
    triggerConfig: TriggerConfig;
  }) => void;
  isEditMode?: boolean;
}

export function Step1BasicInfo({
  personas,
  initialData,
  onNext,
  isEditMode = false,
}: Step1BasicInfoProps) {
  const [personaId, setPersonaId] = useState(initialData.personaId || "");
  const [title, setTitle] = useState(initialData.title || "");
  const [description, setDescription] = useState(initialData.description || "");
  const [workflowType, setWorkflowType] = useState<WorkflowType | "">(
    initialData.workflowType || "",
  );
  const [autoGenerateObjective, setAutoGenerateObjective] = useState(
    !initialData.workflowObjective,
  );
  const [workflowObjective, setWorkflowObjective] = useState(
    initialData.workflowObjective || "",
  );

  // Trigger config state with smart defaults
  const defaultConfig =
    initialData.workflowType &&
    getDefaultTriggerConfig(initialData.workflowType);
  const [promotionMode, setPromotionMode] = useState<PromotionMode>(
    initialData.triggerConfig?.promotion_mode ||
      defaultConfig?.promotion_mode ||
      "contextual",
  );
  const [maxAttempts, setMaxAttempts] = useState<number>(
    initialData.triggerConfig?.max_attempts || defaultConfig?.max_attempts || 3,
  );
  const [cooldownTurns, setCooldownTurns] = useState<number>(
    initialData.triggerConfig?.cooldown_turns ||
      defaultConfig?.cooldown_turns ||
      5,
  );

  // Validation errors state
  const [validationErrors, setValidationErrors] = useState<{
    maxAttempts: string | null;
    cooldownTurns: string | null;
  }>({
    maxAttempts: null,
    cooldownTurns: null,
  });

  // Update state when initialData changes (for edit mode)
  useEffect(() => {
    if (initialData.personaId) setPersonaId(initialData.personaId);
    if (initialData.title) setTitle(initialData.title);
    if (initialData.description !== undefined)
      setDescription(initialData.description);
    if (initialData.workflowType) setWorkflowType(initialData.workflowType);
    if (initialData.workflowObjective !== undefined) {
      setWorkflowObjective(initialData.workflowObjective);
      setAutoGenerateObjective(!initialData.workflowObjective);
    }
    // Handle trigger config with smart defaults
    if (initialData.triggerConfig) {
      setPromotionMode(initialData.triggerConfig.promotion_mode);
      setMaxAttempts(initialData.triggerConfig.max_attempts);
      setCooldownTurns(initialData.triggerConfig.cooldown_turns);
    } else if (initialData.workflowType) {
      const defaults = getDefaultTriggerConfig(initialData.workflowType);
      setPromotionMode(defaults.promotion_mode);
      setMaxAttempts(defaults.max_attempts);
      setCooldownTurns(defaults.cooldown_turns);
    }
  }, [initialData]);

  // Auto-fill promotion_mode when workflow type changes
  const handleWorkflowTypeChange = (newType: WorkflowType) => {
    setWorkflowType(newType);
    // Auto-select promotion mode based on workflow type
    const defaults = getDefaultTriggerConfig(newType);
    setPromotionMode(defaults.promotion_mode);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!personaId || !title || !workflowType) return;

    onNext({
      personaId,
      title,
      description,
      workflowType,
      workflowObjective: autoGenerateObjective ? null : workflowObjective,
      triggerConfig: {
        promotion_mode: promotionMode,
        max_attempts: maxAttempts,
        cooldown_turns: cooldownTurns,
      },
    });
  };

  const isValid = personaId && title && workflowType;

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Basic Information</h2>
        <p className="text-sm text-muted-foreground">
          Set up the basics for your workflow
        </p>
      </div>

      {/* Persona Selector */}
      {!isEditMode && (
        <div className="space-y-2">
          <Label htmlFor="persona">For which persona? *</Label>
          <Select value={personaId} onValueChange={setPersonaId}>
            <SelectTrigger id="persona">
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
          {personas.length === 0 && (
            <p className="text-sm text-amber-600">
              You need to create a persona first before creating a workflow.
            </p>
          )}
        </div>
      )}

      {/* Title */}
      <div className="space-y-2">
        <Label htmlFor="title">Workflow Title *</Label>
        <Input
          id="title"
          placeholder="e.g., Business Growth Readiness Quiz"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
      </div>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="description">Description (optional)</Label>
        <Textarea
          id="description"
          placeholder="For your reference - not shown to users"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
        />
      </div>

      {/* Workflow Type */}
      <div className="space-y-3">
        <Label>Workflow Type *{isEditMode && " (cannot be changed)"}</Label>
        <RadioGroup
          value={workflowType}
          onValueChange={(value: string) =>
            !isEditMode && handleWorkflowTypeChange(value as WorkflowType)
          }
          disabled={isEditMode}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Simple */}
            <label
              htmlFor="type-simple"
              className={`relative flex rounded-lg border p-4 transition-all ${
                workflowType === "simple"
                  ? "border-yellow-bright bg-yellow-bright/10"
                  : "border-border hover:border-yellow-bright/50"
              } ${isEditMode ? "opacity-60 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <div className="flex items-start gap-3 w-full">
                <RadioGroupItem
                  value="simple"
                  id="type-simple"
                  className="mt-1"
                />
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <ClipboardList className="size-5 text-yellow-bright" />
                    <span className="font-semibold">Simple</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Collect information without scoring. Best for intake forms
                    and data collection.
                  </p>
                </div>
              </div>
            </label>

            {/* Scored */}
            <label
              htmlFor="type-scored"
              className={`relative flex rounded-lg border p-4 transition-all ${
                workflowType === "scored"
                  ? "border-yellow-bright bg-yellow-bright/10"
                  : "border-border hover:border-yellow-bright/50"
              } ${isEditMode ? "opacity-60 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <div className="flex items-start gap-3 w-full">
                <RadioGroupItem
                  value="scored"
                  id="type-scored"
                  className="mt-1"
                />
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <WorkflowIcon className="size-5 text-yellow-bright" />
                    <span className="font-semibold">Scored Quiz</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Questions with points and result categories. Best for
                    assessments and qualification.
                  </p>
                </div>
              </div>
            </label>
          </div>
        </RadioGroup>
      </div>

      {/* Advanced Settings - Workflow Objective */}
      <Collapsible>
        <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium hover:text-yellow-bright transition-colors">
          <ChevronDown className="size-4" />
          Advanced Settings (Optional)
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-4 pt-4">
          <div className="flex items-start space-x-2">
            <Checkbox
              id="auto-generate"
              checked={autoGenerateObjective}
              onCheckedChange={(checked) => setAutoGenerateObjective(!!checked)}
            />
            <div className="grid gap-1.5 leading-none">
              <Label htmlFor="auto-generate" className="text-sm font-medium">
                Auto-generate workflow objective using AI
              </Label>
              <p className="text-sm text-muted-foreground">
                Let AI create guidance for when to promote this workflow to
                users
              </p>
            </div>
          </div>

          {!autoGenerateObjective && (
            <div className="space-y-2">
              <Label htmlFor="objective">Workflow Objective</Label>
              <Textarea
                id="objective"
                placeholder="Describe how the AI should guide users toward this workflow..."
                value={workflowObjective}
                onChange={(e) => setWorkflowObjective(e.target.value)}
                rows={4}
              />
            </div>
          )}

          {/* Divider */}
          <div className="border-t pt-4 mt-4">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="size-4 text-yellow-bright" />
              <h3 className="text-sm font-semibold">Promotion Strategy</h3>
            </div>

            {/* Promotion Mode */}
            <div className="space-y-3">
              <Label className="text-sm">
                How should the AI promote this workflow?
              </Label>
              <RadioGroup
                value={promotionMode}
                onValueChange={(value) =>
                  setPromotionMode(value as PromotionMode)
                }
              >
                <div className="space-y-3">
                  {/* Proactive */}
                  <label
                    htmlFor="mode-proactive"
                    className={`relative flex rounded-lg border p-3 cursor-pointer transition-all ${
                      promotionMode === "proactive"
                        ? "border-yellow-bright bg-yellow-bright/5"
                        : "border-border hover:border-yellow-bright/50"
                    }`}
                  >
                    <div className="flex items-start gap-3 w-full">
                      <RadioGroupItem
                        value="proactive"
                        id="mode-proactive"
                        className="mt-0.5"
                      />
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">Proactive</span>
                          {workflowType === "scored" && (
                            <span className="text-xs bg-yellow-bright/20 text-amber-800 font-medium px-2 py-0.5 rounded">
                              Recommended
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Push immediately within 1-2 exchanges. Best for
                          assessments and quizzes.
                        </p>
                      </div>
                    </div>
                  </label>

                  {/* Contextual */}
                  <label
                    htmlFor="mode-contextual"
                    className={`relative flex rounded-lg border p-3 cursor-pointer transition-all ${
                      promotionMode === "contextual"
                        ? "border-yellow-bright bg-yellow-bright/5"
                        : "border-border hover:border-yellow-bright/50"
                    }`}
                  >
                    <div className="flex items-start gap-3 w-full">
                      <RadioGroupItem
                        value="contextual"
                        id="mode-contextual"
                        className="mt-0.5"
                      />
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">
                            Contextual
                          </span>
                          {workflowType === "simple" && (
                            <span className="text-xs bg-yellow-bright/20 text-amber-800 font-medium px-2 py-0.5 rounded">
                              Recommended
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Suggest when conversation naturally aligns. Best for
                          intake forms.
                        </p>
                      </div>
                    </div>
                  </label>

                  {/* Reactive */}
                  <label
                    htmlFor="mode-reactive"
                    className={`relative flex rounded-lg border p-3 cursor-pointer transition-all ${
                      promotionMode === "reactive"
                        ? "border-yellow-bright bg-yellow-bright/5"
                        : "border-border hover:border-yellow-bright/50"
                    }`}
                  >
                    <div className="flex items-start gap-3 w-full">
                      <RadioGroupItem
                        value="reactive"
                        id="mode-reactive"
                        className="mt-0.5"
                      />
                      <div className="flex-1 space-y-1">
                        <span className="font-medium text-sm">Reactive</span>
                        <p className="text-xs text-muted-foreground">
                          Wait for user to explicitly ask. Best for booking or
                          scheduling.
                        </p>
                      </div>
                    </div>
                  </label>
                </div>
              </RadioGroup>
            </div>

            {/* Max Attempts and Cooldown */}
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="max-attempts" className="text-sm">
                  Max Re-attempts
                </Label>
                <NumericInput
                  id="max-attempts"
                  min={1}
                  max={10}
                  value={maxAttempts}
                  onChange={(value) => setMaxAttempts(value ?? 1)}
                  onValidationError={(message) =>
                    setValidationErrors((prev) => ({
                      ...prev,
                      maxAttempts: message,
                    }))
                  }
                />
                {validationErrors.maxAttempts ? (
                  <p className="text-xs text-destructive">
                    {validationErrors.maxAttempts}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">1-10 attempts</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="cooldown-turns" className="text-sm">
                  Cooldown (turns)
                </Label>
                <NumericInput
                  id="cooldown-turns"
                  min={1}
                  max={20}
                  value={cooldownTurns}
                  onChange={(value) => setCooldownTurns(value ?? 1)}
                  onValidationError={(message) =>
                    setValidationErrors((prev) => ({
                      ...prev,
                      cooldownTurns: message,
                    }))
                  }
                />
                {validationErrors.cooldownTurns ? (
                  <p className="text-xs text-destructive">
                    {validationErrors.cooldownTurns}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">1-20 turns</p>
                )}
              </div>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-4 border-t">
        <Button type="submit" disabled={!isValid}>
          Next: Add Questions
        </Button>
      </div>
    </form>
  );
}
