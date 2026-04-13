"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Database,
  Mic,
  CheckCircle2,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

interface SetupGuideProps {
  hasKnowledgeLibrary: boolean;
  hasVoiceClone: boolean;
  onDismiss?: () => void;
}

export function SetupGuide({
  hasKnowledgeLibrary,
  hasVoiceClone,
  onDismiss,
}: SetupGuideProps) {
  // If both are complete, don't show the guide
  if (hasKnowledgeLibrary && hasVoiceClone) {
    return null;
  }

  const steps = [
    {
      id: "knowledge",
      title: "Add Knowledge Library",
      description:
        "Add your LinkedIn, Twitter, website, or documents to give your persona context and knowledge",
      icon: Database,
      href: "/dashboard/knowledge",
      completed: hasKnowledgeLibrary,
      priority: 1,
    },
    {
      id: "voice",
      title: "Clone Your Voice (Optional)",
      description:
        "Create a voice clone to make your persona sound like you in voice conversations",
      icon: Mic,
      href: "/dashboard/voice-clone",
      completed: hasVoiceClone,
      priority: 2,
    },
  ];

  const incompleteSteps = steps.filter((step) => !step.completed);

  return (
    <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50">
      <CardHeader className="p-4 sm:p-6">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1 min-w-0 flex-1">
            <div className="flex items-start gap-2">
              <Sparkles className="size-4 shrink-0 text-blue-600 sm:size-5" />
              <CardTitle className="text-base leading-tight sm:text-lg">
                Complete Your Setup to Activate Your Persona
              </CardTitle>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Your default persona is created, but needs knowledge sources to
              function properly
            </p>
          </div>
          {onDismiss && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDismiss}
              className="text-muted-foreground hover:text-foreground shrink-0 h-8 px-2 sm:h-9 sm:px-3"
            >
              <span className="text-xs sm:text-sm">Dismiss</span>
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3 p-4 sm:p-6">
        {incompleteSteps.map((step) => (
          <div
            key={step.id}
            className="group relative flex items-start gap-3 rounded-lg border bg-white p-3 transition-all hover:shadow-md hover:border-blue-300 sm:items-center sm:gap-4 sm:p-4"
          >
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
              <step.icon className="size-5" />
            </div>
            <div className="flex-1 space-y-1 min-w-0">
              <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                <h3 className="font-semibold text-xs sm:text-sm">
                  {step.title}
                </h3>
                {step.priority === 1 && (
                  <Badge
                    variant="outline"
                    className="bg-red-50 text-red-700 border-red-200 text-[10px] px-1.5 py-0 sm:text-xs sm:px-2"
                  >
                    Required
                  </Badge>
                )}
              </div>
              <p className="text-[10px] sm:text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                {step.description}
              </p>
            </div>
            <Button
              asChild
              size="sm"
              className="shrink-0 gap-1.5 opacity-80 group-hover:opacity-100 transition-opacity h-8 px-3 text-xs sm:h-9 sm:px-4 sm:gap-2 sm:text-sm"
            >
              <Link href={step.href}>
                <span className="hidden sm:inline">Setup</span>
                <span className="sm:hidden">Go</span>
                <ArrowRight className="size-3 sm:size-4" />
              </Link>
            </Button>
          </div>
        ))}

        {/* Progress indicator */}
        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center gap-1.5 text-xs sm:gap-2 sm:text-sm text-muted-foreground">
            <CheckCircle2 className="size-3.5 sm:size-4 text-green-600 shrink-0" />
            <span className="truncate">
              {steps.filter((s) => s.completed).length} of {steps.length}{" "}
              completed
            </span>
          </div>
          <div className="flex gap-1 shrink-0">
            {steps.map((step) => (
              <div
                key={step.id}
                className={`h-1.5 w-6 sm:w-8 rounded-full transition-all ${
                  step.completed ? "bg-green-600" : "bg-gray-200"
                }`}
              />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
