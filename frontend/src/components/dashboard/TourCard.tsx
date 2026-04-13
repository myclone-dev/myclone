"use client";

import React, { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import {
  isOnboardingInProgress,
  markKnowledgeStepComplete,
  markVoiceCloneStepComplete,
  markPersonaStepComplete,
  completeOnboarding,
  skipPersonaCreationTour,
} from "@/lib/utils/onboardingProgress";
import {
  hasCompletedKnowledgeLibrary,
  hasCompletedVoiceClone,
  getCurrentUsername,
} from "@/lib/utils/setupProgress";
import { useRouter } from "next/navigation";
import type { CardComponentProps } from "nextstepjs";

/**
 * Custom Tour Card Component
 * Matches ConvoxAI brand colors - uses Tailwind CSS
 * Responsive for mobile, tablet, and desktop
 * Saves completion status to localStorage
 */

export const TourCard: React.FC<CardComponentProps> = ({
  step,
  currentStep,
  totalSteps,
  nextStep,
  prevStep,
  skipTour,
  arrow,
}) => {
  const router = useRouter();

  // Responsive sizing hook - must be called before any conditional returns
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkSize = () => {
      setIsMobile(window.innerWidth < 640); // sm breakpoint
    };

    checkSize();
    window.addEventListener("resize", checkSize);
    return () => window.removeEventListener("resize", checkSize);
  }, []);

  // Defensive check: TypeScript types say step is required, but we check anyway
  // to handle edge cases (NextStepJS bugs, tour persistence race conditions, etc.)
  useEffect(() => {
    if (!step) {
      let mounted = true;

      // Track to Sentry with context
      if (typeof window !== "undefined") {
        import("@sentry/nextjs")
          .then((Sentry) => {
            // Only capture if component is still mounted
            if (mounted) {
              Sentry.captureMessage("Tour step is undefined", {
                level: "error",
                tags: {
                  component: "TourCard",
                  tour_error: "step_undefined",
                },
                contexts: {
                  tour: {
                    currentStep,
                    totalSteps,
                    pathname: window.location.pathname,
                    viewport: `${window.innerWidth}x${window.innerHeight}`,
                  },
                },
              });
            }
          })
          .catch(() => {
            // Silently fail if sentry import fails
          });
      }

      // Cleanup: prevent memory leak if component unmounts during import
      return () => {
        mounted = false;
      };

      // Note: We don't auto-skip broken tours to avoid DOM manipulation race conditions
      // with React's cleanup. Just render null and let NextStepJS handle state.
    }
  }, [step, currentStep, totalSteps]);

  // Early return after all hooks have been called
  // TypeScript doesn't know we checked above, so we assert it's defined
  if (!step) {
    return null;
  }

  // Check if this is first or last step (welcome/completion cards)
  const isWelcomeOrCompletion =
    currentStep === 0 || currentStep === totalSteps - 1;

  // Handle Next button click with event propagation prevention
  const handleNext = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    nextStep?.();
  };

  // Handle Previous button click with event propagation prevention
  const handlePrevious = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    prevStep?.();
  };

  /**
   * Determine next navigation destination based on setup progress
   * Flow: Knowledge Library → Voice Clone → Public Agent Page (/{username})
   */
  const getNextDestination = (): string => {
    const hasKnowledge = hasCompletedKnowledgeLibrary();
    const hasVoice = hasCompletedVoiceClone();
    const username = getCurrentUsername();

    // If both knowledge and voice exist, go to public agent page
    if (hasKnowledge && hasVoice && username) {
      return `/${username}`;
    }

    // If knowledge exists but no voice, go to voice clone
    if (hasKnowledge && !hasVoice) {
      return "/dashboard/voice-clone";
    }

    // Default: go to knowledge library
    return "/dashboard/knowledge";
  };

  // Handle tour completion with onboarding progression
  const handleFinish = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // Handle onboarding progression if user is in onboarding flow
    if (isOnboardingInProgress()) {
      const currentPath = window.location.pathname;

      // Mark steps complete based on current page
      if (currentPath.includes("/knowledge")) {
        markKnowledgeStepComplete();
      } else if (currentPath.includes("/voice-clone")) {
        markVoiceCloneStepComplete();
      }

      // Get next destination based on setup progress
      const nextDestination = getNextDestination();

      // If going to public page, complete onboarding
      const username = getCurrentUsername();
      if (username && nextDestination === `/${username}`) {
        completeOnboarding();
      }

      setTimeout(() => {
        router.push(nextDestination);
      }, 500);
    }

    skipTour?.();
  };

  const handleSkip = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // Skip persona creation dialog tours whenever Skip Tour is clicked
    // This covers both the personas page tour and the create persona dialog tour
    skipPersonaCreationTour();

    // Mark current onboarding step as complete to allow progression to next page
    const currentPath = window.location.pathname;
    if (currentPath.includes("/knowledge")) {
      markKnowledgeStepComplete();
    } else if (currentPath.includes("/voice-clone")) {
      markVoiceCloneStepComplete();
    } else if (currentPath.includes("/personas")) {
      markPersonaStepComplete();
    }

    skipTour?.();
  };

  return (
    <div
      data-nextstepjs-tour-card="true"
      onClick={(e) => {
        e.stopPropagation();
      }}
      onMouseDown={(e) => {
        e.stopPropagation();
      }}
      className={cn(
        "rounded-[0.625rem] border-2 border-primary bg-card shadow-lg",
        // Responsive width
        isMobile && "w-[calc(100vw-2rem)]",
        !isMobile && isWelcomeOrCompletion && "min-w-[24rem] max-w-[42rem]",
        !isMobile && !isWelcomeOrCompletion && "min-w-[22rem] max-w-[38rem]",
        // Responsive padding
        isMobile && isWelcomeOrCompletion && "p-6",
        isMobile && !isWelcomeOrCompletion && "p-4",
        !isMobile && isWelcomeOrCompletion && "p-8",
        !isMobile && !isWelcomeOrCompletion && "p-5",
      )}
    >
      {/* Header: Title and Icon */}
      <div
        className={cn(
          "flex items-center justify-between",
          isWelcomeOrCompletion ? "mb-6" : "mb-4",
        )}
      >
        <h2
          className={cn(
            "font-semibold text-foreground",
            isMobile && isWelcomeOrCompletion && "text-xl",
            isMobile && !isWelcomeOrCompletion && "text-base",
            !isMobile && isWelcomeOrCompletion && "text-2xl",
            !isMobile && !isWelcomeOrCompletion && "text-lg",
          )}
        >
          {step.title}
        </h2>
        {step.icon && (
          <span
            className={cn(
              isMobile && isWelcomeOrCompletion && "text-[1.75rem]",
              isMobile && !isWelcomeOrCompletion && "text-xl",
              !isMobile && isWelcomeOrCompletion && "text-[2rem]",
              !isMobile && !isWelcomeOrCompletion && "text-2xl",
            )}
          >
            {step.icon}
          </span>
        )}
      </div>

      {/* Content */}
      <div
        className={cn(
          "leading-relaxed text-muted-foreground",
          isWelcomeOrCompletion ? "mb-6" : "mb-4",
          isMobile && "text-sm",
          !isMobile && isWelcomeOrCompletion && "text-base",
          !isMobile && !isWelcomeOrCompletion && "text-sm",
        )}
      >
        {step.content}
      </div>

      {/* Progress bar */}
      <div className="mb-4 h-2 overflow-hidden rounded-full bg-secondary">
        <div
          className="h-2 rounded-full bg-primary transition-all duration-300"
          style={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }}
        />
      </div>

      {/* Control buttons */}
      <div className="flex items-center justify-between gap-3 text-sm">
        {/* Previous button */}
        <button
          onClick={handlePrevious}
          disabled={currentStep === 0}
          className={cn(
            "rounded-md border border-border bg-secondary font-medium text-foreground transition-all",
            "hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50",
            step.showControls ? "block" : "hidden",
            isMobile && "px-3 py-2 text-[0.8125rem]",
            !isMobile &&
              isWelcomeOrCompletion &&
              "px-5 py-2.5 text-[0.9375rem]",
            !isMobile && !isWelcomeOrCompletion && "px-4 py-2 text-sm",
          )}
        >
          Previous
        </button>

        {/* Step counter */}
        <span className="whitespace-nowrap text-xs font-medium text-muted-foreground">
          {currentStep + 1} of {totalSteps}
        </span>

        {/* Next/Finish button */}
        {currentStep === totalSteps - 1 ? (
          <button
            onClick={handleFinish}
            className={cn(
              "rounded-md border-none bg-primary font-semibold text-primary-foreground transition-all",
              "hover:bg-primary/90 hover:-translate-y-px",
              step.showControls ? "block" : "hidden",
              isMobile && "px-3.5 py-2 text-[0.8125rem]",
              !isMobile &&
                isWelcomeOrCompletion &&
                "px-6 py-2.5 text-[0.9375rem]",
              !isMobile && !isWelcomeOrCompletion && "px-5 py-2 text-sm",
            )}
          >
            Finish
          </button>
        ) : (
          <button
            onClick={handleNext}
            className={cn(
              "rounded-md border-none bg-primary font-semibold text-primary-foreground transition-all",
              "hover:bg-primary/90 hover:-translate-y-px",
              step.showControls ? "block" : "hidden",
              isMobile && "px-3.5 py-2 text-[0.8125rem]",
              !isMobile &&
                isWelcomeOrCompletion &&
                "px-6 py-2.5 text-[0.9375rem]",
              !isMobile && !isWelcomeOrCompletion && "px-5 py-2 text-sm",
            )}
          >
            Next
          </button>
        )}
      </div>

      {arrow}

      {/* Skip button */}
      {skipTour && currentStep < totalSteps - 1 && (
        <button
          onClick={handleSkip}
          className={cn(
            "mt-4 w-full rounded-md border border-border bg-transparent px-4 py-2 text-xs font-medium text-muted-foreground transition-all",
            "hover:bg-secondary",
            step.showSkip ? "block" : "hidden",
          )}
        >
          Skip Tour
        </button>
      )}
    </div>
  );
};
