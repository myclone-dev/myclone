/**
 * Converts workflow data to ReactFlow nodes and edges
 */

import type { Node, Edge } from "reactflow";
import type { Workflow, WorkflowStep } from "@/lib/queries/workflows";
import type { WorkflowNodeData } from "./types";

interface ConversionResult {
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
}

/**
 * Converts a Workflow object to ReactFlow nodes and edges
 * Creates a linear flow: Start → Questions → Result
 */
export function workflowToNodes(workflow: Workflow | null): ConversionResult {
  const nodes: Node<WorkflowNodeData>[] = [];
  const edges: Edge[] = [];

  const steps = workflow?.workflow_config?.steps || [];

  // Start node
  nodes.push({
    id: "start",
    type: "startNode",
    position: { x: 250, y: 50 },
    data: {
      type: "start",
      openingMessage:
        workflow?.opening_message || "Hi! How can I help you today?",
      label: "Start",
    },
    draggable: true,
  });

  // Question nodes
  steps.forEach((step: WorkflowStep, index: number) => {
    const nodeId = step.step_id;
    nodes.push({
      id: nodeId,
      type: "questionNode",
      position: { x: 250, y: 180 + index * 140 },
      data: {
        type: "question",
        step,
        label: step.question_text || `Question ${index + 1}`,
      },
      draggable: true,
    });

    // Edge from previous node
    const sourceId = index === 0 ? "start" : steps[index - 1].step_id;
    edges.push({
      id: `e-${sourceId}-${nodeId}`,
      source: sourceId,
      target: nodeId,
      type: "smoothstep",
      sourceHandle: "source-main",
      targetHandle: "target-main",
    });
  });

  // Result node
  const resultNodeId = "result";
  nodes.push({
    id: resultNodeId,
    type: "resultNode",
    position: { x: 250, y: 180 + steps.length * 140 },
    data: {
      type: "result",
      resultMessage: "Thank you for your responses!",
      label: "End",
    },
    draggable: true,
  });

  // Edge from last question (or start if no questions) to result
  if (steps.length > 0) {
    edges.push({
      id: `e-${steps[steps.length - 1].step_id}-${resultNodeId}`,
      source: steps[steps.length - 1].step_id,
      target: resultNodeId,
      type: "smoothstep",
      sourceHandle: "source-main",
      targetHandle: "target-main",
    });
  } else {
    edges.push({
      id: `e-start-${resultNodeId}`,
      source: "start",
      target: resultNodeId,
      type: "smoothstep",
      sourceHandle: "source-main",
      targetHandle: "target-main",
    });
  }

  return { nodes, edges };
}

/**
 * Creates an empty workflow structure with start and result nodes only
 */
export function createEmptyWorkflowNodes(): ConversionResult {
  return workflowToNodes(null);
}
