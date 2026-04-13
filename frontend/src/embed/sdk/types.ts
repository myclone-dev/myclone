/**
 * ConvoxAI Embed SDK Types
 * Type definitions for the embed widget configuration and communication
 */

/**
 * Position of the widget on the page
 */
export type WidgetPosition =
  | "bottom-right"
  | "bottom-left"
  | "top-right"
  | "top-left";

/**
 * Widget display mode
 *
 * - "bubble": Floating button in corner that opens modal (default)
 * - "inline": Embedded directly in page content within a container
 * - "fullpage": Takes over the entire page (for white-label deployments)
 */
export type WidgetMode = "bubble" | "inline" | "fullpage";

/**
 * Size & Dimensions customization options
 */
export interface WidgetSizeConfig {
  /**
   * Width of the chat modal
   * @default "420px"
   * @example "500px", "90vw", "100%"
   */
  width?: string;

  /**
   * Height of the chat modal
   * @default "600px"
   * @example "700px", "85vh", "100%"
   */
  height?: string;

  /**
   * Size of the bubble button
   * @default "60px"
   * @example "50px", "70px"
   */
  bubbleSize?: string;

  /**
   * Border radius for the chat modal
   * @default "16px"
   * @example "8px", "24px", "0"
   */
  borderRadius?: string;

  /**
   * Width of the chatbot-style modal (when modalPosition is set to a corner)
   * @default "380px"
   * @example "400px", "450px"
   */
  chatbotWidth?: string;

  /**
   * Height of the chatbot-style modal (when modalPosition is set to a corner)
   * @default "550px"
   * @example "600px", "min(600px, calc(100vh - 120px))"
   */
  chatbotHeight?: string;
}

/**
 * Colors & Theming customization options
 */
export interface WidgetThemeConfig {
  /**
   * Primary accent color (hex format)
   * Used for buttons, highlights, and accents
   * @default "#6366f1"
   */
  primaryColor?: string;

  /**
   * Background color of the chat container
   * @default "#ffffff"
   */
  backgroundColor?: string;

  /**
   * Header background color or gradient
   * If not set, uses primaryColor
   * @example "#6366f1", "linear-gradient(135deg, #6366f1, #8b5cf6)"
   */
  headerBackground?: string;

  /**
   * Primary text color
   * @default "#1f2937"
   */
  textColor?: string;

  /**
   * Secondary/muted text color
   * @default "#6b7280"
   */
  textSecondaryColor?: string;

  /**
   * Bubble button background color
   * If not set, uses primaryColor
   */
  bubbleBackgroundColor?: string;

  /**
   * Bubble button text/icon color
   * @default "#ffffff"
   */
  bubbleTextColor?: string;

  /**
   * User message bubble background color
   * @default same as primaryColor
   */
  userMessageBg?: string;

  /**
   * Bot message bubble background color
   * @default "#f3f4f6"
   */
  botMessageBg?: string;

  /**
   * User message text color
   * @default "#ffffff"
   */
  userMessageTextColor?: string;

  /**
   * Bot message text color
   * @default "#1f2937"
   */
  botMessageTextColor?: string;
}

/**
 * Layout & Positioning customization options
 */
export interface WidgetLayoutConfig {
  /**
   * Position of the widget on the page
   * @default "bottom-right"
   */
  position?: WidgetPosition;

  /**
   * Horizontal offset from the edge
   * @default "20px"
   */
  offsetX?: string;

  /**
   * Vertical offset from the edge
   * @default "20px"
   */
  offsetY?: string;

  /**
   * Horizontal offset of the chat modal from the bubble
   * @default "0px"
   */
  modalOffsetX?: string;

  /**
   * Vertical offset (gap) between the bubble and chat modal
   * @default "10px"
   */
  modalOffsetY?: string;

  /**
   * Position of the chat modal when opened
   * If set, the modal will be positioned at the specified corner instead of centered
   * @default undefined (centered modal)
   * @example "bottom-right" - chatbot-style UI at bottom right corner
   * @example "bottom-left" - chatbot-style UI at bottom left corner
   */
  modalPosition?: WidgetPosition;
}

/**
 * Branding customization options
 */
export interface WidgetBrandingConfig {
  /**
   * Show "Powered by ConvoxAI" branding
   * @default true
   */
  showBranding?: boolean;

  /**
   * Show the entire header section (avatar, title, subtitle)
   * When false, hides the complete header area
   * @default true
   */
  showHeader?: boolean;

  /**
   * Custom header title (overrides persona name)
   */
  headerTitle?: string;

  /**
   * Custom header subtitle
   */
  headerSubtitle?: string;

  /**
   * Custom avatar URL (overrides persona avatar)
   */
  avatarUrl?: string;

  /**
   * Show avatar in header
   * @default true
   */
  showAvatar?: boolean;

  /**
   * Custom bubble icon URL (overrides avatarUrl for the bubble button only)
   */
  bubbleIcon?: string;

  /**
   * Disable bubble animations (pulsating waves, floating, tooltips)
   * When true, shows a simple static bubble button
   * @default false
   */
  simpleBubble?: boolean;
}

/**
 * Configuration options for the ConvoxAI widget
 */
export interface ConvoxAIConfig {
  /**
   * Your expert username from ConvoxAI dashboard
   */
  expertUsername: string;

  /**
   * Widget display mode
   * @default "bubble"
   *
   * - "bubble": Floating button in corner that opens modal (default)
   * - "inline": Embedded directly in page content within a container
   * - "fullpage": Takes over entire page (for white-label deployments)
   */
  mode?: WidgetMode;

  /**
   * Container selector for inline mode
   * Required when mode is "inline"
   *
   * @example "#chat-container"
   * @example ".widget-wrapper"
   */
  container?: string;

  /**
   * Height for inline mode (legacy - use size.height instead)
   * @default "600px"
   * @deprecated Use size.height instead
   */
  height?: string;

  /**
   * Persona name (optional)
   * If not provided, defaults to "default" persona
   */
  personaName?: string;

  /**
   * Widget authentication token from ConvoxAI dashboard
   * Required for API access
   */
  widgetToken: string;

  /**
   * Position of the widget on the page (legacy - use layout.position instead)
   * @default "bottom-right"
   * @deprecated Use layout.position instead
   */
  position?: WidgetPosition;

  /**
   * Primary color for the widget (legacy - use theme.primaryColor instead)
   * @default "#6366f1"
   * @deprecated Use theme.primaryColor instead
   */
  primaryColor?: string;

  /**
   * Text to display on the bubble button
   * @default "Chat with me"
   */
  bubbleText?: string;

  /**
   * Custom icon URL for the bubble button
   * If not provided, uses default avatar icon
   */
  bubbleIcon?: string;

  /**
   * Enable voice chat functionality
   * @default false
   */
  enableVoice?: boolean;

  /**
   * Welcome message to display when chat opens
   */
  welcomeMessage?: string;

  /**
   * Placeholder text for the message input
   * @default "Type your message..."
   */
  inputPlaceholder?: string;

  /**
   * Custom CSS to inject into the iframe
   */
  customCss?: string;

  /**
   * z-index for the widget container
   * @default 999999
   */
  zIndex?: number;

  /**
   * Initial user information (if known)
   */
  user?: {
    email?: string;
    name?: string;
    [key: string]: unknown;
  };

  // ============================================
  // NEW CUSTOMIZATION OPTIONS
  // ============================================

  /**
   * Size & Dimensions customization
   */
  size?: WidgetSizeConfig;

  /**
   * Colors & Theming customization
   */
  theme?: WidgetThemeConfig;

  /**
   * Layout & Positioning customization
   */
  layout?: WidgetLayoutConfig;

  /**
   * Branding customization
   */
  branding?: WidgetBrandingConfig;

  // ============================================
  // CALLBACKS
  // ============================================

  /**
   * Called when the widget is opened
   */
  onOpen?: () => void;

  /**
   * Called when the widget is closed
   */
  onClose?: () => void;

  /**
   * Called when user sends a message
   */
  onMessage?: (message: string) => void;

  /**
   * Called when user submits their email
   */
  onEmailSubmit?: (email: string) => void;

  /**
   * Called when an error occurs
   */
  onError?: (error: Error) => void;
}

/**
 * Methods exposed by the child iframe to the parent
 */
export interface ChildMethods {
  /**
   * Open the chat widget
   */
  open: () => void;

  /**
   * Close the chat widget
   */
  close: () => void;

  /**
   * Toggle the chat widget open/closed
   */
  toggle: () => void;

  /**
   * Set or update user information
   */
  setUser: (user: ConvoxAIConfig["user"]) => void;

  /**
   * Check if the widget is currently expanded
   */
  isExpanded: () => boolean;
}

/**
 * Methods exposed by the parent window to the child iframe
 */
export interface ParentMethods {
  /**
   * Notify parent that widget opened
   */
  notifyOpen: () => void;

  /**
   * Notify parent that widget closed
   */
  notifyClose: () => void;

  /**
   * Notify parent of a user message
   */
  notifyMessage: (message: string) => void;

  /**
   * Notify parent of email submission
   */
  notifyEmailSubmit: (email: string) => void;

  /**
   * Notify parent of an error
   */
  notifyError: (error: string) => void;

  /**
   * Notify parent of the persona avatar URL (so the loader bubble can update its icon)
   */
  notifyAvatarUrl: (url: string) => void;
}

/**
 * Public API for the ConvoxAI widget instance
 */
export interface ConvoxAIWidget {
  /**
   * Open the chat widget
   */
  open: () => Promise<void>;

  /**
   * Close the chat widget
   */
  close: () => Promise<void>;

  /**
   * Toggle the chat widget open/closed
   */
  toggle: () => Promise<void>;

  /**
   * Set or update user information
   */
  setUser: (user: ConvoxAIConfig["user"]) => Promise<void>;

  /**
   * Destroy the widget and clean up
   */
  destroy: () => void;

  /**
   * Check if the widget is currently expanded
   */
  isExpanded: () => Promise<boolean>;
}

/**
 * Global window interface extension
 */
declare global {
  interface Window {
    ConvoxAI?: {
      (config: ConvoxAIConfig): ConvoxAIWidget;
      instances: Map<string, ConvoxAIWidget>;
    };
  }
}
