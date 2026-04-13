"use client";

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AgentStatus {
  status: "searching" | "fetching" | "generating" | "idle";
  message?: string;
}

interface AgentStatusIndicatorProps {
  agentStatus: AgentStatus | null;
  className?: string;
}

export function AgentStatusIndicator({
  agentStatus,
  className,
}: AgentStatusIndicatorProps) {
  if (!agentStatus || agentStatus.status === "idle") return null;

  return (
    <div className={cn("flex justify-start", className)}>
      <div className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-2.5 shadow-sm">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-gray-500" />
        <span className="text-sm text-gray-500">
          {agentStatus.message || agentStatus.status}
        </span>
      </div>
    </div>
  );
}
