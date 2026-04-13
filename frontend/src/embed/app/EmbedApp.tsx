/**
 * ConvoxAI Embed App
 * Main component that runs inside the iframe
 * Uses the same ExpertChatInterface as the main app
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ChildMessenger } from "../sdk/messaging";
import type { ParentMethods } from "../sdk/types";
import { EmbedBubble } from "./EmbedBubble";
import { EmbedFullpage } from "./EmbedFullpage";
import { GuideStyleModal } from "./GuideStyleModal";
import { ExpertChatInterface } from "../../components/expert/ExpertChatInterface";
import { Sparkles } from "lucide-react";
import { usePersona } from "../../lib/queries/persona";
import { I18nProvider } from "../../i18n/I18nProvider";

// Create QueryClient for the embed app
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

interface SizeConfig {
  width?: string;
  height?: string;
  bubbleSize?: string;
  borderRadius?: string;
  chatbotWidth?: string;
  chatbotHeight?: string;
}

interface ThemeConfig {
  primaryColor?: string;
  backgroundColor?: string;
  headerBackground?: string;
  textColor?: string;
  textSecondaryColor?: string;
  bubbleBackgroundColor?: string;
  bubbleTextColor?: string;
  userMessageBg?: string;
  botMessageBg?: string;
  userMessageTextColor?: string;
  botMessageTextColor?: string;
}

interface LayoutConfig {
  position?: string;
  offsetX?: string;
  offsetY?: string;
  modalOffsetX?: string;
  modalOffsetY?: string;
  modalPosition?: string;
  /**
   * Style for chatbot mode (bottom-right positioned modal)
   * - "guide": Uses Guide Widget style (centered avatar, mode toggle in header, inline transcript) - DEFAULT
   * - "classic": Uses original chatbot style (header with avatar/name, full chat interface)
   */
  chatbotStyle?: "guide" | "classic";
}

// Branding config
interface BrandingConfig {
  showBranding?: boolean;
  showHeader?: boolean;
  headerTitle?: string;
  headerSubtitle?: string;
  avatarUrl?: string;
  showAvatar?: boolean;
  simpleBubble?: boolean;
}

interface EmbedConfig {
  expertUsername: string;
  personaName?: string;
  widgetToken: string;
  mode: "bubble" | "inline" | "fullpage";
  position: string;
  primaryColor: string;
  bubbleText: string;
  bubbleIcon?: string;
  enableVoice: boolean;
  welcomeMessage?: string;
  inputPlaceholder: string;
  customCss?: string;
  apiUrl?: string;
  livekitUrl?: string;
  height: string;
  /** Language code for i18n (e.g., "en", "es", "fr", "ar") */
  lang?: string;
  user?: {
    email?: string;
    name?: string;
    [key: string]: unknown;
  };
  // New customization options
  size?: SizeConfig;
  theme?: ThemeConfig;
  layout?: LayoutConfig;
  branding?: BrandingConfig;
  /** When true, the SDK loader renders the bubble – the iframe should not render its own */
  loaderBubble?: boolean;
}

// Inner component that fetches persona and sets up i18n
const EmbedWithI18n: React.FC<{
  config: EmbedConfig;
  isExpanded: boolean;
  handleBubbleClick: () => void;
  parentMethods: ParentMethods | null;
}> = ({ config, isExpanded, handleBubbleClick, parentMethods }) => {
  // Fetch expert persona details first to get the language setting
  const { data: persona } = usePersona(
    config.expertUsername,
    config.personaName,
  );

  // Determine language: persona.language takes priority, fallback to config.lang
  const language = persona?.language || config.lang;

  // When persona loads, send avatar URL to the loader so the bubble can update its icon
  useEffect(() => {
    if (!parentMethods || !config.loaderBubble || !persona) return;

    const avatarUrl = persona.persona_avatar_url || persona.avatar || undefined;
    if (avatarUrl) {
      parentMethods.notifyAvatarUrl(avatarUrl);
    }
  }, [persona, parentMethods, config.loaderBubble]);

  return (
    <I18nProvider locale={language}>
      <EmbedContent
        config={config}
        isExpanded={isExpanded}
        handleBubbleClick={handleBubbleClick}
        persona={persona}
      />
    </I18nProvider>
  );
};

// Inner component that uses TanStack Query hooks
const EmbedContent: React.FC<{
  config: EmbedConfig;
  isExpanded: boolean;
  handleBubbleClick: () => void;
  persona: ReturnType<typeof usePersona>["data"];
}> = ({ config, isExpanded, handleBubbleClick, persona }) => {
  const { t } = useTranslation();

  // Debug: Log email capture and calendar settings
  if (process.env.NODE_ENV === "development" && persona) {
    console.log("[EmbedApp] Persona settings:", {
      email_capture_enabled: persona.email_capture_enabled,
      email_capture_message_threshold: persona.email_capture_message_threshold,
      email_capture_require_fullname: persona.email_capture_require_fullname,
      email_capture_require_phone: persona.email_capture_require_phone,
      calendar_enabled: persona.calendar_enabled,
      calendar_url: persona.calendar_url,
      calendar_display_name: persona.calendar_display_name,
    });
  }

  const isInlineMode = config.mode === "inline";
  const isFullpageMode = config.mode === "fullpage";
  const isAlwaysExpanded =
    isInlineMode || isFullpageMode || config.loaderBubble;

  // Extract customization values with defaults
  // Priority: URL params > persona.widget_config (server-stored) > defaults
  const size = config.size || {};
  const theme = config.theme || {};
  const layout = config.layout || {};

  // Merge branding: URL params override server-stored widget_config
  const serverWidgetConfig = persona?.widget_config || {};
  const branding = {
    ...serverWidgetConfig, // Server-stored settings (lower priority)
    ...config.branding, // URL params (higher priority)
  };

  // Size values
  const modalWidth = size.width || "420px";
  const modalHeight = size.height || "600px";
  const bubbleSize = size.bubbleSize || "80px";
  const borderRadius = size.borderRadius || "16px";

  // Layout values
  const modalPosition = layout.modalPosition;
  // Chatbot style: "guide" (default) uses GuideStyleModal, "classic" uses original style
  const chatbotStyle = layout.chatbotStyle || "guide";

  // Theme values - defaults match agent page (amber/peach theme)
  const primaryColor = theme.primaryColor || config.primaryColor || "#f59e0b";
  const backgroundColor = theme.backgroundColor || "#fff4eb";
  const headerBackground = theme.headerBackground || undefined;
  const textColor = theme.textColor || "#111827";
  const textSecondaryColor = theme.textSecondaryColor || "#374151";
  const bubbleBackgroundColor = theme.bubbleBackgroundColor || primaryColor;
  const bubbleTextColor = theme.bubbleTextColor || "#ffffff";
  const userMessageBg = theme.userMessageBg || "#3b82f6"; // blue-500 default
  const botMessageBg = theme.botMessageBg || "#ffffff";
  const userMessageTextColor = theme.userMessageTextColor || "#ffffff"; // white text on blue bg
  const botMessageTextColor = theme.botMessageTextColor || "#1f2937"; // gray-800 text on white bg

  // Branding values
  const showBranding = branding.showBranding !== false;
  const showHeader = branding.showHeader !== false;
  const headerTitle =
    branding.headerTitle ||
    persona?.name ||
    persona?.fullname ||
    `@${config.expertUsername || "expert"}`;
  const headerSubtitle = branding.headerSubtitle || undefined;
  const customAvatarUrl = branding.avatarUrl || undefined;
  const showAvatar = branding.showAvatar !== false;
  const simpleBubble = branding.simpleBubble === true;

  // Determine actual avatar to use (ensure we have a valid non-empty URL)
  // Priority: widget config override > persona-specific avatar > user profile avatar
  const avatarUrl =
    customAvatarUrl ||
    persona?.persona_avatar_url ||
    persona?.avatar ||
    undefined;

  // Check if we're in chatbot mode (positioned modal, not centered)
  // "centered" means use traditional overlay mode, any other position = chatbot mode
  const isChatbotMode = !!modalPosition && modalPosition !== "centered";

  // Chatbot mode dimensions - use configurable values with responsive fallback
  const configuredChatbotWidth = size.chatbotWidth || "420px";
  const configuredChatbotHeight = size.chatbotHeight || "700px";
  // Apply responsive constraint to height if it's a fixed pixel value
  const chatbotWidth = configuredChatbotWidth;
  const chatbotHeight = configuredChatbotHeight.endsWith("px")
    ? `min(${configuredChatbotHeight}, calc(100vh - 120px))`
    : configuredChatbotHeight;

  // Bubble dimensions for positioning calculations
  const bubbleSizeNum = parseInt(bubbleSize) || 60;
  const bubbleMargin = 16; // Gap between bubble and modal

  /**
   * Get chatbot modal styles - positions the modal using fixed positioning
   * for proper viewport containment
   */
  const getChatbotModalStyles = (): React.CSSProperties => {
    if (!isChatbotMode) return {};

    const offset = `${20 + bubbleSizeNum + bubbleMargin}px`;
    const isTop = modalPosition?.startsWith("top");
    const isLeft = modalPosition?.endsWith("left");

    return {
      position: "fixed" as const,
      [isTop ? "top" : "bottom"]: offset,
      [isLeft ? "left" : "right"]: "20px",
      zIndex: 999998,
    };
  };

  // Fullpage mode - render the dedicated fullpage layout
  if (isFullpageMode) {
    return (
      <EmbedFullpage
        expertUsername={config.expertUsername}
        personaName={config.personaName}
        widgetToken={config.widgetToken}
        persona={persona}
        primaryColor={primaryColor}
        enableVoice={config.enableVoice}
      />
    );
  }

  /**
   * Render the chat modal content (reusable for both chatbot and overlay modes)
   */
  const renderChatModal = (isChatbot: boolean) => {
    const modalStyles: React.CSSProperties = {
      background: backgroundColor,
      overflow: "hidden",
      borderRadius: borderRadius,
      boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
      // CSS Variables for message colors
      ["--embed-user-message-bg" as string]: userMessageBg,
      ["--embed-bot-message-bg" as string]: botMessageBg,
      ["--embed-user-message-text" as string]: userMessageTextColor,
      ["--embed-bot-message-text" as string]: botMessageTextColor,
      ["--embed-text-color" as string]: textColor,
      ["--embed-text-secondary" as string]: textSecondaryColor,
    };

    if (isChatbot) {
      // Chatbot mode: fixed size, positioned relative to container
      Object.assign(modalStyles, {
        ...getChatbotModalStyles(),
        width: chatbotWidth,
        height: chatbotHeight,
      });
    } else if (isInlineMode) {
      // Inline mode: fill container
      Object.assign(modalStyles, {
        position: "relative" as const,
        width: "100%",
        height: "100%",
        borderRadius: "0",
        boxShadow: "none",
      });
    } else {
      // Centered overlay mode - use CSS class for positioning to allow animation
      // The .centered-modal-enter animation handles the transform
      Object.assign(modalStyles, {
        position: "absolute" as const,
        left: "50%",
        top: "50%",
        // Don't set transform inline - let CSS animation handle it
        // Final position will be translate(-50%, -50%) from the animation's "to" state
        width: modalWidth,
        height: modalHeight,
        maxWidth: modalWidth,
        maxHeight: modalHeight,
      });
    }

    // Determine animation class
    const animationClass = isChatbot
      ? isExpanded
        ? "chatbot-modal-enter"
        : ""
      : isExpanded && !isInlineMode
        ? "centered-modal-enter"
        : "";

    return (
      <div
        className={`embed-chat-container ${isChatbot ? "chatbot-mode-container" : ""} ${animationClass}`}
        onClick={(e) => e.stopPropagation()}
        style={modalStyles}
      >
        {/* Decorative Background Elements */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            overflow: "hidden",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: "-10rem",
              right: "-10rem",
              width: "20rem",
              height: "20rem",
              background: "rgb(196 181 253)",
              borderRadius: "9999px",
              mixBlendMode: "multiply",
              filter: "blur(64px)",
              opacity: 0.3,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "-10rem",
              left: "-10rem",
              width: "20rem",
              height: "20rem",
              background: "rgb(167 139 250)",
              borderRadius: "9999px",
              mixBlendMode: "multiply",
              filter: "blur(64px)",
              opacity: 0.3,
            }}
          />
        </div>

        {/* Close Button - Only show in bubble mode (not in inline or fullpage) */}
        {!isAlwaysExpanded && (
          <button
            onClick={handleBubbleClick}
            style={{
              position: "absolute",
              top: "1rem",
              right: "1rem",
              zIndex: 10,
              background: "rgba(255, 255, 255, 0.9)",
              border: "1px solid rgba(0, 0, 0, 0.1)",
              borderRadius: "9999px",
              width: "2rem",
              height: "2rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              fontSize: "1.25rem",
              color: "#64748b",
              transition: "all 150ms",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(255, 255, 255, 1)";
              e.currentTarget.style.color = "#334155";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.9)";
              e.currentTarget.style.color = "#64748b";
            }}
            aria-label={t("widget.closeChat")}
          >
            ✕
          </button>
        )}

        {/* Content */}
        <div
          style={{
            position: "relative",
            zIndex: 1,
            height: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Header - Conditionally show based on branding.showHeader */}
          {showHeader && (
            <div
              className="embed-header"
              style={{
                textAlign: "center",
                padding: isChatbot
                  ? "1rem 1rem 0.5rem 1rem"
                  : "1.5rem 1rem 0.75rem 1rem",
                background: headerBackground || "rgba(255, 255, 255, 0.8)",
                backdropFilter: "blur(8px)",
                borderBottom: "1px solid rgba(0, 0, 0, 0.05)",
              }}
            >
              {/* Avatar with AI Badge - Conditionally show based on branding */}
              {showAvatar && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    marginBottom: isChatbot ? "0.5rem" : "1rem",
                  }}
                >
                  <div
                    style={{
                      position: "relative",
                      display: "inline-block",
                    }}
                  >
                    <div
                      className="embed-avatar"
                      style={{
                        width: isChatbot ? "4rem" : "5rem",
                        height: isChatbot ? "4rem" : "5rem",
                        borderRadius: "9999px",
                        overflow: "hidden",
                        border: "4px solid white",
                        boxShadow: "0 10px 25px rgba(0, 0, 0, 0.15)",
                        background: avatarUrl
                          ? "white"
                          : `linear-gradient(to bottom right, ${primaryColor}, ${primaryColor}cc)`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {avatarUrl ? (
                        <img
                          src={avatarUrl}
                          alt={headerTitle}
                          style={{
                            width: "100%",
                            height: "100%",
                            objectFit: "cover",
                          }}
                          onError={(e) => {
                            // Fallback if image fails to load
                            e.currentTarget.style.display = "none";
                            const parent = e.currentTarget.parentElement;
                            if (parent) {
                              parent.style.background = `linear-gradient(to bottom right, ${primaryColor}, ${primaryColor}cc)`;
                              const fallback = document.createElement("span");
                              fallback.textContent = headerTitle
                                .charAt(0)
                                .toUpperCase();
                              fallback.style.fontSize = isChatbot
                                ? "1.5rem"
                                : "1.75rem";
                              fallback.style.fontWeight = "600";
                              fallback.style.color = "white";
                              parent.appendChild(fallback);
                            }
                          }}
                        />
                      ) : (
                        <span
                          style={{
                            fontSize: isChatbot ? "1.5rem" : "1.75rem",
                            fontWeight: "600",
                            color: "white",
                          }}
                        >
                          {headerTitle.charAt(0).toUpperCase()}
                        </span>
                      )}
                    </div>
                    {/* AI Badge */}
                    <div
                      className="embed-ai-badge"
                      style={{
                        position: "absolute",
                        bottom: "-2px",
                        right: "-2px",
                        width: isChatbot ? "1.75rem" : "2rem",
                        height: isChatbot ? "1.75rem" : "2rem",
                        borderRadius: "9999px",
                        background: `linear-gradient(to bottom right, ${primaryColor}, ${primaryColor}cc)`,
                        border: "2px solid white",
                        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.15)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Sparkles
                        style={{
                          width: isChatbot ? "0.875rem" : "1.125rem",
                          height: isChatbot ? "0.875rem" : "1.125rem",
                          color: "white",
                          fill: "white",
                        }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Name / Header Title */}
              <h1
                className="embed-header-title"
                style={{
                  fontSize: isChatbot ? "1rem" : "1.125rem",
                  fontWeight: "700",
                  color: textColor,
                  marginBottom: "0.25rem",
                  padding: "0 0.5rem",
                }}
              >
                {headerTitle}
              </h1>

              {/* Custom Subtitle or Role/Company */}
              {(headerSubtitle ||
                (persona && (persona.role || persona.company))) && (
                <p
                  style={{
                    fontSize: isChatbot ? "0.75rem" : "0.875rem",
                    fontWeight: "500",
                    color: textSecondaryColor,
                    marginBottom: "0.25rem",
                    padding: "0 0.5rem",
                  }}
                >
                  {headerSubtitle ||
                    (persona?.role && persona?.company
                      ? `${persona.role} ${t("common.at")} ${persona.company}`
                      : persona?.role || persona?.company)}
                </p>
              )}

              {/* AI Badge Text - Show branding if enabled (hide in chatbot for space) */}
              {showBranding && !isChatbot && (
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    paddingTop: "0.5rem",
                  }}
                >
                  <div
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      fontSize: "0.875rem",
                      fontWeight: "600",
                      color: primaryColor,
                    }}
                  >
                    <Sparkles style={{ width: "1rem", height: "1rem" }} />
                    <span>{t("widget.aiPowered")}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Chat Interface */}
          <div
            className="embed-chat-content"
            style={{
              flex: 1,
              overflow: "auto",
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
            }}
          >
            {config.expertUsername ? (
              <div
                className="embed-widget-chat-wrapper"
                style={{
                  height: "100%",
                  width: "100%",
                  display: "flex",
                  flexDirection: "column",
                  padding: isChatbot
                    ? "0 0.75rem 1rem 0.75rem"
                    : "0 1rem 1.5rem 1rem",
                }}
              >
                <ExpertChatInterface
                  username={config.expertUsername}
                  personaName={config.personaName}
                  expertName={
                    persona?.fullname || persona?.name || config.expertUsername
                  }
                  avatarUrl={persona?.avatar}
                  widgetToken={config.widgetToken}
                  suggestedQuestions={persona?.suggested_questions}
                  emailCaptureEnabled={persona?.email_capture_enabled}
                  emailCaptureThreshold={
                    persona?.email_capture_message_threshold
                  }
                  emailCaptureRequireFullname={
                    persona?.email_capture_require_fullname
                  }
                  emailCaptureRequirePhone={
                    persona?.email_capture_require_phone
                  }
                  sessionTimeLimitEnabled={persona?.session_time_limit_enabled}
                  sessionTimeLimitMinutes={persona?.session_time_limit_minutes}
                  sessionTimeLimitWarningMinutes={
                    persona?.session_time_limit_warning_minutes
                  }
                  enableVoice={config.enableVoice}
                  calendarDisplayName={
                    persona?.calendar_display_name ?? undefined
                  }
                />
              </div>
            ) : (
              <div
                style={{
                  padding: "2rem",
                  textAlign: "center",
                  color: "#666",
                }}
              >
                <p>{t("widget.noUsername")}</p>
                <p style={{ fontSize: "0.875rem", marginTop: "0.5rem" }}>
                  expertUsername: &quot;{config.expertUsername}&quot;
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // ========================================
  // CHATBOT MODE: Bubble + modal independently positioned
  // ========================================
  if (isChatbotMode) {
    const isTop = modalPosition?.startsWith("top");
    const isLeft = modalPosition?.endsWith("left");

    // Get bubble position styles based on modalPosition
    // When collapsed: bubble is centered in the padded container
    // When expanded: bubble uses fixed positioning to stay in corner
    const getBubblePositionStyles = (): React.CSSProperties => {
      if (isExpanded) {
        return {
          position: "fixed",
          zIndex: 999999,
          [isTop ? "top" : "bottom"]: "20px",
          [isLeft ? "left" : "right"]: "20px",
        };
      }
      return {
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
      };
    };

    // Guide style modal positioning
    const getGuideModalStyles = (): React.CSSProperties => {
      const offset = `${20 + bubbleSizeNum + bubbleMargin}px`;
      return {
        position: "fixed",
        zIndex: 999998,
        width: chatbotWidth,
        height: chatbotHeight,
        maxWidth: "calc(100vw - 40px)",
        maxHeight: "calc(100vh - 120px)",
        [isTop ? "top" : "bottom"]: offset,
        [isLeft ? "left" : "right"]: "20px",
      };
    };

    return (
      <div className="embed-widget">
        {/* Chat Modal - Guide Style (new default) or Classic Style */}
        {isExpanded && chatbotStyle === "guide" ? (
          <div
            style={getGuideModalStyles()}
            className="guide-style-modal-wrapper"
          >
            <GuideStyleModal
              expertUsername={config.expertUsername}
              personaName={config.personaName}
              widgetToken={config.widgetToken}
              expertName={headerTitle}
              avatarUrl={avatarUrl}
              primaryColor={primaryColor}
              enableVoice={config.enableVoice}
              suggestedQuestions={persona?.suggested_questions}
              emailCaptureEnabled={persona?.email_capture_enabled}
              emailCaptureThreshold={persona?.email_capture_message_threshold}
              emailCaptureRequireFullname={
                persona?.email_capture_require_fullname
              }
              emailCaptureRequirePhone={persona?.email_capture_require_phone}
              sessionTimeLimitEnabled={persona?.session_time_limit_enabled}
              sessionTimeLimitMinutes={persona?.session_time_limit_minutes}
              sessionTimeLimitWarningMinutes={
                persona?.session_time_limit_warning_minutes
              }
              onClose={handleBubbleClick}
              isLoading={!persona && !config.expertUsername}
              calendarDisplayName={persona?.calendar_display_name ?? undefined}
              hideCloseButton={!!config.loaderBubble}
            />
          </div>
        ) : isExpanded ? (
          // Classic chatbot style (original implementation)
          renderChatModal(true)
        ) : null}

        {/* Bubble - centered when collapsed, fixed when expanded */}
        {/* Skip rendering bubble when the SDK loader handles it */}
        {!config.loaderBubble && (
          <div style={getBubblePositionStyles()}>
            <EmbedBubble
              text={config.bubbleText}
              icon={
                config.bubbleIcon ||
                branding.bubbleIcon ||
                avatarUrl ||
                undefined
              }
              primaryColor={primaryColor}
              bubbleSize={bubbleSize}
              bubbleBackgroundColor={bubbleBackgroundColor}
              bubbleTextColor={bubbleTextColor}
              onClick={handleBubbleClick}
              isExpanded={isExpanded}
              tooltipText={
                config.bubbleText !== "Chat with me"
                  ? config.bubbleText
                  : undefined
              }
              simpleBubble={simpleBubble}
            />
          </div>
        )}
      </div>
    );
  }

  // ========================================
  // INLINE MODE: No bubble, always expanded
  // ========================================
  if (isInlineMode) {
    return (
      <div
        className="embed-widget embed-inline-container"
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
        }}
      >
        {renderChatModal(false)}
      </div>
    );
  }

  // ========================================
  // CENTERED OVERLAY MODE: Traditional bubble + overlay modal
  // ========================================
  return (
    <div className="embed-widget">
      {/* Bubble - only visible when modal is closed */}
      {/* Skip rendering bubble when the SDK loader handles it */}
      {!config.loaderBubble && !isExpanded && (
        <EmbedBubble
          text={config.bubbleText}
          icon={
            config.bubbleIcon || branding.bubbleIcon || avatarUrl || undefined
          }
          primaryColor={primaryColor}
          bubbleSize={bubbleSize}
          bubbleBackgroundColor={bubbleBackgroundColor}
          bubbleTextColor={bubbleTextColor}
          onClick={handleBubbleClick}
          isExpanded={isExpanded}
          tooltipText={
            config.bubbleText !== "Chat with me" ? config.bubbleText : undefined
          }
          simpleBubble={simpleBubble}
        />
      )}

      {/* Modal with dark overlay */}
      {isExpanded && (
        <div
          className="embed-modal-overlay centered-modal-overlay"
          onClick={handleBubbleClick}
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 999998,
          }}
        >
          {renderChatModal(false)}
        </div>
      )}
    </div>
  );
};

export const EmbedApp: React.FC = () => {
  const [config, setConfig] = useState<EmbedConfig | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const isExpandedRef = useRef(false); // Track latest expanded state for messenger
  const [parentMethods, setParentMethods] = useState<ParentMethods | null>(
    null,
  );
  const [isReady, setIsReady] = useState(false);

  // Keep ref in sync with state
  useEffect(() => {
    isExpandedRef.current = isExpanded;
  }, [isExpanded]);

  /**
   * Parse configuration from URL parameters
   */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    const parsedConfig: EmbedConfig = {
      expertUsername: params.get("expertUsername") || "",
      personaName: params.get("personaName") || undefined,
      widgetToken: params.get("widgetToken") || "",
      mode:
        (params.get("mode") as "bubble" | "inline" | "fullpage") || "bubble",
      position: params.get("position") || "bottom-right",
      primaryColor: params.get("primaryColor") || "#f59e0b",
      bubbleText: params.get("bubbleText") || "Chat with me",
      bubbleIcon: params.get("bubbleIcon") || undefined,
      enableVoice: params.get("enableVoice") === "true",
      welcomeMessage: params.get("welcomeMessage") || undefined,
      inputPlaceholder:
        params.get("inputPlaceholder") || "Type your message...",
      customCss: params.get("customCss") || undefined,
      apiUrl: params.get("apiUrl") || undefined,
      livekitUrl: params.get("livekitUrl") || undefined,
      height: params.get("height") || "600px",
      lang: params.get("lang") || undefined,
      loaderBubble: params.get("loaderBubble") === "true",
    };

    // Parse new customization options
    const sizeParam = params.get("size");
    if (sizeParam) {
      try {
        parsedConfig.size = JSON.parse(sizeParam);
      } catch (error) {
        console.error("Failed to parse size config:", error);
      }
    }

    const themeParam = params.get("theme");
    if (themeParam) {
      try {
        parsedConfig.theme = JSON.parse(themeParam);
      } catch (error) {
        console.error("Failed to parse theme config:", error);
      }
    }

    const layoutParam = params.get("layout");
    if (layoutParam) {
      try {
        parsedConfig.layout = JSON.parse(layoutParam);
      } catch (error) {
        console.error("Failed to parse layout config:", error);
      }
    }

    const brandingParam = params.get("branding");
    if (brandingParam) {
      try {
        parsedConfig.branding = JSON.parse(brandingParam);
      } catch (error) {
        console.error("Failed to parse branding config:", error);
      }
    }

    // Auto-expand if inline, fullpage, or loaderBubble mode
    // When loaderBubble is true, the loader handles the bubble and the iframe
    // only needs to show the chat modal — so start expanded
    if (
      parsedConfig.mode === "inline" ||
      parsedConfig.mode === "fullpage" ||
      parsedConfig.loaderBubble
    ) {
      setIsExpanded(true);
    }

    // Parse user object if provided
    const userParam = params.get("user");
    if (userParam) {
      try {
        parsedConfig.user = JSON.parse(userParam);
      } catch (error) {
        console.error("Failed to parse user config:", error);
      }
    }

    setConfig(parsedConfig);

    // Store widget token in sessionStorage for API client interceptor
    if (parsedConfig.widgetToken) {
      sessionStorage.setItem("widget_token", parsedConfig.widgetToken);
    }

    // Set environment variables globally for embed context
    // This makes them available to components that import from @/env
    if (parsedConfig.apiUrl) {
      (window as { EMBED_API_URL?: string }).EMBED_API_URL =
        parsedConfig.apiUrl;
    }
    if (parsedConfig.livekitUrl) {
      (window as { EMBED_LIVEKIT_URL?: string }).EMBED_LIVEKIT_URL =
        parsedConfig.livekitUrl;
    }

    // Apply custom CSS if provided
    if (parsedConfig.customCss) {
      const style = document.createElement("style");
      style.textContent = parsedConfig.customCss;
      document.head.appendChild(style);
    }

    // Apply primary color CSS variable
    // Convert hex to HSL for CSS variable (Tailwind expects HSL format)
    const hexToHSL = (hex: string): string => {
      // Remove # if present
      hex = hex.replace("#", "");

      // Parse hex values
      const r = parseInt(hex.substring(0, 2), 16) / 255;
      const g = parseInt(hex.substring(2, 4), 16) / 255;
      const b = parseInt(hex.substring(4, 6), 16) / 255;

      const max = Math.max(r, g, b);
      const min = Math.min(r, g, b);
      let h = 0,
        s = 0,
        l = (max + min) / 2;

      if (max !== min) {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

        switch (max) {
          case r:
            h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
            break;
          case g:
            h = ((b - r) / d + 2) / 6;
            break;
          case b:
            h = ((r - g) / d + 4) / 6;
            break;
        }
      }

      h = Math.round(h * 360);
      s = Math.round(s * 100);
      l = Math.round(l * 100);

      return `${h} ${s}% ${l}%`;
    };

    const hslValue = hexToHSL(parsedConfig.primaryColor);
    document.documentElement.style.setProperty("--primary", hslValue);
  }, []);

  /**
   * Setup postMessage connection with parent
   * Only run once on mount to avoid recreating messenger
   */
  useEffect(() => {
    // Define methods that the child exposes to the parent
    const childMethods = {
      open: () => {
        setIsExpanded(true);
      },
      close: () => {
        setIsExpanded(false);
      },
      toggle: () => {
        setIsExpanded((prev) => !prev);
      },
      setUser: (...args: unknown[]) => {
        const user = args[0] as EmbedConfig["user"];
        setConfig((prev) => (prev ? { ...prev, user } : null));
      },
      isExpanded: () => {
        // Use ref to get latest value (avoid stale closure)
        return isExpandedRef.current;
      },
    };

    // Create messenger only once
    const messenger = new ChildMessenger<ParentMethods>(childMethods);

    // Store messenger in a ref-like way by creating parent methods wrapper
    const parentMethodsWrapper: ParentMethods = {
      notifyOpen: () => messenger.call("notifyOpen"),
      notifyClose: () => messenger.call("notifyClose"),
      notifyMessage: (msg: string) => messenger.call("notifyMessage", msg),
      notifyEmailSubmit: (email: string) =>
        messenger.call("notifyEmailSubmit", email),
      notifyError: (error: string) => messenger.call("notifyError", error),
      notifyAvatarUrl: (url: string) => messenger.call("notifyAvatarUrl", url),
    };

    setParentMethods(parentMethodsWrapper);
    setIsReady(true);

    // Cleanup on unmount
    return () => {
      messenger.destroy();
    };
  }, []); // Empty deps - only create messenger once

  /**
   * Notify parent when expanded state changes
   */
  useEffect(() => {
    if (!parentMethods || !isReady) return;

    if (isExpanded) {
      parentMethods.notifyOpen();
    } else {
      parentMethods.notifyClose();
    }
  }, [isExpanded, parentMethods, isReady]);

  /**
   * Handle bubble click
   * Note: notifyOpen/notifyClose will be called by the useEffect that watches isExpanded
   */
  const handleBubbleClick = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  // Show loading state until config is ready
  if (!config || !isReady) {
    return null;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <EmbedWithI18n
        config={config}
        isExpanded={isExpanded}
        handleBubbleClick={handleBubbleClick}
        parentMethods={parentMethods}
      />
    </QueryClientProvider>
  );
};
