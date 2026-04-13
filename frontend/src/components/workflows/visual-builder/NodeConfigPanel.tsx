"use client";

import type { Node } from "reactflow";
import {
  X,
  Type,
  AlignLeft,
  Hash,
  List,
  ToggleLeft,
  Trash2,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { WorkflowNodeData } from "./utils/types";
import type {
  StepType,
  WorkflowStep,
  WorkflowOption,
} from "@/lib/queries/workflows";

interface NodeConfigPanelProps {
  node: Node<WorkflowNodeData>;
  onUpdate: (nodeId: string, data: Partial<WorkflowNodeData>) => void;
  onClose: () => void;
  onDelete?: (nodeId: string) => void;
}

const STEP_TYPES: { type: StepType; label: string; description: string }[] = [
  { type: "text_input", label: "Text Input", description: "Short text answer" },
  {
    type: "text_area",
    label: "Long Text",
    description: "Multi-line response",
  },
  { type: "number_input", label: "Number", description: "Numeric input" },
  {
    type: "multiple_choice",
    label: "Multiple Choice",
    description: "Select one option",
  },
  { type: "yes_no", label: "Yes / No", description: "Binary choice" },
];

const stepTypeIcons: Record<StepType, React.ElementType> = {
  text_input: Type,
  text_area: AlignLeft,
  number_input: Hash,
  multiple_choice: List,
  yes_no: ToggleLeft,
};

/**
 * NodeConfigPanel - Right sidebar for editing selected node
 * Shows different fields based on node type (start, question, result)
 */
export function NodeConfigPanel({
  node,
  onUpdate,
  onClose,
  onDelete,
}: NodeConfigPanelProps) {
  const { data } = node;

  const handleStepUpdate = (updates: Partial<WorkflowStep>) => {
    if (data.step) {
      onUpdate(node.id, {
        ...data,
        step: { ...data.step, ...updates },
      });
    }
  };

  const handleOptionUpdate = (
    index: number,
    updates: Partial<WorkflowOption>,
  ) => {
    if (data.step?.options) {
      const newOptions = [...data.step.options];
      newOptions[index] = { ...newOptions[index], ...updates };
      handleStepUpdate({ options: newOptions });
    }
  };

  const handleAddOption = () => {
    if (data.step?.options) {
      const labels = "ABCDEFGHIJ";
      const nextLabel = labels[data.step.options.length] || "?";
      const newOptions: WorkflowOption[] = [
        ...data.step.options,
        { label: nextLabel, text: "", score: null },
      ];
      handleStepUpdate({ options: newOptions });
    }
  };

  const handleRemoveOption = (index: number) => {
    if (data.step?.options && data.step.options.length > 2) {
      const newOptions = data.step.options.filter((_, i) => i !== index);
      // Re-label remaining options
      const labels = "ABCDEFGHIJ";
      const relabeledOptions = newOptions.map((opt, i) => ({
        ...opt,
        label: labels[i] || opt.label,
      }));
      handleStepUpdate({ options: relabeledOptions });
    }
  };

  return (
    <div className="w-80 bg-card border-l border-border h-full overflow-y-auto">
      <div className="p-4 border-b border-border flex items-center justify-between">
        <h3 className="font-semibold text-foreground">
          {data.type === "start"
            ? "Start Node"
            : data.type === "result"
              ? "Result Node"
              : "Question"}
        </h3>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="p-4 space-y-4">
        {/* Start Node Config */}
        {data.type === "start" && (
          <div className="space-y-2">
            <Label>Opening Message</Label>
            <Textarea
              value={data.openingMessage || ""}
              onChange={(e) =>
                onUpdate(node.id, { ...data, openingMessage: e.target.value })
              }
              placeholder="Enter the opening message..."
              rows={3}
            />
            <p className="text-xs text-muted-foreground">
              This message is shown when the workflow starts
            </p>
          </div>
        )}

        {/* Result Node Config */}
        {data.type === "result" && (
          <div className="space-y-2">
            <Label>Result Message</Label>
            <Textarea
              value={data.resultMessage || ""}
              onChange={(e) =>
                onUpdate(node.id, { ...data, resultMessage: e.target.value })
              }
              placeholder="Enter the result message..."
              rows={3}
            />
            <p className="text-xs text-muted-foreground">
              This message is shown when the workflow completes
            </p>
          </div>
        )}

        {/* Question Node Config */}
        {data.type === "question" && data.step && (
          <>
            {/* Question Type Selector */}
            <div className="space-y-2">
              <Label>Question Type</Label>
              <Select
                value={data.step.step_type}
                onValueChange={(value: StepType) => {
                  const updates: Partial<WorkflowStep> = { step_type: value };
                  if (value === "multiple_choice") {
                    updates.options = [
                      { label: "A", text: "", score: null },
                      { label: "B", text: "", score: null },
                    ];
                  } else if (value === "yes_no") {
                    updates.options = [
                      { label: "A", text: "Yes", score: null },
                      { label: "B", text: "No", score: null },
                    ];
                  } else {
                    updates.options = null;
                  }
                  handleStepUpdate(updates);
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STEP_TYPES.map((stepType) => {
                    const Icon = stepTypeIcons[stepType.type];
                    return (
                      <SelectItem key={stepType.type} value={stepType.type}>
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4" />
                          {stepType.label}
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            {/* Question Text */}
            <div className="space-y-2">
              <Label>Question Text</Label>
              <Textarea
                value={data.step.question_text}
                onChange={(e) =>
                  handleStepUpdate({ question_text: e.target.value })
                }
                placeholder="Enter your question..."
                rows={2}
              />
            </div>

            {/* Options Editor (for multiple choice / yes-no) */}
            {(data.step.step_type === "multiple_choice" ||
              data.step.step_type === "yes_no") &&
              data.step.options && (
                <div className="space-y-2">
                  <Label>Options</Label>
                  <div className="space-y-2">
                    {data.step.options.map((option, index) => (
                      <div
                        key={option.label}
                        className="flex items-center gap-2"
                      >
                        <span className="text-xs font-medium text-muted-foreground w-5">
                          {option.label}
                        </span>
                        <Input
                          value={option.text}
                          onChange={(e) =>
                            handleOptionUpdate(index, { text: e.target.value })
                          }
                          placeholder={`Option ${option.label}`}
                          className="flex-1"
                          disabled={data.step?.step_type === "yes_no"}
                        />
                        {data.step?.step_type === "multiple_choice" &&
                          data.step.options!.length > 2 && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-muted-foreground hover:text-destructive"
                              onClick={() => handleRemoveOption(index)}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          )}
                      </div>
                    ))}
                    {data.step.step_type === "multiple_choice" &&
                      data.step.options.length < 10 && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full mt-2"
                          onClick={handleAddOption}
                        >
                          <Plus className="h-4 w-4 mr-2" />
                          Add Option
                        </Button>
                      )}
                  </div>
                </div>
              )}

            {/* Required Toggle */}
            <div className="flex items-center justify-between">
              <Label>Required</Label>
              <Switch
                checked={data.step.required}
                onCheckedChange={(checked) =>
                  handleStepUpdate({ required: checked })
                }
              />
            </div>

            {/* Delete Button */}
            {onDelete && (
              <div className="pt-4 border-t border-border">
                <Button
                  variant="destructive"
                  size="sm"
                  className="w-full"
                  onClick={() => onDelete(node.id)}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Question
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
