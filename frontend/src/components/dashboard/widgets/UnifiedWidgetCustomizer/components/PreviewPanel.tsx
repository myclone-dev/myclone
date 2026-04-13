"use client";

import { Card } from "@/components/ui/card";
import { Sparkles, Send, Mic, MessageSquare } from "lucide-react";
import { WidgetConfig, EffectiveColors } from "../types";

// Preview dimension constants
const PREVIEW_WIDTH = 260;
const MAX_PREVIEW_HEIGHT = 320;
const DEFAULT_CONFIG_WIDTH = 900;
const DEFAULT_CONFIG_HEIGHT = 820;
const PREVIEW_CONTAINER_HEIGHT = 420;

interface PreviewPanelProps {
  config: WidgetConfig;
  colors: EffectiveColors;
  username: string;
}

export function PreviewPanel({ config, colors, username }: PreviewPanelProps) {
  // Check if chatbot mode is enabled (modalPosition is set to a corner position)
  const isChatbotMode =
    !!config.modalPosition && config.modalPosition !== "centered";

  // Check if guide style is selected for chatbot mode
  const isGuideStyle = isChatbotMode && config.chatbotStyle === "guide";

  // Calculate preview dimensions maintaining aspect ratio
  const getPreviewDimensions = () => {
    // Use chatbot dimensions if in chatbot mode
    const configHeight = isChatbotMode
      ? parseInt(config.chatbotHeight) || 550
      : parseInt(config.height) || DEFAULT_CONFIG_HEIGHT;
    const configWidth = isChatbotMode
      ? parseInt(config.chatbotWidth) || 380
      : parseInt(config.width) || DEFAULT_CONFIG_WIDTH;
    const aspectRatio = configHeight / configWidth;
    const previewHeight = Math.min(
      Math.round(PREVIEW_WIDTH * aspectRatio),
      MAX_PREVIEW_HEIGHT,
    );
    return { width: PREVIEW_WIDTH, height: previewHeight };
  };

  const previewSize = getPreviewDimensions();

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-col gap-2 border-b bg-slate-50 px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-4">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-slate-900">Live Preview</h3>
          <p className="text-xs text-slate-500">
            Scaled preview of your widget
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          <div className="rounded-md bg-indigo-100 px-2 py-1 text-xs font-medium text-indigo-700 whitespace-nowrap">
            {config.width} × {config.height}
          </div>
          <div className="rounded-md bg-slate-200 px-2 py-1 text-xs font-medium text-slate-600 whitespace-nowrap">
            Bubble: {config.bubbleSize}
          </div>
        </div>
      </div>

      {/* Preview Container */}
      <div
        className="relative overflow-hidden bg-gradient-to-br from-slate-100 to-slate-200"
        style={{ height: `${PREVIEW_CONTAINER_HEIGHT}px` }}
      >
        {/* Browser mockup header */}
        <div className="absolute left-4 top-4 flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="size-2.5 rounded-full bg-red-400" />
            <div className="size-2.5 rounded-full bg-yellow-400" />
            <div className="size-2.5 rounded-full bg-green-400" />
          </div>
          <span className="ml-2 text-xs text-slate-400">yourwebsite.com</span>
        </div>

        {/* Test in Real button */}
        <a
          href="/test-embed"
          target="_blank"
          rel="noopener noreferrer"
          className="absolute right-4 top-4 flex items-center gap-1.5 rounded-md bg-slate-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-colors hover:bg-slate-700"
        >
          Test in Real
        </a>

        {/* Chat Modal Preview */}
        <div
          className="absolute flex flex-col overflow-hidden shadow-2xl transition-all duration-300"
          style={{
            width: `${previewSize.width}px`,
            height: `${previewSize.height}px`,
            backgroundColor: isGuideStyle ? "#ffffff" : colors.background,
            borderRadius: config.borderRadius,
            // Position based on modalPosition setting
            ...(isChatbotMode
              ? {
                  // Chatbot mode - position in corner
                  ...(config.modalPosition === "bottom-right" && {
                    bottom: "10px",
                    right: "10px",
                  }),
                  ...(config.modalPosition === "bottom-left" && {
                    bottom: "10px",
                    left: "10px",
                  }),
                  ...(config.modalPosition === "top-right" && {
                    top: "40px",
                    right: "10px",
                  }),
                  ...(config.modalPosition === "top-left" && {
                    top: "40px",
                    left: "10px",
                  }),
                }
              : {
                  // Centered overlay mode
                  left: "50%",
                  top: "50%",
                  transform: "translate(-50%, -50%)",
                }),
          }}
        >
          {isGuideStyle ? (
            /* Guide Style Preview */
            <>
              {/* Header with mode toggle */}
              <div
                className="flex-shrink-0 flex items-center justify-center py-2 px-2 relative"
                style={{
                  borderBottom: "1px solid rgba(0,0,0,0.05)",
                  background: "rgba(250, 250, 250, 0.5)",
                }}
              >
                {/* Mode Toggle */}
                <div className="flex items-center bg-gray-100 rounded-full p-0.5">
                  <div className="flex items-center gap-1 bg-gray-900 text-white rounded-full px-2.5 py-1">
                    <Mic className="size-2.5" />
                    <span className="text-[8px] font-medium">Voice</span>
                  </div>
                  <div className="flex items-center gap-1 text-gray-500 rounded-full px-2.5 py-1">
                    <MessageSquare className="size-2.5" />
                    <span className="text-[8px] font-medium">Text</span>
                  </div>
                </div>
                {/* Close button indicator */}
                <div className="absolute right-1.5 w-4 h-4 rounded-full bg-gray-100 flex items-center justify-center">
                  <span className="text-[8px] text-gray-400">×</span>
                </div>
              </div>

              {/* Main content - centered avatar with animated rings */}
              <div
                className="flex-1 flex flex-col items-center justify-center p-4 relative"
                style={{
                  background:
                    "linear-gradient(180deg, #fafafa 0%, #f5f5f5 100%)",
                }}
              >
                {/* Subtle dot pattern */}
                <div
                  className="absolute inset-0 opacity-20"
                  style={{
                    backgroundImage:
                      "radial-gradient(circle at 2px 2px, #e5e5e5 1px, transparent 0)",
                    backgroundSize: "16px 16px",
                  }}
                />

                {/* Avatar with animated rings preview */}
                <div className="relative z-10 mb-3">
                  {/* Outer ring 1 */}
                  <div
                    className="absolute inset-0 rounded-full border border-primary/20"
                    style={{
                      width: "56px",
                      height: "56px",
                      left: "50%",
                      top: "50%",
                      transform: "translate(-50%, -50%) scale(1.4)",
                    }}
                  />
                  {/* Outer ring 2 */}
                  <div
                    className="absolute inset-0 rounded-full border border-primary/30"
                    style={{
                      width: "56px",
                      height: "56px",
                      left: "50%",
                      top: "50%",
                      transform: "translate(-50%, -50%) scale(1.2)",
                    }}
                  />
                  {/* Avatar */}
                  <div
                    className="relative flex items-center justify-center overflow-hidden rounded-full shadow-lg ring-2 ring-white/50"
                    style={{
                      width: "40px",
                      height: "40px",
                      background: config.avatarUrl
                        ? "#fff"
                        : "linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 50%, #1a1a1a 100%)",
                    }}
                  >
                    {config.avatarUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={config.avatarUrl}
                        alt="Avatar"
                        className="size-full object-cover"
                      />
                    ) : (
                      <span className="text-sm font-semibold text-white">
                        {(config.headerTitle || username || "E")
                          .charAt(0)
                          .toUpperCase()}
                      </span>
                    )}
                  </div>
                  {/* Status dot */}
                  <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-green-500 border-2 border-white" />
                </div>

                {/* Name and status */}
                <div className="relative z-10 text-center mb-4">
                  <h4 className="text-xs font-semibold text-gray-900 mb-0.5">
                    {config.headerTitle || username || "Expert Name"}
                  </h4>
                  <p className="text-[9px] text-gray-500">Speaking...</p>
                </div>

                {/* Control buttons */}
                <div className="relative z-10 flex items-center gap-2">
                  {/* Mute button */}
                  <div className="w-8 h-8 rounded-full bg-white border border-gray-200 flex items-center justify-center shadow-sm">
                    <Mic className="size-3.5 text-gray-600" />
                  </div>
                  {/* Transcript toggle */}
                  <div className="w-7 h-7 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center">
                    <MessageSquare className="size-3 text-primary" />
                  </div>
                  {/* End call */}
                  <div className="w-8 h-8 rounded-full bg-red-500 flex items-center justify-center shadow-sm">
                    <span className="text-white text-[8px]">✕</span>
                  </div>
                </div>
              </div>

              {/* Live transcript panel */}
              <div
                className="flex-shrink-0 border-t border-gray-200 bg-white"
                style={{ height: "60px" }}
              >
                <div className="px-2 py-1 border-b border-gray-100 flex items-center justify-between bg-gray-50">
                  <div className="flex items-center gap-1">
                    <div className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                    <span className="text-[8px] font-medium text-gray-600">
                      Live Transcript
                    </span>
                  </div>
                  <span className="text-[7px] text-gray-400">2 messages</span>
                </div>
                <div className="p-1.5 space-y-1 overflow-hidden">
                  <div className="bg-black text-white text-[7px] rounded px-1.5 py-0.5 ml-4">
                    Hi there!
                  </div>
                  <div className="bg-gray-100 text-gray-800 text-[7px] rounded px-1.5 py-0.5 mr-4">
                    Hello! How can I help?
                  </div>
                </div>
              </div>
            </>
          ) : (
            /* Classic Style Preview */
            <>
              {/* Header */}
              <div
                className="flex-shrink-0 p-3 text-center"
                style={{
                  background: colors.headerBg,
                  borderBottom: "1px solid rgba(0,0,0,0.05)",
                }}
              >
                {config.showAvatar && (
                  <div className="mb-2 flex justify-center">
                    <div className="relative">
                      <div
                        className="flex size-10 items-center justify-center overflow-hidden rounded-full border-2 border-white shadow-md"
                        style={{
                          background: config.avatarUrl
                            ? "#fff"
                            : `linear-gradient(to bottom right, ${colors.primary}, ${colors.primary}cc)`,
                        }}
                      >
                        {config.avatarUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={config.avatarUrl}
                            alt="Avatar"
                            className="size-full object-cover"
                          />
                        ) : (
                          <span
                            className="text-sm font-semibold"
                            style={{ color: colors.bubbleText }}
                          >
                            {(config.headerTitle || username || "E")
                              .charAt(0)
                              .toUpperCase()}
                          </span>
                        )}
                      </div>
                      <div
                        className="absolute -bottom-0.5 -right-0.5 flex size-4 items-center justify-center rounded-full border border-white shadow-sm"
                        style={{
                          background: `linear-gradient(to bottom right, ${colors.primary}, ${colors.primary}cc)`,
                        }}
                      >
                        <Sparkles
                          className="size-2.5"
                          style={{ color: "white" }}
                        />
                      </div>
                    </div>
                  </div>
                )}

                <h4
                  className="text-sm font-semibold"
                  style={{ color: colors.text }}
                >
                  {config.headerTitle || username || "Expert Name"}
                </h4>

                {config.showBranding && (
                  <div
                    className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium"
                    style={{ color: colors.primary }}
                  >
                    <Sparkles className="size-3" />
                    <span>AI powered digital clone</span>
                  </div>
                )}
              </div>

              {/* Chat Messages */}
              <div className="flex flex-1 flex-col gap-1.5 overflow-hidden p-2">
                <div className="flex justify-end">
                  <div
                    className="max-w-[80%] rounded-lg px-2.5 py-1 text-[10px]"
                    style={{
                      backgroundColor: colors.userMsgBg,
                      color: colors.userMsgText,
                    }}
                  >
                    Hello! I have a question.
                  </div>
                </div>
                <div className="flex justify-start">
                  <div
                    className="max-w-[80%] rounded-lg px-2.5 py-1 text-[10px]"
                    style={{
                      backgroundColor: colors.botMsgBg,
                      color: colors.botMsgText,
                    }}
                  >
                    Hello! How can I help you?
                  </div>
                </div>
              </div>

              {/* Input Area */}
              <div
                className="flex-shrink-0 border-t p-2"
                style={{ borderColor: "rgba(0,0,0,0.05)" }}
              >
                <div className="flex items-center gap-2 rounded-lg border bg-white px-3 py-2">
                  <span className="flex-1 text-xs text-slate-400">
                    Type your message...
                  </span>
                  <Send className="size-4" style={{ color: colors.primary }} />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Bubble Button */}
        <div
          className="absolute flex items-center justify-center rounded-full shadow-lg transition-all duration-300 overflow-hidden"
          style={{
            width: config.bubbleSize,
            height: config.bubbleSize,
            background: colors.bubbleBg,
            ...(config.position === "bottom-right" && {
              bottom: "10px",
              right: "10px",
            }),
            ...(config.position === "bottom-left" && {
              bottom: "10px",
              left: "10px",
            }),
            ...(config.position === "top-right" && {
              top: "40px",
              right: "10px",
            }),
            ...(config.position === "top-left" && {
              top: "40px",
              left: "10px",
            }),
          }}
        >
          {config.bubbleIcon || config.avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={config.bubbleIcon || config.avatarUrl}
              alt="Bubble Icon"
              className="size-full object-cover"
              style={{
                border: "2px solid rgba(255, 255, 255, 0.9)",
                borderRadius: "50%",
              }}
            />
          ) : (
            <svg
              width="20"
              height="20"
              viewBox="0 0 28 28"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M14 2.33337C7.55672 2.33337 2.33337 7.03171 2.33337 12.8334C2.33337 15.3184 3.29837 17.5867 4.90171 19.3634V25.6667L10.7617 22.5167C11.8017 22.7517 12.8834 22.8767 14 22.8767C20.4434 22.8767 25.6667 18.1784 25.6667 12.3767C25.6667 6.57504 20.4434 2.33337 14 2.33337Z"
                fill={colors.bubbleText}
              />
            </svg>
          )}
        </div>
      </div>
    </Card>
  );
}
