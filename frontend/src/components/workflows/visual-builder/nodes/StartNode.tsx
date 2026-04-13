"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { MessageCircle } from "lucide-react";
import type { WorkflowNodeData } from "../utils/types";

/**
 * Start Node - Entry point for the workflow
 * Displays the opening message and has a single output handle
 */
export const StartNode = memo(function StartNode({
  data,
  selected,
}: NodeProps<WorkflowNodeData>) {
  const isHorizontal = data.layoutDirection === "horizontal";

  return (
    <div
      className={`
        px-4 py-3 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600
        text-white shadow-lg w-[240px]
        transition-all duration-200
        ${selected ? "ring-2 ring-emerald-300 ring-offset-2 ring-offset-background shadow-xl scale-105" : ""}
      `}
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-white/20 rounded-lg">
          <MessageCircle className="w-4 h-4" />
        </div>
        <span className="font-semibold text-sm">Start</span>
      </div>
      <p className="text-xs text-white/90 line-clamp-2">
        {data.openingMessage || "Opening message..."}
      </p>
      <Handle
        type="source"
        position={isHorizontal ? Position.Right : Position.Bottom}
        id="source-main"
        className="!w-3 !h-3 !bg-white !border-2 !border-emerald-600"
      />
    </div>
  );
});
