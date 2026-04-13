/**
 * Types for the visual node-based workflow editor
 * Bridges between ReactFlow nodes and our WorkflowStep interface
 */

import type { WorkflowStep, StepType } from "@/lib/queries/workflows";

/** Layout direction for node positioning */
export type LayoutDirection = "vertical" | "horizontal";

/** Node types in the visual editor */
export type WorkflowNodeType = "start" | "question" | "result";

/**
 * Data attached to each ReactFlow node
 */
export interface WorkflowNodeData {
  type: WorkflowNodeType;
  /** The workflow step data (only for question nodes) */
  step?: WorkflowStep;
  /** Opening message (only for start node) */
  openingMessage?: string;
  /** Result message (only for result node) */
  resultMessage?: string;
  /** Display label for the node */
  label: string;
  /** Current layout direction (affects handle positions) */
  layoutDirection?: LayoutDirection;
}

/**
 * Step type metadata for the palette
 */
export interface StepTypeMetadata {
  type: StepType;
  label: string;
  description: string;
  icon: string;
  colorClass: string;
}

/**
 * Palette items configuration
 */
export const STEP_TYPE_PALETTE: StepTypeMetadata[] = [
  {
    type: "text_input",
    label: "Text Input",
    description: "Short text answer",
    icon: "Type",
    colorClass:
      "bg-blue-500/10 text-blue-600 border-blue-200 hover:bg-blue-500/20",
  },
  {
    type: "text_area",
    label: "Long Text",
    description: "Multi-line response",
    icon: "AlignLeft",
    colorClass:
      "bg-indigo-500/10 text-indigo-600 border-indigo-200 hover:bg-indigo-500/20",
  },
  {
    type: "number_input",
    label: "Number",
    description: "Numeric input",
    icon: "Hash",
    colorClass:
      "bg-violet-500/10 text-violet-600 border-violet-200 hover:bg-violet-500/20",
  },
  {
    type: "multiple_choice",
    label: "Multiple Choice",
    description: "Select one option",
    icon: "List",
    colorClass:
      "bg-emerald-500/10 text-emerald-600 border-emerald-200 hover:bg-emerald-500/20",
  },
  {
    type: "yes_no",
    label: "Yes / No",
    description: "Binary choice",
    icon: "ToggleLeft",
    colorClass:
      "bg-amber-500/10 text-amber-600 border-amber-200 hover:bg-amber-500/20",
  },
];

/**
 * Color mapping for each step type (used in nodes)
 */
export const STEP_TYPE_COLORS: Record<
  StepType,
  { bg: string; border: string; icon: string }
> = {
  text_input: {
    bg: "from-blue-500 to-blue-600",
    border: "border-blue-400",
    icon: "bg-blue-400/30",
  },
  text_area: {
    bg: "from-indigo-500 to-indigo-600",
    border: "border-indigo-400",
    icon: "bg-indigo-400/30",
  },
  number_input: {
    bg: "from-violet-500 to-violet-600",
    border: "border-violet-400",
    icon: "bg-violet-400/30",
  },
  multiple_choice: {
    bg: "from-emerald-500 to-emerald-600",
    border: "border-emerald-400",
    icon: "bg-emerald-400/30",
  },
  yes_no: {
    bg: "from-amber-500 to-amber-600",
    border: "border-amber-400",
    icon: "bg-amber-400/30",
  },
};

/** Grid size for snap-to-grid feature */
export const GRID_SIZE = 20;

/** Fixed node dimensions for layout calculations */
export const NODE_WIDTH = 240;
export const NODE_HEIGHT = 100;
