"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { CheckCircle2 } from "lucide-react";
import type { WorkflowNodeData } from "../utils/types";

/**
 * Result Node - End point for the workflow
 * Displays the result message and has a single input handle
 */
export const ResultNode = memo(function ResultNode({
  data,
  selected,
}: NodeProps<WorkflowNodeData>) {
  const isHorizontal = data.layoutDirection === "horizontal";

  return (
    <div
      className={`
        px-4 py-3 rounded-xl bg-gradient-to-br from-purple-500 to-purple-600
        text-white shadow-lg w-[240px]
        transition-all duration-200
        ${selected ? "ring-2 ring-purple-300 ring-offset-2 ring-offset-background shadow-xl scale-105" : ""}
      `}
    >
      <Handle
        type="target"
        position={isHorizontal ? Position.Left : Position.Top}
        id="target-main"
        className="!w-3 !h-3 !bg-white !border-2 !border-purple-600"
      />
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-white/20 rounded-lg">
          <CheckCircle2 className="w-4 h-4" />
        </div>
        <span className="font-semibold text-sm">Result</span>
      </div>
      <p className="text-xs text-white/90 line-clamp-2">
        {data.resultMessage || "Thank you for your responses!"}
      </p>
    </div>
  );
});
