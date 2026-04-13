// Types for UnifiedWidgetCustomizer

export type Framework =
  | "html"
  | "nextjs"
  | "react"
  | "react-js"
  | "vue"
  | "astro"
  | "wordpress"
  | "wix"
  | "hostinger";

export type WidgetMode = "bubble" | "inline" | "fullpage";

export type CustomizeTab =
  | "essentials"
  | "theme"
  | "size"
  | "layout"
  | "branding";

export type ChatbotStyle = "guide" | "classic";

/**
 * Valid modal positions for the widget.
 * - "centered": Opens as a centered modal (default behavior)
 * - Corner positions: Opens as a chatbot docked to the specified corner
 */
export type ModalPosition =
  | "centered"
  | "bottom-right"
  | "bottom-left"
  | "top-right"
  | "top-left";

/**
 * Positions that enable "chatbot mode" - a docked chat interface instead of centered modal.
 * Used to determine when to show chatbot-specific options in the customizer.
 */
export const CHATBOT_MODE_POSITIONS: ModalPosition[] = [
  "bottom-right",
  "bottom-left",
  "top-right",
  "top-left",
];

/**
 * Check if a modal position enables chatbot mode.
 * Chatbot mode positions are corner positions (not centered).
 */
export function isChatbotModePosition(position: string | undefined): boolean {
  return (
    !!position && CHATBOT_MODE_POSITIONS.includes(position as ModalPosition)
  );
}

export interface WidgetConfig {
  // Essentials
  personaName: string;
  widgetToken: string;
  // Size & Dimensions
  width: string;
  height: string;
  bubbleSize: string;
  borderRadius: string;
  // Chatbot Mode Size (for bottom-right chatbot style only)
  chatbotWidth: string;
  chatbotHeight: string;
  // Theme & Colors
  primaryColor: string;
  backgroundColor: string;
  headerBackground: string;
  textColor: string;
  textSecondaryColor: string;
  bubbleBackgroundColor: string;
  bubbleTextColor: string;
  userMessageBg: string;
  botMessageBg: string;
  userMessageTextColor: string;
  botMessageTextColor: string;
  // Layout & Positioning
  position: string;
  offsetX: string;
  offsetY: string;
  modalPosition: string;
  /**
   * Style for chatbot mode (positioned modal)
   * - "guide": Centered avatar, mode toggle in header, inline transcript (like dashboard assistant)
   * - "classic": Header with avatar/name, full chat interface (original style)
   */
  chatbotStyle: ChatbotStyle;
  // Branding
  showBranding: boolean;
  headerTitle: string;
  headerSubtitle: string;
  avatarUrl: string;
  showAvatar: boolean;
  // Behavior
  enableVoice: boolean;
  bubbleText: string;
  welcomeMessage: string;
  /**
   * Custom bubble icon URL (overrides avatarUrl for bubble only)
   * If set, this image will be used for the bubble button instead of avatarUrl
   */
  bubbleIcon: string;
  /**
   * Disable bubble animations (pulsating waves, floating, tooltips)
   * When true, shows a simple static bubble button
   */
  simpleBubble: boolean;
}

// Default configuration values - matching agent page colors
export const DEFAULT_CONFIG: WidgetConfig = {
  // Essentials
  personaName: "",
  widgetToken: "",
  // Size & Dimensions
  width: "900px",
  height: "820px",
  bubbleSize: "60px",
  borderRadius: "16px",
  // Chatbot Mode Size (for bottom-right chatbot style only)
  // Matches the dashboard AssistantWidget size (420px × 700px)
  chatbotWidth: "420px",
  chatbotHeight: "700px",
  // Theme & Colors - matching agent page
  primaryColor: "#f59e0b",
  backgroundColor: "#fff4eb",
  headerBackground: "rgba(255, 255, 255, 0.8)",
  textColor: "#4c6eb8",
  textSecondaryColor: "#374151",
  bubbleBackgroundColor: "#f59e0b",
  bubbleTextColor: "#ffffff",
  userMessageBg: "#3b82f6",
  botMessageBg: "#ffffff",
  userMessageTextColor: "#ffffff",
  botMessageTextColor: "#1f2937",
  // Layout & Positioning
  position: "bottom-right",
  offsetX: "20px",
  offsetY: "20px",
  modalPosition: "bottom-right",
  chatbotStyle: "guide",
  // Branding
  showBranding: true,
  headerTitle: "",
  headerSubtitle: "",
  avatarUrl: "",
  showAvatar: true,
  // Behavior
  enableVoice: true,
  bubbleText: "Chat with me",
  welcomeMessage: "Hello! How can I help you?",
  bubbleIcon: "",
  simpleBubble: false,
};

export interface EffectiveColors {
  primary: string;
  background: string;
  headerBg: string;
  text: string;
  textSecondary: string;
  bubbleBg: string;
  bubbleText: string;
  userMsgBg: string;
  botMsgBg: string;
  userMsgText: string;
  botMsgText: string;
}

export interface UnifiedWidgetCustomizerProps {
  username: string;
  widgetToken?: string;
}
