"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/ui/numeric-input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Plus, Trash2, Edit, FileText, Loader2 } from "lucide-react";
import type {
  WorkflowStep,
  WorkflowType,
  StepType,
  WorkflowOption,
} from "@/lib/queries/workflows";

// Smart parser for bulk question import
function parseBulkQuestions(
  text: string,
  isScored: boolean,
): Array<{ question: string; options: WorkflowOption[] | null }> {
  const lines = text.split("\n").filter((line) => line.trim());
  const questions: Array<{
    question: string;
    options: WorkflowOption[] | null;
  }> = [];
  let currentQuestion: string | null = null;
  let currentOptions: WorkflowOption[] = [];
  let optionIndex = 0;

  for (const line of lines) {
    const trimmed = line.trim();

    // Check if this is an option line: A) text [score] or A. text - score
    const optionMatch = trimmed.match(
      /^([A-Z])[.)]\s*(.+?)(?:\s*[-\[]\s*(\d+)\s*\]?)?$/i,
    );

    if (optionMatch) {
      // This is an option line
      const [, label, text, score] = optionMatch;
      currentOptions.push({
        label: label.toUpperCase(),
        text: text.trim(),
        score: isScored
          ? score
            ? parseInt(score, 10)
            : optionIndex + 1
          : null,
      });
      optionIndex++;
    } else {
      // This is a question line
      if (currentQuestion) {
        // Save previous question
        questions.push({
          question: currentQuestion,
          options: currentOptions.length > 0 ? currentOptions : null,
        });
      }
      // Start new question
      currentQuestion = trimmed.replace(/^Q[:\d.)\s]+/i, "").trim();
      currentOptions = [];
      optionIndex = 0;
    }
  }

  // Don't forget the last question
  if (currentQuestion) {
    questions.push({
      question: currentQuestion,
      options: currentOptions.length > 0 ? currentOptions : null,
    });
  }

  return questions;
}

interface Step2QuestionsProps {
  initialSteps: WorkflowStep[];
  workflowType: WorkflowType;
  onNext: (data: { steps: WorkflowStep[] }) => void;
  onBack: () => void;
  isLoading?: boolean;
}

export function Step2Questions({
  initialSteps,
  workflowType,
  onNext,
  onBack,
  isLoading = false,
}: Step2QuestionsProps) {
  const [steps, setSteps] = useState<WorkflowStep[]>(initialSteps);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [bulkPasteDialogOpen, setBulkPasteDialogOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  // Update steps when initialSteps changes (for edit mode)
  useEffect(() => {
    if (initialSteps.length > 0) {
      setSteps(initialSteps);
    }
  }, [initialSteps]);

  const handleAddQuestion = () => {
    setEditingIndex(null);
    setEditDialogOpen(true);
  };

  const handleEditQuestion = (index: number) => {
    setEditingIndex(index);
    setEditDialogOpen(true);
  };

  const handleDeleteQuestion = (index: number) => {
    setSteps(steps.filter((_, i) => i !== index));
  };

  const handleSaveQuestion = (step: WorkflowStep) => {
    if (editingIndex !== null) {
      // Update existing
      setSteps(steps.map((s, i) => (i === editingIndex ? step : s)));
    } else {
      // Add new
      setSteps([...steps, step]);
    }
    setEditDialogOpen(false);
    setEditingIndex(null);
  };

  const handleBulkPaste = (text: string) => {
    const parsed = parseBulkQuestions(text, isScored);
    const newSteps = parsed.map((q, index) => ({
      step_id: `q${steps.length + index + 1}`,
      step_type: q.options
        ? ("multiple_choice" as StepType)
        : ("text_input" as StepType),
      question_text: q.question,
      required: true,
      options: q.options,
      validation: null,
    }));
    setSteps([...steps, ...newSteps]);
    setBulkPasteDialogOpen(false);
  };

  const handleSubmit = () => {
    if (steps.length === 0) return;
    onNext({ steps });
  };

  const isScored = workflowType === "scored";

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Add Questions</h2>
        <p className="text-sm text-muted-foreground">
          {isScored
            ? "Create questions and set point values for each answer"
            : "Create questions to collect information"}
        </p>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        <Button onClick={handleAddQuestion} variant="outline" size="sm">
          <Plus className="size-4 mr-2" />
          Add Question
        </Button>
        <Button
          onClick={() => setBulkPasteDialogOpen(true)}
          variant="outline"
          size="sm"
        >
          <FileText className="size-4 mr-2" />
          Paste Multiple
        </Button>
      </div>

      {/* Questions List */}
      <div className="space-y-3">
        {steps.length === 0 ? (
          <Card className="p-8 text-center border-dashed">
            <p className="text-muted-foreground">
              No questions yet. Click "Add Question" to get started.
            </p>
          </Card>
        ) : (
          steps.map((step, index) => (
            <Card key={index} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-muted-foreground">
                      Q{index + 1}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded bg-muted">
                      {step.step_type.replace("_", " ")}
                    </span>
                  </div>
                  <p className="font-medium">{step.question_text}</p>
                  {step.options && (
                    <div className="mt-2 space-y-1">
                      {step.options.map((opt, optIdx) => (
                        <div
                          key={optIdx}
                          className="text-sm text-muted-foreground"
                        >
                          {opt.label}: {opt.text}
                          {opt.score !== null && (
                            <span className="ml-2 text-yellow-bright font-medium">
                              ({opt.score} pts)
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleEditQuestion(index)}
                  >
                    <Edit className="size-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteQuestion(index)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      {/* Summary */}
      {steps.length > 0 && (
        <div className="text-sm text-muted-foreground">
          Total Questions: {steps.length}
          {isScored && (
            <>
              {" • "}
              Score Range:{" "}
              {steps.reduce((min, s) => {
                const minScore = Math.min(
                  ...(s.options?.map((o) => o.score || 0) || [0]),
                );
                return Math.min(min, minScore);
              }, 0)}{" "}
              -{" "}
              {steps.reduce((sum, s) => {
                const maxScore = Math.max(
                  ...(s.options?.map((o) => o.score || 0) || [0]),
                );
                return sum + maxScore;
              }, 0)}
            </>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-between gap-3 pt-4 border-t">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={steps.length === 0 || isLoading}
        >
          {isLoading && <Loader2 className="size-4 mr-2 animate-spin" />}
          {isScored ? "Next: Set Categories" : "Save & Publish"}
        </Button>
      </div>

      {/* Edit Question Dialog */}
      <QuestionEditorDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        initialData={editingIndex !== null ? steps[editingIndex] : undefined}
        questionNumber={
          (editingIndex !== null ? editingIndex : steps.length) + 1
        }
        isScored={isScored}
        onSave={handleSaveQuestion}
      />

      {/* Bulk Paste Dialog */}
      <BulkPasteDialog
        open={bulkPasteDialogOpen}
        onOpenChange={setBulkPasteDialogOpen}
        onPaste={handleBulkPaste}
      />
    </div>
  );
}

// Question Editor Dialog Component
function QuestionEditorDialog({
  open,
  onOpenChange,
  initialData,
  questionNumber,
  isScored,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialData?: WorkflowStep;
  questionNumber: number;
  isScored: boolean;
  onSave: (step: WorkflowStep) => void;
}) {
  const [questionText, setQuestionText] = useState("");
  const [stepType, setStepType] = useState<StepType>("text_input");
  const [options, setOptions] = useState<WorkflowOption[]>([
    { label: "A", text: "", score: 1 },
    { label: "B", text: "", score: 2 },
    { label: "C", text: "", score: 3 },
    { label: "D", text: "", score: 4 },
  ]);

  // Update form when dialog opens or initialData changes
  useEffect(() => {
    if (open) {
      if (initialData) {
        setQuestionText(initialData.question_text);
        setStepType(initialData.step_type);
        setOptions(
          initialData.options || [
            { label: "A", text: "", score: 1 },
            { label: "B", text: "", score: 2 },
            { label: "C", text: "", score: 3 },
            { label: "D", text: "", score: 4 },
          ],
        );
      } else {
        setQuestionText("");
        setStepType("text_input");
        setOptions([
          { label: "A", text: "", score: 1 },
          { label: "B", text: "", score: 2 },
          { label: "C", text: "", score: 3 },
          { label: "D", text: "", score: 4 },
        ]);
      }
    }
  }, [open, initialData]);

  const handleSave = () => {
    const step: WorkflowStep = {
      step_id: initialData?.step_id || `q${questionNumber}`,
      step_type: stepType,
      question_text: questionText,
      required: true,
      options: stepType === "multiple_choice" ? options : null,
      validation: null,
    };
    onSave(step);
    // Reset form
    setQuestionText("");
    setStepType("text_input");
    setOptions([
      { label: "A", text: "", score: 1 },
      { label: "B", text: "", score: 2 },
      { label: "C", text: "", score: 3 },
      { label: "D", text: "", score: 4 },
    ]);
  };

  const isValid =
    questionText.trim() &&
    (stepType !== "multiple_choice" || options.every((o) => o.text.trim()));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {initialData ? "Edit" : "Add"} Question {questionNumber}
          </DialogTitle>
          <DialogDescription>
            Configure the question and answer options
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Question Text *</Label>
            <Textarea
              value={questionText}
              onChange={(e) => setQuestionText(e.target.value)}
              placeholder="What do you want to ask?"
              rows={2}
            />
          </div>

          <div className="space-y-2">
            <Label>Type *</Label>
            <Select
              value={stepType}
              onValueChange={(v) => setStepType(v as StepType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="text_input">Text Input</SelectItem>
                <SelectItem value="text_area">Text Area</SelectItem>
                <SelectItem value="number_input">Number Input</SelectItem>
                <SelectItem value="multiple_choice">Multiple Choice</SelectItem>
                <SelectItem value="yes_no">Yes/No</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {stepType === "multiple_choice" && (
            <div className="space-y-3">
              <Label>Options *</Label>
              {options.map((opt, idx) => (
                <div key={`option-${idx}`} className="flex gap-2">
                  <Input value={opt.label || ""} disabled className="w-16" />
                  <Input
                    placeholder="Option text"
                    value={opt.text || ""}
                    onChange={(e) => {
                      const newOptions = [...options];
                      newOptions[idx].text = e.target.value;
                      setOptions(newOptions);
                    }}
                    className="flex-1"
                  />
                  {isScored && (
                    <NumericInput
                      placeholder="Score"
                      value={opt.score}
                      onChange={(value) => {
                        const newOptions = [...options];
                        newOptions[idx].score = value ?? idx + 1;
                        setOptions(newOptions);
                      }}
                      allowNegative
                      className="w-24"
                    />
                  )}
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  setOptions([
                    ...options,
                    {
                      label: String.fromCharCode(65 + options.length),
                      text: "",
                      score: options.length + 1,
                    },
                  ])
                }
              >
                <Plus className="size-4 mr-2" />
                Add Option
              </Button>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!isValid}>
            Save Question
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Bulk Paste Dialog
function BulkPasteDialog({
  open,
  onOpenChange,
  onPaste,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPaste: (text: string) => void;
}) {
  const [text, setText] = useState("");

  const handlePaste = () => {
    onPaste(text);
    setText("");
  };

  const lineCount = text.split("\n").filter((line) => line.trim()).length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Paste Multiple Questions</DialogTitle>
          <DialogDescription>
            Paste questions with options and scores. Supports multiple formats.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="text-xs space-y-2 bg-muted p-3 rounded-md">
            <p className="font-medium">Example format:</p>
            <pre className="text-xs">
              {`Can you explain your business?
A) No [1]
B) Somewhat [2]
C) Yes, clearly [4]

Do you have a framework?
A. No - 1
B. Working on it - 2
C. Yes, documented - 4`}
            </pre>
            <p className="text-muted-foreground">
              • Questions without options become text inputs
              <br />• Scores in [brackets] or after -dash
            </p>
          </div>

          <Textarea
            placeholder="Paste your questions here..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={12}
            className="font-mono text-sm"
          />
          {lineCount > 0 && (
            <p className="text-sm text-muted-foreground">
              Ready to import (paste above to see parsed questions)
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handlePaste} disabled={lineCount === 0}>
            Add Questions
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
