/**
 * Onboarding Progress Tracker
 * Manages localStorage flags for the step-by-step first-time user onboarding flow
 *
 * Flow: Check existing state → Guide to Knowledge Library → Guide to Voice Clone → Guide to Create Persona
 */

const STORAGE_KEYS = {
  ONBOARDING_STARTED: "hasStartedOnboarding",
  ONBOARDING_COMPLETED: "hasCompletedOnboarding",
  ONBOARDING_SKIPPED: "hasSkippedOnboarding",
  KNOWLEDGE_STEP_COMPLETED: "onboardingKnowledgeStepCompleted",
  VOICE_CLONE_STEP_COMPLETED: "onboardingVoiceCloneStepCompleted",
  PERSONA_STEP_COMPLETED: "onboardingPersonaStepCompleted",
  PERSONA_CREATION_TOUR_SKIPPED: "hasSkippedPersonaCreationTour",
} as const;

/**
 * Check if user should see onboarding flow
 * Returns true for first-time users who haven't started, completed, or skipped
 */
export function shouldShowOnboarding(): boolean {
  if (typeof window === "undefined") return false;

  const started = localStorage.getItem(STORAGE_KEYS.ONBOARDING_STARTED);
  const completed = localStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETED);
  const skipped = localStorage.getItem(STORAGE_KEYS.ONBOARDING_SKIPPED);

  // Show onboarding if none of these flags are set
  return started !== "true" && completed !== "true" && skipped !== "true";
}

/**
 * Check if onboarding is in progress
 */
export function isOnboardingInProgress(): boolean {
  if (typeof window === "undefined") return false;

  const started = localStorage.getItem(STORAGE_KEYS.ONBOARDING_STARTED);
  const completed = localStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETED);
  const skipped = localStorage.getItem(STORAGE_KEYS.ONBOARDING_SKIPPED);

  return started === "true" && completed !== "true" && skipped !== "true";
}

/**
 * Start onboarding flow
 */
export function startOnboarding(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.ONBOARDING_STARTED, "true");
}

/**
 * Mark entire onboarding as completed
 */
export function completeOnboarding(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.ONBOARDING_COMPLETED, "true");
}

/**
 * Skip onboarding (user dismisses it)
 */
export function skipOnboarding(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.ONBOARDING_SKIPPED, "true");
}

/**
 * Check if knowledge library step is completed
 */
export function hasCompletedKnowledgeStep(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(STORAGE_KEYS.KNOWLEDGE_STEP_COMPLETED) === "true";
}

/**
 * Mark knowledge library step as completed
 */
export function markKnowledgeStepComplete(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.KNOWLEDGE_STEP_COMPLETED, "true");
}

/**
 * Check if voice clone step is completed
 */
export function hasCompletedVoiceCloneStep(): boolean {
  if (typeof window === "undefined") return false;
  return (
    localStorage.getItem(STORAGE_KEYS.VOICE_CLONE_STEP_COMPLETED) === "true"
  );
}

/**
 * Mark voice clone step as completed
 */
export function markVoiceCloneStepComplete(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.VOICE_CLONE_STEP_COMPLETED, "true");
}

/**
 * Check if persona creation step is completed
 */
export function hasCompletedPersonaStep(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(STORAGE_KEYS.PERSONA_STEP_COMPLETED) === "true";
}

/**
 * Mark persona creation step as completed
 */
export function markPersonaStepComplete(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.PERSONA_STEP_COMPLETED, "true");
}

/**
 * Check if persona creation tour was skipped
 */
export function hasSkippedPersonaCreationTour(): boolean {
  if (typeof window === "undefined") return false;
  return (
    localStorage.getItem(STORAGE_KEYS.PERSONA_CREATION_TOUR_SKIPPED) === "true"
  );
}

/**
 * Mark persona creation tour as skipped
 */
export function skipPersonaCreationTour(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.PERSONA_CREATION_TOUR_SKIPPED, "true");
}

/**
 * Get current onboarding step based on completion status
 * Returns: 'knowledge' | 'voice-clone' | 'persona' | 'completed'
 */
export function getCurrentOnboardingStep():
  | "knowledge"
  | "voice-clone"
  | "persona"
  | "completed" {
  if (typeof window === "undefined") return "knowledge";

  if (!hasCompletedKnowledgeStep()) {
    return "knowledge";
  }

  if (!hasCompletedVoiceCloneStep()) {
    return "voice-clone";
  }

  if (!hasCompletedPersonaStep()) {
    return "persona";
  }

  return "completed";
}

/**
 * Reset all onboarding progress (for testing)
 */
export function resetOnboarding(): void {
  if (typeof window === "undefined") return;

  Object.values(STORAGE_KEYS).forEach((key) => {
    localStorage.removeItem(key);
  });
}

/**
 * Get onboarding progress percentage
 */
export function getOnboardingProgress(): number {
  if (typeof window === "undefined") return 0;

  let completed = 0;
  const total = 3; // knowledge, voice clone, persona

  if (hasCompletedKnowledgeStep()) completed++;
  if (hasCompletedVoiceCloneStep()) completed++;
  if (hasCompletedPersonaStep()) completed++;

  return Math.round((completed / total) * 100);
}
