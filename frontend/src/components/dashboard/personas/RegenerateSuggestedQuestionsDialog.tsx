"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Sparkles, Loader2, Check } from "lucide-react";
import { useGenerateSuggestedQuestions } from "@/lib/queries/prompt";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";

interface RegenerateSuggestedQuestionsDialogProps {
  personaId: string;
  personaName: string;
  currentQuestions?: string[];
  trigger?: React.ReactNode;
}

export function RegenerateSuggestedQuestionsDialog({
  personaId,
  personaName,
  currentQuestions,
  trigger,
}: RegenerateSuggestedQuestionsDialogProps) {
  const [open, setOpen] = useState(false);
  const [generatedQuestions, setGeneratedQuestions] = useState<string[] | null>(
    null,
  );
  const generateMutation = useGenerateSuggestedQuestions();

  const handleGenerate = () => {
    generateMutation.mutate(
      {
        personaId,
        numQuestions: 5,
        forceRegenerate: true,
      },
      {
        onSuccess: (data) => {
          setGeneratedQuestions(data.suggested_questions);
          toast.success("Suggested questions regenerated successfully!", {
            description: `Generated ${data.suggested_questions.length} new questions.`,
          });
        },
        onError: (error: Error) => {
          toast.error("Failed to regenerate questions", {
            description: error.message,
          });
        },
      },
    );
  };

  const handleClose = () => {
    setOpen(false);
    setGeneratedQuestions(null);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className="gap-2">
            <Sparkles className="size-4" />
            Suggested Questions
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-5 text-ai-brown" />
            Suggested Questions for {personaName}
          </DialogTitle>
          <DialogDescription>
            AI-generated starter questions to help users engage with your
            persona.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Current Questions */}
          {!generatedQuestions &&
            currentQuestions &&
            currentQuestions.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm font-medium">
                  Current Questions
                  <Badge variant="secondary" className="ml-2">
                    {currentQuestions.length}
                  </Badge>
                </Label>
                <div className="space-y-2 max-h-[200px] overflow-y-auto">
                  {currentQuestions.map((question, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2 text-sm p-2 rounded-lg bg-muted/50"
                    >
                      <Check className="size-4 text-green-600 mt-0.5 shrink-0" />
                      <span>{question}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

          {/* Generated Questions */}
          {generatedQuestions && (
            <div className="space-y-2">
              <Label className="text-sm font-medium text-green-600">
                New Questions Generated
                <Badge variant="secondary" className="ml-2 bg-green-100">
                  {generatedQuestions.length}
                </Badge>
              </Label>
              <div className="space-y-2 max-h-[200px] overflow-y-auto">
                {generatedQuestions.map((question, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 text-sm p-2 rounded-lg bg-green-50 border border-green-200"
                  >
                    <Sparkles className="size-4 text-green-600 mt-0.5 shrink-0" />
                    <span>{question}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty State */}
          {!generatedQuestions &&
            (!currentQuestions || currentQuestions.length === 0) && (
              <div className="rounded-lg border border-dashed p-6 text-center">
                <Sparkles className="mx-auto mb-2 size-8 text-muted-foreground" />
                <p className="text-sm font-medium text-muted-foreground mb-1">
                  No questions generated yet
                </p>
                <p className="text-xs text-muted-foreground">
                  Click &quot;Generate Questions&quot; to create AI-powered
                  starter questions
                </p>
              </div>
            )}

          <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
            <p className="font-medium mb-1">How it works:</p>
            <p>
              Questions are generated based on your persona&apos;s introduction,
              expertise, chat objective, and other configuration. They appear on
              the chat interface to help users start meaningful conversations.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Close
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={generateMutation.isPending}
            className="gap-2"
          >
            {generateMutation.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="size-4" />
                {generatedQuestions ? "Regenerate" : "Generate Questions"}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
