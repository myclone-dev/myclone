/**
 * Converts ReactFlow nodes and edges back to workflow data
 */

import type { Node, Edge } from "reactflow";
import type {
  Workflow,
  WorkflowStep,
  WorkflowConfig,
} from "@/lib/queries/workflows";
import type { WorkflowNodeData } from "./types";

/**
 * Converts ReactFlow nodes/edges back to a Workflow object
 * Traverses the graph from start node following edges to determine step order
 */
export function nodesToWorkflow(
  nodes: Node<WorkflowNodeData>[],
  edges: Edge[],
  existingWorkflow: Partial<Workflow>,
): Partial<Workflow> {
  // Build adjacency map from edges
  const adjacencyMap = new Map<string, string>();
  edges.forEach((edge) => {
    // Only use main source handle edges for ordering (skip branching handles)
    if (!edge.sourceHandle || edge.sourceHandle === "source-main") {
      adjacencyMap.set(edge.source, edge.target);
    }
  });

  // Find start node
  const startNode = nodes.find((n) => n.data.type === "start");

  // Extract opening message from start node
  const openingMessage =
    startNode?.data.openingMessage || existingWorkflow.opening_message;

  // Traverse from start to build ordered steps
  const orderedSteps: WorkflowStep[] = [];
  let currentId = "start";
  const visited = new Set<string>();

  while (adjacencyMap.has(currentId) && !visited.has(currentId)) {
    visited.add(currentId);
    const nextId = adjacencyMap.get(currentId)!;
    const nextNode = nodes.find((n) => n.id === nextId);

    if (nextNode?.data.type === "question" && nextNode.data.step) {
      orderedSteps.push(nextNode.data.step);
    }

    currentId = nextId;
  }

  // Build workflow config
  const workflowConfig: WorkflowConfig = {
    steps: orderedSteps,
  };

  return {
    ...existingWorkflow,
    opening_message: openingMessage,
    workflow_config: workflowConfig,
  };
}

/**
 * Validates the node graph for common issues
 */
export function validateNodeGraph(
  nodes: Node<WorkflowNodeData>[],
  edges: Edge[],
): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];

  // Must have start node
  const hasStart = nodes.some((n) => n.data.type === "start");
  if (!hasStart) {
    errors.push("Missing start node");
  }

  // Must have result node
  const hasResult = nodes.some((n) => n.data.type === "result");
  if (!hasResult) {
    errors.push("Missing result node");
  }

  // All question nodes should have question text
  const questionNodes = nodes.filter((n) => n.data.type === "question");
  questionNodes.forEach((node, index) => {
    if (!node.data.step?.question_text?.trim()) {
      errors.push(`Question ${index + 1} has no text`);
    }

    // Multiple choice needs at least 2 options
    if (
      node.data.step?.step_type === "multiple_choice" &&
      (!node.data.step?.options || node.data.step.options.length < 2)
    ) {
      errors.push(`Question ${index + 1} needs at least 2 options`);
    }
  });

  // Check for disconnected nodes
  const connectedNodeIds = new Set<string>();
  edges.forEach((edge) => {
    connectedNodeIds.add(edge.source);
    connectedNodeIds.add(edge.target);
  });

  // Start and result should always be connected if there are edges
  if (edges.length > 0) {
    if (!connectedNodeIds.has("start")) {
      errors.push("Start node is not connected");
    }
    if (!connectedNodeIds.has("result")) {
      errors.push("Result node is not connected");
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}
