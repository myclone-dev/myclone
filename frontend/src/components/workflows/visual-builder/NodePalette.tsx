"use client";

import {
  Type,
  AlignLeft,
  Hash,
  List,
  ToggleLeft,
  type LucideIcon,
} from "lucide-react";
import type { StepType } from "@/lib/queries/workflows";
import { ScrollArea } from "@/components/ui/scroll-area";

interface NodePaletteProps {
  onAddNode: (type: StepType) => void;
}

interface PaletteItem {
  type: StepType;
  label: string;
  description: string;
  icon: LucideIcon;
  colorClass: string;
}

const paletteItems: PaletteItem[] = [
  {
    type: "text_input",
    label: "Text Input",
    description: "Short text answer",
    icon: Type,
    colorClass:
      "bg-blue-500/10 text-blue-600 border-blue-200 hover:bg-blue-500/20",
  },
  {
    type: "text_area",
    label: "Long Text",
    description: "Multi-line response",
    icon: AlignLeft,
    colorClass:
      "bg-indigo-500/10 text-indigo-600 border-indigo-200 hover:bg-indigo-500/20",
  },
  {
    type: "number_input",
    label: "Number",
    description: "Numeric input",
    icon: Hash,
    colorClass:
      "bg-violet-500/10 text-violet-600 border-violet-200 hover:bg-violet-500/20",
  },
  {
    type: "multiple_choice",
    label: "Multiple Choice",
    description: "Select one option",
    icon: List,
    colorClass:
      "bg-emerald-500/10 text-emerald-600 border-emerald-200 hover:bg-emerald-500/20",
  },
  {
    type: "yes_no",
    label: "Yes / No",
    description: "Binary choice",
    icon: ToggleLeft,
    colorClass:
      "bg-amber-500/10 text-amber-600 border-amber-200 hover:bg-amber-500/20",
  },
];

/**
 * NodePalette - Sidebar with draggable node types
 * Users can click or drag items to add them to the canvas
 */
export function NodePalette({ onAddNode }: NodePaletteProps) {
  return (
    <div className="absolute top-4 left-4 bottom-4 z-10 w-52 bg-card/95 backdrop-blur-sm rounded-xl border border-border shadow-lg flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="font-semibold text-sm text-foreground">Add Question</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Click or drag to canvas
        </p>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {paletteItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.type}
                onClick={() => onAddNode(item.type)}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData("application/reactflow", item.type);
                  e.dataTransfer.effectAllowed = "move";
                }}
                className={`
                  w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border text-left
                  transition-all duration-150 cursor-grab active:cursor-grabbing ${item.colorClass}
                `}
              >
                <div className="flex-shrink-0">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{item.label}</p>
                  <p className="text-xs opacity-70 truncate">
                    {item.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </ScrollArea>

      {/* Shortcuts Section */}
      <div className="border-t border-border bg-muted/30 p-3">
        <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
          Shortcuts
        </p>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li className="flex items-center gap-2">
            <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono">
              Cmd+C
            </span>
            <span>Copy node</span>
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono">
              Cmd+V
            </span>
            <span>Paste node</span>
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono">
              Cmd+Z
            </span>
            <span>Undo</span>
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono">
              Del
            </span>
            <span>Delete node</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
