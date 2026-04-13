/**
 * Centralized Tour localStorage Keys
 *
 * This file contains all localStorage keys used for tracking tour completion across the app.
 * Centralizing these keys prevents duplication and makes it easier to manage tour state.
 */

export const TOUR_KEYS = {
  // Dashboard tours
  DASHBOARD_GUIDANCE: "hasSeenDashboardGuidance",

  // Onboarding tours
  KNOWLEDGE_TOUR: "hasSeenKnowledgeTour",
  VOICE_CLONE_TOUR: "hasSeenVoiceCloneTour",
  PERSONAS_TOUR: "hasSeenPersonasTour",

  // Feature tours
  SUMMARY_FEATURE_TOUR: "hasSeenSummaryFeatureTour",

  // Setup guide
  SETUP_GUIDE_DISMISSED: "hasSetupGuideDismissed",
} as const;

/**
 * Tour configuration type for useTour hook
 */
export interface TourConfig {
  /** Unique tour identifier (matches tour name in NextStepJS config) */
  tourName: string;

  /** localStorage key for tracking if user has seen this tour */
  storageKey: string;

  /** Condition function that determines if tour should start */
  shouldStart?: () => boolean;

  /** Additional data dependencies that should trigger re-evaluation */
  dependencies?: unknown[];
}
