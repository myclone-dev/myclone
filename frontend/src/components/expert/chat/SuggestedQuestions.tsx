"use client";

import { Button } from "@/components/ui/button";
import { Sparkles, MessageCircle } from "lucide-react";
import { motion } from "framer-motion";

interface SuggestedQuestionsProps {
  questions: string[];
  onQuestionClick: (question: string) => void;
  disabled?: boolean;
}

export function SuggestedQuestions({
  questions,
  onQuestionClick,
  disabled = false,
}: SuggestedQuestionsProps) {
  if (!questions || questions.length === 0) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="w-full max-w-2xl mx-auto px-4"
    >
      <div className="flex items-center justify-center gap-1.5 mb-3">
        <Sparkles className="size-3 text-primary/70" />
        <span className="text-xs font-medium text-muted-foreground">
          Try asking
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {questions.map((question, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: idx * 0.05 }}
          >
            <Button
              variant="outline"
              className="h-auto w-full text-left justify-start whitespace-normal px-3 py-2.5 hover:bg-primary/5 hover:border-primary/30 transition-all group"
              onClick={() => onQuestionClick(question)}
              disabled={disabled}
            >
              <div className="flex items-start gap-2 w-full">
                <MessageCircle className="size-3.5 text-primary/60 shrink-0 mt-0.5" />
                <span className="text-xs leading-relaxed line-clamp-2 text-foreground/70 group-hover:text-foreground transition-colors">
                  {question}
                </span>
              </div>
            </Button>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
