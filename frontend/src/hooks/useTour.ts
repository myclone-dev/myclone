import { useEffect, useRef, useState } from "react";
import { useNextStep } from "nextstepjs";
import {
  shouldShowOnboarding,
  startOnboarding,
} from "@/lib/utils/onboardingProgress";
import type { TourConfig } from "@/config/tour-keys";

/**
 * Manages tour lifecycle: cleanup on unmount, onboarding initialization, and optional tour auto-start
 *
 * **Problem:** NextStepJS tours don't automatically cleanup when users navigate between pages.
 * If a user starts a tour on page A and navigates to page B, the old tour remains active,
 * causing DOM manipulation conflicts, undefined step errors, and stuck overlays.
 *
 * **Solution:** This hook ensures tours are properly closed when the component unmounts,
 * preventing tours from persisting across navigation. Also initializes onboarding for
 * first-time users automatically.
 *
 * **New:** Optionally accepts tour configuration to automatically handle tour initialization
 * with localStorage checks, reducing code duplication across pages.
 *
 * **Implementation:** Uses a ref to store the latest closeNextStep function and only
 * registers the cleanup once on mount, preventing interference with tour initialization.
 *
 * @example
 * ```typescript
 * // Basic usage (cleanup only)
 * export default function MyPage() {
 *   useTour();
 *   // ... rest of component
 * }
 *
 * // With auto-start configuration
 * export default function MyPage() {
 *   const { data: user } = useUserMe();
 *
 *   useTour({
 *     tourName: "onboarding-knowledge",
 *     storageKey: TOUR_KEYS.KNOWLEDGE_TOUR,
 *     shouldStart: () => isOnboardingInProgress(),
 *     dependencies: [user],
 *   });
 * }
 * ```
 *
 * @param config - Optional tour configuration for auto-start behavior
 * @see https://github.com/myclone/myclone/issues/tour-persistence
 */
export function useTour(config?: TourConfig) {
  const { closeNextStep, startNextStep, isNextStepVisible, currentTour } =
    useNextStep();
  const [hasTriggeredTour, setHasTriggeredTour] = useState(false);

  // Store the latest closeNextStep in a ref to avoid effect re-runs
  const closeNextStepRef = useRef(closeNextStep);

  // Update ref when closeNextStep changes (React 19 requires this in useEffect)
  useEffect(() => {
    closeNextStepRef.current = closeNextStep;
  }, [closeNextStep]);

  // Initialize onboarding for first-time users (runs once on mount)
  useEffect(() => {
    if (typeof window === "undefined") return;

    const shouldShow = shouldShowOnboarding();

    if (shouldShow) {
      startOnboarding();
    }
  }, []); // Empty deps - only check once per mount

  // Register cleanup once on mount (empty deps array)
  // Uses ref to always call the latest version of closeNextStep
  useEffect(() => {
    // Close tour on unmount to prevent persistence across navigation
    return () => {
      closeNextStepRef.current();
    };
  }, []); // Empty deps intentional - we want cleanup to register only once

  // Optional: Auto-start tour based on configuration
  useEffect(() => {
    if (!config || hasTriggeredTour || typeof window === "undefined") return;

    // Check if user has already seen this tour
    const hasSeenTour = localStorage.getItem(config.storageKey);
    if (hasSeenTour === "true") {
      setHasTriggeredTour(true);
      return;
    }

    // Check if tour should start based on custom condition
    const shouldStartTour = config.shouldStart ? config.shouldStart() : true;

    // Only start tour if:
    // 1. Custom condition passes (or no condition provided)
    // 2. No other tour is currently visible
    // 3. NextStepJS is initialized (startNextStep is a function)
    if (
      shouldStartTour &&
      !isNextStepVisible &&
      typeof startNextStep === "function"
    ) {
      setHasTriggeredTour(true);

      // Use RAF to ensure DOM is ready and NextStepJS is initialized
      requestAnimationFrame(() => {
        startNextStep(config.tourName);
        localStorage.setItem(config.storageKey, "true");
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    config?.tourName,
    config?.storageKey,
    hasTriggeredTour,
    startNextStep,
    isNextStepVisible,
    currentTour, // Re-evaluate when another tour starts/stops
    ...(config?.dependencies || []), // Spread additional dependencies
  ]);
}
