"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import {
  Type,
  AlignLeft,
  Hash,
  List,
  ToggleLeft,
  AlertCircle,
} from "lucide-react";
import type { WorkflowNodeData } from "../utils/types";
import { STEP_TYPE_COLORS } from "../utils/types";
import type { StepType } from "@/lib/queries/workflows";

/**
 * Icon mapping for step types
 */
const stepTypeIcons: Record<StepType, React.ElementType> = {
  text_input: Type,
  text_area: AlignLeft,
  number_input: Hash,
  multiple_choice: List,
  yes_no: ToggleLeft,
};

/**
 * Validation helper for question nodes
 */
function validateNode(data: WorkflowNodeData): {
  isValid: boolean;
  errors: string[];
} {
  const errors: string[] = [];
  const step = data.step;

  if (!step) return { isValid: false, errors: ["No step data"] };

  if (!step.question_text || step.question_text.trim() === "") {
    errors.push("Question text is required");
  }

  if (
    (step.step_type === "multiple_choice" || step.step_type === "yes_no") &&
    step.options
  ) {
    const emptyOptions = step.options.filter(
      (opt) => !opt.text || opt.text.trim() === "",
    );
    if (emptyOptions.length > 0) {
      errors.push("All options need text");
    }
  }

  return { isValid: errors.length === 0, errors };
}

/**
 * Check if step type supports branching (multiple output paths)
 */
function supportsBranching(stepType: StepType): boolean {
  return stepType === "multiple_choice" || stepType === "yes_no";
}

/**
 * Question Node - Represents a workflow step/question
 * Supports different input types and conditional branching handles
 */
export const QuestionNode = memo(function QuestionNode({
  data,
  selected,
}: NodeProps<WorkflowNodeData>) {
  const step = data.step;
  const isHorizontal = data.layoutDirection === "horizontal";

  if (!step) return null;

  const Icon = stepTypeIcons[step.step_type] || Type;
  const colors =
    STEP_TYPE_COLORS[step.step_type] || STEP_TYPE_COLORS.text_input;
  const { isValid, errors } = validateNode(data);
  const hasBranching =
    supportsBranching(step.step_type) &&
    step.options &&
    step.options.length > 0;

  return (
    <div
      className={`
        px-4 py-3 rounded-xl bg-gradient-to-br ${colors.bg}
        text-white shadow-lg w-[240px]
        transition-all duration-200
        ${selected ? "ring-2 ring-white/50 ring-offset-2 ring-offset-background shadow-xl scale-105" : ""}
        ${!isValid ? "ring-2 ring-destructive ring-offset-1 ring-offset-background" : ""}
      `}
    >
      <Handle
        type="target"
        position={isHorizontal ? Position.Left : Position.Top}
        id="target-main"
        className="!w-3 !h-3 !bg-white !border-2 !border-current"
      />

      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 ${colors.icon} rounded-lg`}>
          <Icon className="w-4 h-4" />
        </div>
        <span className="font-medium text-xs uppercase tracking-wide opacity-90">
          {step.step_type.replace("_", " ")}
        </span>
        {!isValid && (
          <span
            className="ml-auto flex items-center gap-1 text-[10px] bg-destructive/90 px-1.5 py-0.5 rounded"
            title={errors.join(", ")}
          >
            <AlertCircle className="w-3 h-3" />
            Incomplete
          </span>
        )}
        {isValid && step.required && (
          <span className="ml-auto text-[10px] bg-white/20 px-1.5 py-0.5 rounded">
            Required
          </span>
        )}
      </div>

      <p
        className={`text-sm font-medium line-clamp-2 ${!step.question_text ? "opacity-50 italic" : ""}`}
      >
        {step.question_text || "Enter your question..."}
      </p>

      {step.options && step.options.length > 0 && (
        <p className="mt-1 text-[10px] text-white/60 truncate">
          {step.options.map((opt) => opt.text || opt.label).join(" - ")}
        </p>
      )}

      {/* Default bottom handle for linear flow */}
      {!hasBranching && (
        <Handle
          type="source"
          position={isHorizontal ? Position.Right : Position.Bottom}
          id="source-main"
          className="!w-3 !h-3 !bg-white !border-2 !border-current"
        />
      )}

      {/* Multiple handles for branching options */}
      {hasBranching && step.options && (
        <>
          {step.options.map((option, idx) => {
            const totalOptions = step.options!.length;
            // Spread handles vertically across the node
            const startPercent = 35;
            const endPercent = 92;
            const range = endPercent - startPercent;
            const topPercent =
              totalOptions === 1
                ? 60
                : startPercent + idx * (range / (totalOptions - 1));

            return (
              <Handle
                key={option.label}
                type="source"
                position={Position.Right}
                id={`option-${option.label}`}
                style={{ top: `${topPercent}%` }}
                className="!w-2.5 !h-2.5 !bg-emerald-400 !border-2 !border-white hover:!bg-emerald-300 transition-colors"
                title={option.text || `Option ${option.label}`}
              />
            );
          })}
          {/* Keep a default handle for linear flow */}
          <Handle
            type="source"
            position={isHorizontal ? Position.Right : Position.Bottom}
            id="source-main"
            className="!w-3 !h-3 !bg-white !border-2 !border-current"
          />
        </>
      )}
    </div>
  );
});
