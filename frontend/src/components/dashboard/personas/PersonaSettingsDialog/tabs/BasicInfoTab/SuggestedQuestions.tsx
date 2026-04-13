"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  HelpCircle,
  RefreshCw,
  Edit2,
  X,
  Check,
  Trash2,
  Plus,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import {
  useGetSuggestedQuestions,
  useGenerateSuggestedQuestions,
  useUpdateSuggestedQuestions,
} from "@/lib/queries/prompt";

interface SuggestedQuestionsProps {
  personaId: string;
}

/**
 * Suggested Questions component with CRUD operations
 * Allows viewing, editing, adding, deleting, and regenerating questions
 */
export function SuggestedQuestions({ personaId }: SuggestedQuestionsProps) {
  // Fetch suggested questions
  const { data: suggestedQuestionsData, refetch: refetchQuestions } =
    useGetSuggestedQuestions(personaId, { enabled: true });

  // Mutations
  const generateQuestionsMutation = useGenerateSuggestedQuestions();
  const updateQuestionsMutation = useUpdateSuggestedQuestions();

  // Editing state
  const [isEditingQuestions, setIsEditingQuestions] = useState(false);
  const [editingQuestions, setEditingQuestions] = useState<string[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [newQuestionText, setNewQuestionText] = useState("");

  // Sync editing questions with fetched data
  useEffect(() => {
    if (suggestedQuestionsData?.suggested_questions) {
      setEditingQuestions(suggestedQuestionsData.suggested_questions);
    }
  }, [suggestedQuestionsData]);

  // ===== HANDLERS =====
  const handleRegenerateQuestions = async () => {
    try {
      await generateQuestionsMutation.mutateAsync({
        personaId,
        numQuestions: 5,
        forceRegenerate: true,
      });

      await refetchQuestions();

      toast.success("Suggested questions regenerated successfully!");
      setIsEditingQuestions(false);
    } catch (error) {
      console.error("Failed to regenerate questions:", error);
      toast.error("Failed to regenerate questions");
    }
  };

  const handleStartEditing = () => {
    setIsEditingQuestions(true);
  };

  const handleCancelEditing = () => {
    setIsEditingQuestions(false);
    setEditingIndex(null);
    setEditingText("");
    setNewQuestionText("");
    // Reset to original questions
    if (suggestedQuestionsData?.suggested_questions) {
      setEditingQuestions(suggestedQuestionsData.suggested_questions);
    }
  };

  const handleSaveQuestions = async () => {
    try {
      const result = await updateQuestionsMutation.mutateAsync({
        persona_id: personaId,
        questions: editingQuestions.filter((q) => q.trim() !== ""),
      });

      // Update local editing state with the response
      if (result.suggested_questions) {
        setEditingQuestions(result.suggested_questions);
      }

      setIsEditingQuestions(false);
      setEditingIndex(null);
      setEditingText("");
      toast.success("Suggested questions updated successfully!");
    } catch (error) {
      console.error("Failed to update questions:", error);
      toast.error("Failed to update questions");
    }
  };

  const handleAddQuestion = () => {
    if (newQuestionText.trim()) {
      setEditingQuestions([...editingQuestions, newQuestionText.trim()]);
      setNewQuestionText("");
    }
  };

  const handleStartEditingQuestion = (index: number) => {
    setEditingIndex(index);
    setEditingText(editingQuestions[index]);
  };

  const handleSaveEditingQuestion = () => {
    if (editingIndex !== null && editingText.trim()) {
      const updated = [...editingQuestions];
      updated[editingIndex] = editingText.trim();
      setEditingQuestions(updated);
      setEditingIndex(null);
      setEditingText("");
    }
  };

  const handleCancelEditingQuestion = () => {
    setEditingIndex(null);
    setEditingText("");
  };

  const handleDeleteQuestion = (index: number) => {
    setEditingQuestions(editingQuestions.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3 pt-2">
      {/* Header with actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex items-center gap-2">
          <HelpCircle className="size-4 sm:size-5 text-primary" />
          <Label className="text-sm font-medium m-0">Suggested Questions</Label>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {!isEditingQuestions ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleStartEditing}
                className="gap-1.5 sm:gap-2 h-7 sm:h-8 text-xs sm:text-sm"
              >
                <Edit2 className="size-3" />
                Edit
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRegenerateQuestions}
                disabled={generateQuestionsMutation.isPending}
                className="gap-1.5 sm:gap-2 h-7 sm:h-8 text-xs sm:text-sm"
              >
                {generateQuestionsMutation.isPending ? (
                  <>
                    <Loader2 className="size-3 animate-spin" />
                    <span className="hidden xs:inline">Generating...</span>
                    <span className="xs:hidden">...</span>
                  </>
                ) : (
                  <>
                    <RefreshCw className="size-3" />
                    Regenerate
                  </>
                )}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelEditing}
                disabled={updateQuestionsMutation.isPending}
                className="gap-1.5 sm:gap-2 h-7 sm:h-8 text-xs sm:text-sm"
              >
                <X className="size-3" />
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleSaveQuestions}
                disabled={updateQuestionsMutation.isPending}
                className="gap-1.5 sm:gap-2 h-7 sm:h-8 text-xs sm:text-sm"
              >
                {updateQuestionsMutation.isPending ? (
                  <>
                    <Loader2 className="size-3 animate-spin" />
                    <span className="hidden xs:inline">Saving...</span>
                    <span className="xs:hidden">...</span>
                  </>
                ) : (
                  <>
                    <Check className="size-3" />
                    Save
                  </>
                )}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Questions display/edit */}
      {!isEditingQuestions ? (
        // Read-only view
        suggestedQuestionsData?.suggested_questions &&
        suggestedQuestionsData.suggested_questions.length > 0 ? (
          <div className="grid gap-2">
            {suggestedQuestionsData.suggested_questions.map(
              (question: string, index: number) => (
                <div
                  key={index}
                  className="flex items-start gap-3 p-3 rounded-lg border bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  <Badge
                    variant="secondary"
                    className="shrink-0 size-6 rounded-full flex items-center justify-center p-0 bg-primary/10 text-primary border-primary/20"
                  >
                    {index + 1}
                  </Badge>
                  <p className="text-sm text-foreground leading-relaxed flex-1">
                    {question}
                  </p>
                </div>
              ),
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center p-8 rounded-lg border border-dashed bg-muted/20">
            <HelpCircle className="size-8 text-muted-foreground/50 mb-3" />
            <p className="text-sm font-medium text-muted-foreground mb-1">
              No suggested questions yet
            </p>
            <p className="text-xs text-muted-foreground/80">
              Click &ldquo;Edit&rdquo; to add questions or
              &ldquo;Regenerate&rdquo; to generate AI-powered starter questions
            </p>
          </div>
        )
      ) : (
        // Editing view
        <div className="space-y-3">
          {editingQuestions.length > 0 ? (
            <div className="grid gap-2">
              {editingQuestions.map((question, index) => (
                <div
                  key={index}
                  className="flex items-start gap-2 p-2 rounded-lg border bg-muted/30"
                >
                  <Badge
                    variant="secondary"
                    className="shrink-0 size-6 rounded-full flex items-center justify-center p-0 bg-primary/10 text-primary border-primary/20 mt-1"
                  >
                    {index + 1}
                  </Badge>
                  {editingIndex === index ? (
                    <>
                      <Input
                        value={editingText}
                        onChange={(e) => setEditingText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            handleSaveEditingQuestion();
                          } else if (e.key === "Escape") {
                            handleCancelEditingQuestion();
                          }
                        }}
                        className="flex-1 h-8 text-sm"
                        autoFocus
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleSaveEditingQuestion}
                        className="h-8 w-8 p-0"
                      >
                        <Check className="size-4 text-green-600" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleCancelEditingQuestion}
                        className="h-8 w-8 p-0"
                      >
                        <X className="size-4 text-muted-foreground" />
                      </Button>
                    </>
                  ) : (
                    <>
                      <p className="text-sm text-foreground leading-relaxed flex-1 py-1">
                        {question}
                      </p>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleStartEditingQuestion(index)}
                        className="h-8 w-8 p-0"
                      >
                        <Edit2 className="size-3 text-muted-foreground" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteQuestion(index)}
                        className="h-8 w-8 p-0 hover:text-destructive"
                      >
                        <Trash2 className="size-3" />
                      </Button>
                    </>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-6 rounded-lg border border-dashed bg-muted/20">
              <HelpCircle className="size-6 text-muted-foreground/50 mb-2" />
              <p className="text-xs text-muted-foreground">
                No questions yet. Add one below.
              </p>
            </div>
          )}

          {/* Add new question */}
          <div className="flex items-center gap-2 p-2 rounded-lg border bg-background">
            <Plus className="size-4 text-primary shrink-0" />
            <Input
              value={newQuestionText}
              onChange={(e) => setNewQuestionText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleAddQuestion();
                }
              }}
              placeholder="Add a new question..."
              className="flex-1 h-8 text-sm border-0 shadow-none focus-visible:ring-0 px-2"
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={handleAddQuestion}
              disabled={!newQuestionText.trim()}
              className="h-8 px-3"
            >
              Add
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
