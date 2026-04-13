"use client";

import { useCallback, useState, useEffect, useRef } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type NodeTypes,
  ReactFlowProvider,
  useReactFlow,
  useUpdateNodeInternals,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  Undo2,
  Redo2,
  LayoutGrid,
  LayoutTemplate,
  FlaskConical,
  Copy,
  Clipboard,
  ArrowDownUp,
  ArrowLeftRight,
} from "lucide-react";
import { toast } from "sonner";

import { StartNode, QuestionNode, ResultNode } from "./nodes";
import { NodeConfigPanel } from "./NodeConfigPanel";
import { NodePalette } from "./NodePalette";
import {
  workflowToNodes,
  createEmptyWorkflowNodes,
} from "./utils/workflowToNodes";
import { nodesToWorkflow } from "./utils/nodesToWorkflow";
import { useNodeHistory } from "./hooks/useNodeHistory";
import type { WorkflowNodeData, LayoutDirection } from "./utils/types";
import { GRID_SIZE } from "./utils/types";
import type { Workflow, StepType, WorkflowStep } from "@/lib/queries/workflows";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";

const nodeTypes: NodeTypes = {
  startNode: StartNode,
  questionNode: QuestionNode,
  resultNode: ResultNode,
};

interface NodeEditorProps {
  workflow: Workflow | null;
  onWorkflowChange: (workflow: Partial<Workflow>) => void;
}

function NodeEditorInner({ workflow, onWorkflowChange }: NodeEditorProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] =
    useState<Node<WorkflowNodeData> | null>(null);
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [layoutDirection, setLayoutDirection] =
    useState<LayoutDirection>("vertical");
  const [clipboard, setClipboard] = useState<Node<WorkflowNodeData> | null>(
    null,
  );
  const { pushState, undo, redo, canUndo, canRedo } = useNodeHistory();
  const reactFlowInstance = useReactFlow();
  const { fitView } = reactFlowInstance;
  const updateNodeInternals = useUpdateNodeInternals();
  const initRef = useRef(false);

  // Check if canvas has question nodes
  const hasQuestionNodes = nodes.some((n) => n.data.type === "question");

  // Check if selected node can be copied (only question nodes)
  const canCopy =
    selectedNode !== null && selectedNode.data.type === "question";

  // Initialize nodes from workflow (or empty)
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    const { nodes: initialNodes, edges: initialEdges } = workflow
      ? workflowToNodes(workflow)
      : createEmptyWorkflowNodes();
    setNodes(initialNodes);
    setEdges(initialEdges);
    pushState(initialNodes, initialEdges);
  }, [workflow, setNodes, setEdges, pushState]);

  // Sync changes back to workflow (debounced)
  useEffect(() => {
    if (!initRef.current) return;
    const timer = setTimeout(() => {
      const updatedWorkflow = nodesToWorkflow(nodes, edges, workflow || {});
      onWorkflowChange(updatedWorkflow);
    }, 300);
    return () => clearTimeout(timer);
  }, [nodes, edges, workflow, onWorkflowChange]);

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => {
        const newEdges = addEdge(
          {
            ...params,
            type: "smoothstep",
            sourceHandle: params.sourceHandle || "source-main",
            targetHandle: params.targetHandle || "target-main",
          },
          eds,
        );
        setTimeout(() => pushState(nodes, newEdges), 0);
        return newEdges;
      });
    },
    [setEdges, nodes, pushState],
  );

  // Drag and drop handlers
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData(
        "application/reactflow",
      ) as StepType;
      if (!type) return;

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const snappedPosition = snapToGrid
        ? {
            x: Math.round(position.x / GRID_SIZE) * GRID_SIZE,
            y: Math.round(position.y / GRID_SIZE) * GRID_SIZE,
          }
        : position;

      const newStep = createEmptyStep(type);
      const questionNodes = nodes.filter((n) => n.data.type === "question");

      const newNode: Node<WorkflowNodeData> = {
        id: newStep.step_id,
        type: "questionNode",
        position: snappedPosition,
        data: {
          type: "question",
          step: newStep,
          label: `Question ${questionNodes.length + 1}`,
        },
        draggable: true,
      };

      setNodes((nds) => [...nds, newNode]);
      setSelectedNode(newNode);
      toast.success(`Added ${type.replace("_", " ")}`);

      setTimeout(() => {
        pushState([...nodes, newNode], edges);
      }, 50);
    },
    [reactFlowInstance, nodes, edges, setNodes, pushState, snapToGrid],
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node<WorkflowNodeData>) => {
      setSelectedNode(node);
    },
    [],
  );

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const handleNodeUpdate = useCallback(
    (nodeId: string, data: Partial<WorkflowNodeData>) => {
      setNodes((nds) => {
        const newNodes = nds.map((node) => {
          if (node.id === nodeId) {
            return { ...node, data: { ...node.data, ...data } };
          }
          return node;
        });
        return newNodes;
      });
      if (selectedNode?.id === nodeId) {
        setSelectedNode((prev) =>
          prev ? { ...prev, data: { ...prev.data, ...data } } : null,
        );
      }
    },
    [setNodes, selectedNode],
  );

  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      const nodeToDelete = nodes.find((n) => n.id === nodeId);
      if (
        !nodeToDelete ||
        nodeToDelete.data.type === "start" ||
        nodeToDelete.data.type === "result"
      ) {
        return;
      }

      const incomingEdge = edges.find((e) => e.target === nodeId);
      const outgoingEdge = edges.find((e) => e.source === nodeId);

      setNodes((nds) => nds.filter((n) => n.id !== nodeId));

      setEdges((eds) => {
        let newEdges = eds.filter(
          (e) => e.source !== nodeId && e.target !== nodeId,
        );

        // Reconnect graph if both incoming and outgoing edges existed
        if (incomingEdge && outgoingEdge) {
          newEdges = [
            ...newEdges,
            {
              id: `e-${incomingEdge.source}-${outgoingEdge.target}`,
              source: incomingEdge.source,
              target: outgoingEdge.target,
              type: "smoothstep",
              sourceHandle: "source-main",
              targetHandle: "target-main",
            },
          ];
        }
        return newEdges;
      });

      if (selectedNode?.id === nodeId) {
        setSelectedNode(null);
      }

      setTimeout(() => {
        pushState(
          nodes.filter((n) => n.id !== nodeId),
          edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
        );
      }, 0);
    },
    [nodes, edges, selectedNode, setNodes, setEdges, pushState],
  );

  const handleAddNode = useCallback(
    (stepType: StepType) => {
      const newStep = createEmptyStep(stepType);
      const questionNodes = nodes.filter((n) => n.data.type === "question");
      const resultNode = nodes.find((n) => n.data.type === "result");
      const lastQuestionNode = questionNodes[questionNodes.length - 1];
      const startNode = nodes.find((n) => n.data.type === "start");

      let xPos = 250;
      let yPos = 200;

      if (lastQuestionNode) {
        xPos = lastQuestionNode.position.x;
        yPos = lastQuestionNode.position.y + 140;
      } else if (startNode) {
        xPos = startNode.position.x;
        yPos = startNode.position.y + 140;
      }

      const newNode: Node<WorkflowNodeData> = {
        id: newStep.step_id,
        type: "questionNode",
        position: { x: xPos, y: yPos },
        data: {
          type: "question",
          step: newStep,
          label: `Question ${questionNodes.length + 1}`,
        },
        draggable: true,
      };

      let updatedNodes: Node<WorkflowNodeData>[] = [];
      let updatedEdges: Edge[] = [];

      // Move result node down if needed
      if (resultNode && resultNode.position.y <= yPos + 100) {
        setNodes((nds) => {
          updatedNodes = nds.map((n) => {
            if (n.id === "result") {
              return { ...n, position: { ...n.position, y: yPos + 160 } };
            }
            return n;
          });
          updatedNodes = [...updatedNodes, newNode];
          return updatedNodes;
        });
      } else {
        setNodes((nds) => {
          updatedNodes = [...nds, newNode];
          return updatedNodes;
        });
      }

      // Update edges
      setEdges((eds) => {
        const sourceId = lastQuestionNode?.id || startNode?.id || "start";
        const filteredEdges = eds.filter(
          (e) => !(e.source === sourceId && e.target === "result"),
        );

        updatedEdges = [
          ...filteredEdges,
          {
            id: `e-${sourceId}-${newNode.id}`,
            source: sourceId,
            target: newNode.id,
            type: "smoothstep",
            sourceHandle: "source-main",
            targetHandle: "target-main",
          },
          {
            id: `e-${newNode.id}-result`,
            source: newNode.id,
            target: "result",
            type: "smoothstep",
            sourceHandle: "source-main",
            targetHandle: "target-main",
          },
        ];

        return updatedEdges;
      });

      setTimeout(() => {
        pushState(updatedNodes, updatedEdges);
      }, 50);

      setSelectedNode(newNode);
    },
    [nodes, setNodes, setEdges, pushState],
  );

  // Fixed node dimensions for layout calculations
  const NODE_WIDTH = 240;
  const NODE_HEIGHT = 100;

  // Auto-layout handler - supports both vertical and horizontal layouts
  const handleAutoLayout = useCallback(
    (directionOverride?: LayoutDirection) => {
      const direction = directionOverride ?? layoutDirection;
      const startNode = nodes.find((n) => n.data.type === "start");
      const resultNode = nodes.find((n) => n.data.type === "result");
      const questionNodes = nodes.filter((n) => n.data.type === "question");

      if (!startNode || !resultNode) return;

      // Sort question nodes by connections
      const orderedQuestions: Node<WorkflowNodeData>[] = [];
      let currentNodeId = "start";

      while (orderedQuestions.length < questionNodes.length) {
        const nextEdge = edges.find(
          (e) => e.source === currentNodeId && e.target !== "result",
        );
        if (!nextEdge) break;

        const nextNode = questionNodes.find((n) => n.id === nextEdge.target);
        if (nextNode) {
          orderedQuestions.push(nextNode);
          currentNodeId = nextNode.id;
        } else {
          break;
        }
      }

      // Add unconnected question nodes
      questionNodes.forEach((qn) => {
        if (!orderedQuestions.find((oq) => oq.id === qn.id)) {
          orderedQuestions.push(qn);
        }
      });

      let updatedNodes: Node<WorkflowNodeData>[];

      if (direction === "vertical") {
        // Vertical: stack top to bottom
        const centerX = 300;
        const startY = 50;
        const nodeSpacing = 150;
        const xPos = centerX - NODE_WIDTH / 2;

        updatedNodes = nodes.map((node) => {
          const newData = { ...node.data, layoutDirection: direction };
          if (node.data.type === "start") {
            return { ...node, data: newData, position: { x: xPos, y: startY } };
          }
          if (node.data.type === "result") {
            const resultY =
              startY + (orderedQuestions.length + 1) * nodeSpacing;
            return {
              ...node,
              data: newData,
              position: { x: xPos, y: resultY },
            };
          }
          if (node.data.type === "question") {
            const index = orderedQuestions.findIndex((q) => q.id === node.id);
            if (index !== -1) {
              return {
                ...node,
                data: newData,
                position: {
                  x: xPos,
                  y: startY + (index + 1) * nodeSpacing,
                },
              };
            }
          }
          return { ...node, data: newData };
        });
      } else {
        // Horizontal: arrange left to right
        const startX = 50;
        const centerY = 150;
        const nodeSpacing = 300;
        const yPos = centerY - NODE_HEIGHT / 2;

        updatedNodes = nodes.map((node) => {
          const newData = { ...node.data, layoutDirection: direction };
          if (node.data.type === "start") {
            return { ...node, data: newData, position: { x: startX, y: yPos } };
          }
          if (node.data.type === "result") {
            const resultX =
              startX + (orderedQuestions.length + 1) * nodeSpacing;
            return {
              ...node,
              data: newData,
              position: { x: resultX, y: yPos },
            };
          }
          if (node.data.type === "question") {
            const index = orderedQuestions.findIndex((q) => q.id === node.id);
            if (index !== -1) {
              return {
                ...node,
                data: newData,
                position: {
                  x: startX + (index + 1) * nodeSpacing,
                  y: yPos,
                },
              };
            }
          }
          return { ...node, data: newData };
        });
      }

      // Force edges to recalculate by generating new edge IDs
      const refreshedEdges = edges.map((edge) => ({
        ...edge,
        id: `${edge.source}-${edge.target}-${Date.now()}`,
        type: "smoothstep",
        sourceHandle: edge.sourceHandle?.startsWith("option-")
          ? edge.sourceHandle
          : "source-main",
        targetHandle: "target-main",
      }));

      setNodes(updatedNodes);
      setEdges(refreshedEdges);

      // Force ReactFlow to recalculate handle positions
      setTimeout(() => {
        updatedNodes.forEach((node) => {
          updateNodeInternals(node.id);
        });
        pushState(updatedNodes, refreshedEdges);
        fitView({ padding: 0.3, duration: 300 });
      }, 50);

      toast.success("Layout organized");
    },
    [
      nodes,
      edges,
      setNodes,
      setEdges,
      pushState,
      fitView,
      layoutDirection,
      updateNodeInternals,
    ],
  );

  // Copy selected node to clipboard
  const handleCopy = useCallback(() => {
    if (!selectedNode || selectedNode.data.type !== "question") return;
    setClipboard(selectedNode);
    toast.success("Copied to clipboard");
  }, [selectedNode]);

  // Paste node from clipboard
  const handlePaste = useCallback(() => {
    if (
      !clipboard ||
      clipboard.data.type !== "question" ||
      !clipboard.data.step
    )
      return;

    const questionNodes = nodes.filter((n) => n.data.type === "question");

    // Create new step with copied data but new ID
    const newStep: WorkflowStep = {
      ...clipboard.data.step,
      step_id: `step-${Date.now()}`,
      question_text: `${clipboard.data.step.question_text} (copy)`,
    };

    const newNode: Node<WorkflowNodeData> = {
      id: newStep.step_id,
      type: "questionNode",
      position: {
        x: clipboard.position.x + 30,
        y: clipboard.position.y + 30,
      },
      data: {
        type: "question",
        step: newStep,
        label: `Question ${questionNodes.length + 1}`,
        layoutDirection,
      },
      draggable: true,
    };

    setNodes((nds) => [...nds, newNode]);
    setSelectedNode(newNode);
    toast.success("Pasted node");

    setTimeout(() => {
      pushState([...nodes, newNode], edges);
    }, 50);
  }, [clipboard, nodes, edges, setNodes, pushState, layoutDirection]);

  // Toggle layout direction and re-layout
  const handleToggleLayout = useCallback(() => {
    const newDirection: LayoutDirection =
      layoutDirection === "vertical" ? "horizontal" : "vertical";
    setLayoutDirection(newDirection);
    // Re-layout with the new direction
    handleAutoLayout(newDirection);
  }, [layoutDirection, handleAutoLayout]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isTyping =
        (e.target as HTMLElement).tagName === "INPUT" ||
        (e.target as HTMLElement).tagName === "TEXTAREA";

      // Delete selected node
      if (
        (e.key === "Delete" || e.key === "Backspace") &&
        selectedNode &&
        !isTyping
      ) {
        e.preventDefault();
        handleDeleteNode(selectedNode.id);
      }

      // Undo: Cmd+Z
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        const state = undo();
        if (state) {
          setNodes(state.nodes as Node<WorkflowNodeData>[]);
          setEdges(state.edges);
          setSelectedNode(null);
          toast.info("Undo");
        }
      }

      // Redo: Cmd+Shift+Z
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "z") {
        e.preventDefault();
        const state = redo();
        if (state) {
          setNodes(state.nodes as Node<WorkflowNodeData>[]);
          setEdges(state.edges);
          setSelectedNode(null);
          toast.info("Redo");
        }
      }

      // Copy: Cmd+C
      if ((e.ctrlKey || e.metaKey) && e.key === "c" && !isTyping) {
        e.preventDefault();
        handleCopy();
      }

      // Paste: Cmd+V
      if ((e.ctrlKey || e.metaKey) && e.key === "v" && !isTyping) {
        e.preventDefault();
        handlePaste();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    selectedNode,
    handleDeleteNode,
    undo,
    redo,
    setNodes,
    setEdges,
    handleCopy,
    handlePaste,
  ]);

  return (
    <div className="flex h-full">
      <div className="flex-1 relative">
        {/* Alpha Badge */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20">
          <Badge
            variant="outline"
            className="text-xs px-3 py-1 border-purple-300 text-purple-600 bg-purple-50/90 backdrop-blur-sm"
          >
            <FlaskConical className="size-3 mr-1.5" />
            Early Alpha - Enterprise Preview
          </Badge>
        </div>

        {/* Toolbar */}
        <div className="absolute top-4 right-4 z-10 flex items-center gap-1 bg-card/95 backdrop-blur-sm rounded-lg border border-border shadow-lg p-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => {
                  const state = undo();
                  if (state) {
                    setNodes(state.nodes as Node<WorkflowNodeData>[]);
                    setEdges(state.edges);
                    setSelectedNode(null);
                    toast.info("Undo");
                  }
                }}
                disabled={!canUndo}
              >
                <Undo2 className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>Undo (Cmd+Z)</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => {
                  const state = redo();
                  if (state) {
                    setNodes(state.nodes as Node<WorkflowNodeData>[]);
                    setEdges(state.edges);
                    setSelectedNode(null);
                    toast.info("Redo");
                  }
                }}
                disabled={!canRedo}
              >
                <Redo2 className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>Redo (Cmd+Shift+Z)</p>
            </TooltipContent>
          </Tooltip>

          <div className="w-px h-5 bg-border mx-1" />

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handleCopy}
                disabled={!canCopy}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>Copy (Cmd+C)</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handlePaste}
                disabled={!clipboard}
              >
                <Clipboard className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>Paste (Cmd+V)</p>
            </TooltipContent>
          </Tooltip>

          <div className="w-px h-5 bg-border mx-1" />

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => handleAutoLayout()}
                disabled={!hasQuestionNodes}
              >
                <LayoutTemplate className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>Auto Layout</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={
                  layoutDirection === "horizontal" ? "secondary" : "ghost"
                }
                size="icon"
                className="h-8 w-8"
                onClick={handleToggleLayout}
              >
                {layoutDirection === "vertical" ? (
                  <ArrowDownUp className="h-4 w-4" />
                ) : (
                  <ArrowLeftRight className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>
                {layoutDirection === "vertical"
                  ? "Switch to Horizontal"
                  : "Switch to Vertical"}
              </p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={snapToGrid ? "secondary" : "ghost"}
                size="icon"
                className="h-8 w-8"
                onClick={() => setSnapToGrid(!snapToGrid)}
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>Snap to Grid {snapToGrid ? "(On)" : "(Off)"}</p>
            </TooltipContent>
          </Tooltip>
        </div>

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onDragOver={onDragOver}
          onDrop={onDrop}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          className="bg-muted/30"
          nodesDraggable={true}
          nodesConnectable={true}
          elementsSelectable={true}
          panOnDrag={true}
          zoomOnScroll={true}
          minZoom={0.3}
          maxZoom={2}
          defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
          snapToGrid={snapToGrid}
          snapGrid={[GRID_SIZE, GRID_SIZE]}
        >
          {snapToGrid && (
            <Background
              variant={BackgroundVariant.Dots}
              gap={GRID_SIZE}
              size={2}
              color="var(--color-workflow-grid-dot)"
            />
          )}
          <Controls
            className="!bg-card !border-border !shadow-lg"
            showInteractive={false}
          />
          <MiniMap
            style={{
              backgroundColor: "var(--color-workflow-minimap-bg)",
              border: "1px solid var(--color-workflow-minimap-border)",
              borderRadius: "0.5rem",
            }}
            nodeColor={(node) => {
              switch (node.data?.type) {
                case "start":
                  return "var(--color-workflow-node-start)";
                case "question":
                  return "var(--color-workflow-node-question)";
                case "result":
                  return "var(--color-workflow-node-result)";
                default:
                  return "var(--color-workflow-node-default)";
              }
            }}
            maskColor="var(--color-workflow-minimap-mask)"
            pannable
            zoomable
          />
        </ReactFlow>

        <NodePalette onAddNode={handleAddNode} />
      </div>

      {selectedNode && (
        <NodeConfigPanel
          node={selectedNode}
          onUpdate={handleNodeUpdate}
          onClose={() => setSelectedNode(null)}
          onDelete={handleDeleteNode}
        />
      )}
    </div>
  );
}

/**
 * Create an empty workflow step
 */
function createEmptyStep(stepType: StepType): WorkflowStep {
  const baseStep: WorkflowStep = {
    step_id: `step-${Date.now()}`,
    step_type: stepType,
    question_text: "",
    required: true,
    options: null,
    validation: null,
  };

  if (stepType === "multiple_choice") {
    baseStep.options = [
      { label: "A", text: "", score: null },
      { label: "B", text: "", score: null },
    ];
  }

  if (stepType === "yes_no") {
    baseStep.options = [
      { label: "A", text: "Yes", score: null },
      { label: "B", text: "No", score: null },
    ];
  }

  return baseStep;
}

/**
 * NodeEditor - Main visual workflow editor component
 * Wraps ReactFlow with a provider for proper context
 */
export function NodeEditor(props: NodeEditorProps) {
  return (
    <ReactFlowProvider>
      <NodeEditorInner {...props} />
    </ReactFlowProvider>
  );
}
