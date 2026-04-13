/**
 * Assistant Widget Type Definitions
 * Types for the persona creation guide assistant (supports both voice and text)
 */

/** Props for the main widget container */
export interface AssistantWidgetProps {
  /** Optional className for positioning override */
  className?: string;
}

/** Props for the floating bubble button */
export interface AssistantBubbleProps {
  /** Handler for bubble click */
  onClick: () => void;
  /** Whether the panel is expanded */
  isExpanded: boolean;
}

/** Props for the assistant interface panel */
export interface AssistantPanelProps {
  /** Handler to close the panel */
  onClose: () => void;
}

/** Guide persona configuration */
export const GUIDE_PERSONA = {
  /** System username that owns the guide persona */
  username: "myclone",
  /** Persona name for the guide */
  personaName: "myclone-support",
  /** Display name shown in the UI */
  displayName: "MyClone Support",
  /** Description shown to users */
  description: "Your AI assistant for MyClone",
} as const;

/** Special widget token for the MyClone Guide widget */
export const GUIDE_WIDGET_TOKEN = "myclone-guide-widget" as const;
