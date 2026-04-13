"use client";

/**
 * Test page for MyClone Embed Widget
 * This page demonstrates how to integrate and test the embed widget
 * Reads configuration from localStorage (saved by WidgetCustomizer)
 */

import { useEffect, useState, useCallback } from "react";

// Same storage key as WidgetCustomizer
const WIDGET_CONFIG_STORAGE_KEY = "myclone_widget_config";

interface WidgetAPI {
  open: () => Promise<void>;
  close: () => Promise<void>;
  toggle: () => Promise<void>;
  setUser: (user: { email?: string; name?: string }) => Promise<void>;
  destroy: () => void;
}

interface SavedWidgetConfig {
  // Meta
  expertUsername?: string;
  widgetToken?: string;
  personaName?: string;
  // Size
  width?: string;
  height?: string;
  bubbleSize?: string;
  borderRadius?: string;
  chatbotWidth?: string;
  chatbotHeight?: string;
  // Theme
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
  // Layout
  position?: string;
  offsetX?: string;
  offsetY?: string;
  modalPosition?: string;
  chatbotStyle?: "guide" | "classic";
  // Branding
  showBranding?: boolean;
  headerTitle?: string;
  headerSubtitle?: string;
  avatarUrl?: string;
  showAvatar?: boolean;
  bubbleIcon?: string;
  simpleBubble?: boolean;
  // Behavior
  enableVoice?: boolean;
  bubbleText?: string;
  welcomeMessage?: string;
}

export default function TestEmbedPage() {
  const [widget, setWidget] = useState<WidgetAPI | null>(null);
  const [status, setStatus] = useState("Widget not initialized");
  const [events, setEvents] = useState<string[]>([]);
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [savedConfig, setSavedConfig] = useState<SavedWidgetConfig | null>(
    null,
  );
  const [configLoaded, setConfigLoaded] = useState(false);

  const logEvent = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setEvents((prev) => [`[${timestamp}] ${message}`, ...prev.slice(0, 9)]);
  }, []);

  const updateStatus = useCallback(
    (message: string) => {
      setStatus(message);
      logEvent(message);
    },
    [logEvent],
  );

  // Load saved config from localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(WIDGET_CONFIG_STORAGE_KEY);
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          setSavedConfig(parsed);
          logEvent("✅ Custom config loaded from dashboard");
        } catch {
          logEvent("Using default config");
        }
      } else {
        logEvent("No saved config found, using defaults");
      }
      setConfigLoaded(true);
    }
  }, [logEvent]);

  // Load the SDK script
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "/embed/myclone-embed.js";
    script.async = true;
    script.onload = () => {
      setScriptLoaded(true);
      logEvent("SDK script loaded");
    };
    script.onerror = () => {
      logEvent("❌ Failed to load SDK script");
    };
    document.body.appendChild(script);

    logEvent("Page loaded. SDK script loading...");

    return () => {
      if (script.parentNode) {
        document.body.removeChild(script);
      }
    };
  }, [logEvent]);

  const initWidget = useCallback(() => {
    if (widget) {
      updateStatus("Widget already initialized");
      return;
    }

    if (!scriptLoaded) {
      updateStatus("❌ SDK script not loaded yet");
      return;
    }

    try {
      const MyClone = (
        window as typeof window & {
          MyClone?: (config: Record<string, unknown>) => WidgetAPI;
        }
      ).MyClone;
      if (!MyClone) {
        updateStatus("❌ MyClone SDK not found");
        return;
      }

      // Build config from saved settings or use defaults
      const config: Record<string, unknown> = {
        mode: "bubble",
        expertUsername: savedConfig?.expertUsername || "demo-user",
        personaName: savedConfig?.personaName || undefined,
        widgetToken: savedConfig?.widgetToken || "",
        position: savedConfig?.position || "bottom-right",
        bubbleText: savedConfig?.bubbleText || "Chat with me",
        enableVoice: savedConfig?.enableVoice ?? true,
        welcomeMessage: savedConfig?.welcomeMessage || undefined,

        // Callbacks
        onOpen: () => logEvent("✅ Widget opened"),
        onClose: () => logEvent("❌ Widget closed"),
        onMessage: (msg: string) => logEvent(`💬 Message: ${msg}`),
        onEmailSubmit: (email: string) => logEvent(`📧 Email: ${email}`),
        onError: (error: Error) => logEvent(`⚠️ Error: ${error.message}`),
      };

      // Add size config if customized
      const sizeConfig: Record<string, string> = {};
      if (savedConfig?.width) sizeConfig.width = savedConfig.width;
      if (savedConfig?.height) sizeConfig.height = savedConfig.height;
      if (savedConfig?.bubbleSize)
        sizeConfig.bubbleSize = savedConfig.bubbleSize;
      if (savedConfig?.borderRadius)
        sizeConfig.borderRadius = savedConfig.borderRadius;
      if (savedConfig?.chatbotWidth)
        sizeConfig.chatbotWidth = savedConfig.chatbotWidth;
      if (savedConfig?.chatbotHeight)
        sizeConfig.chatbotHeight = savedConfig.chatbotHeight;
      if (Object.keys(sizeConfig).length > 0) {
        config.size = sizeConfig;
      }

      // Add theme config if customized
      const themeConfig: Record<string, string> = {};
      if (savedConfig?.primaryColor)
        themeConfig.primaryColor = savedConfig.primaryColor;
      if (savedConfig?.backgroundColor)
        themeConfig.backgroundColor = savedConfig.backgroundColor;
      if (savedConfig?.headerBackground)
        themeConfig.headerBackground = savedConfig.headerBackground;
      if (savedConfig?.textColor) themeConfig.textColor = savedConfig.textColor;
      if (savedConfig?.textSecondaryColor)
        themeConfig.textSecondaryColor = savedConfig.textSecondaryColor;
      if (savedConfig?.bubbleBackgroundColor)
        themeConfig.bubbleBackgroundColor = savedConfig.bubbleBackgroundColor;
      if (savedConfig?.bubbleTextColor)
        themeConfig.bubbleTextColor = savedConfig.bubbleTextColor;
      if (savedConfig?.userMessageBg)
        themeConfig.userMessageBg = savedConfig.userMessageBg;
      if (savedConfig?.botMessageBg)
        themeConfig.botMessageBg = savedConfig.botMessageBg;
      if (savedConfig?.userMessageTextColor)
        themeConfig.userMessageTextColor = savedConfig.userMessageTextColor;
      if (savedConfig?.botMessageTextColor)
        themeConfig.botMessageTextColor = savedConfig.botMessageTextColor;
      if (Object.keys(themeConfig).length > 0) {
        config.theme = themeConfig;
      }

      // Add layout config if customized
      const layoutConfig: Record<string, string> = {};
      if (savedConfig?.position) layoutConfig.position = savedConfig.position;
      if (savedConfig?.offsetX) layoutConfig.offsetX = savedConfig.offsetX;
      if (savedConfig?.offsetY) layoutConfig.offsetY = savedConfig.offsetY;
      if (savedConfig?.modalPosition)
        layoutConfig.modalPosition = savedConfig.modalPosition;
      if (savedConfig?.chatbotStyle)
        layoutConfig.chatbotStyle = savedConfig.chatbotStyle;
      if (Object.keys(layoutConfig).length > 0) {
        config.layout = layoutConfig;
      }

      // Add branding config if customized
      const brandingConfig: Record<string, unknown> = {};
      if (savedConfig?.showBranding !== undefined)
        brandingConfig.showBranding = savedConfig.showBranding;
      if (savedConfig?.headerTitle)
        brandingConfig.headerTitle = savedConfig.headerTitle;
      if (savedConfig?.headerSubtitle)
        brandingConfig.headerSubtitle = savedConfig.headerSubtitle;
      if (savedConfig?.avatarUrl)
        brandingConfig.avatarUrl = savedConfig.avatarUrl;
      if (savedConfig?.showAvatar !== undefined)
        brandingConfig.showAvatar = savedConfig.showAvatar;
      if (savedConfig?.bubbleIcon)
        brandingConfig.bubbleIcon = savedConfig.bubbleIcon;
      if (savedConfig?.simpleBubble !== undefined)
        brandingConfig.simpleBubble = savedConfig.simpleBubble;
      if (Object.keys(brandingConfig).length > 0) {
        config.branding = brandingConfig;
      }

      const newWidget = MyClone(config);

      setWidget(newWidget);
      if (savedConfig?.expertUsername) {
        updateStatus(
          `✅ Widget initialized with custom config (${savedConfig.expertUsername})`,
        );
      } else {
        updateStatus("✅ Widget initialized with default config");
      }
    } catch (error) {
      updateStatus(
        `❌ Error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }, [widget, scriptLoaded, savedConfig, updateStatus, logEvent]);

  const openWidget = useCallback(async () => {
    if (!widget) {
      updateStatus("❌ Initialize widget first");
      return;
    }
    try {
      await widget.open();
      updateStatus("Opening widget...");
    } catch (error) {
      updateStatus(
        `❌ Error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }, [widget, updateStatus]);

  const closeWidget = useCallback(async () => {
    if (!widget) {
      updateStatus("❌ Initialize widget first");
      return;
    }
    try {
      await widget.close();
      updateStatus("Closing widget...");
    } catch (error) {
      updateStatus(
        `❌ Error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }, [widget, updateStatus]);

  const toggleWidget = useCallback(async () => {
    if (!widget) {
      updateStatus("❌ Initialize widget first");
      return;
    }
    try {
      await widget.toggle();
      updateStatus("Toggling widget...");
    } catch (error) {
      updateStatus(
        `❌ Error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }, [widget, updateStatus]);

  const setUser = useCallback(async () => {
    if (!widget) {
      updateStatus("❌ Initialize widget first");
      return;
    }
    try {
      await widget.setUser({
        email: "test@example.com",
        name: "Test User",
      });
      updateStatus("✅ User info set");
    } catch (error) {
      updateStatus(
        `❌ Error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }, [widget, updateStatus]);

  const destroyWidget = useCallback(() => {
    if (!widget) {
      updateStatus("❌ No widget to destroy");
      return;
    }
    try {
      widget.destroy();
      setWidget(null);
      updateStatus("✅ Widget destroyed");
    } catch (error) {
      updateStatus(
        `❌ Error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }, [widget, updateStatus]);

  return (
    <div className="min-h-screen bg-gray-100 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-xl shadow-lg p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            MyClone Widget Test Page
          </h1>
          <p className="text-gray-600 mb-8">Test the embed SDK functionality</p>

          {/* Script Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <h3 className="text-sm font-semibold text-blue-900 mb-2">
              Script Loading Status
            </h3>
            <div className="text-xs font-mono text-blue-800">
              <div>
                Script URL:{" "}
                <span className="text-blue-600">/embed/myclone-embed.js</span>
              </div>
              <div>
                Status:{" "}
                <span
                  className={
                    scriptLoaded ? "text-green-600" : "text-orange-600"
                  }
                >
                  {scriptLoaded ? "✅ Loaded" : "⏳ Loading..."}
                </span>
              </div>
            </div>
          </div>

          {/* Current Config Summary */}
          {savedConfig && configLoaded && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
              <h3 className="text-sm font-semibold text-amber-900 mb-3 flex items-center gap-2">
                <span className="size-2 bg-green-500 rounded-full"></span>
                Configuration from Dashboard
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-amber-700">Username:</span>
                  <span className="ml-1 font-medium text-amber-900">
                    {savedConfig.expertUsername || "demo-user"}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-amber-700">Primary:</span>
                  <div
                    className="size-4 rounded border border-amber-300"
                    style={{
                      backgroundColor: savedConfig.primaryColor || "#f59e0b",
                    }}
                  />
                  <span className="font-mono text-amber-900">
                    {savedConfig.primaryColor || "#f59e0b"}
                  </span>
                </div>
                <div>
                  <span className="text-amber-700">Bubble Position:</span>
                  <span className="ml-1 font-medium text-amber-900">
                    {savedConfig.position || "bottom-right"}
                  </span>
                </div>
                <div>
                  <span className="text-amber-700">Modal Position:</span>
                  <span className="ml-1 font-medium text-amber-900">
                    {savedConfig.modalPosition || "centered"}
                  </span>
                </div>
                <div>
                  <span className="text-amber-700">Voice:</span>
                  <span className="ml-1 font-medium text-amber-900">
                    {savedConfig.enableVoice !== false ? "Enabled" : "Disabled"}
                  </span>
                </div>
              </div>
              <p className="text-xs text-amber-600 mt-3">
                Edit in Dashboard → Widgets → Customize tab
              </p>
            </div>
          )}

          {!savedConfig && configLoaded && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-gray-600">
                No custom configuration found. Using default settings.
                <br />
                <span className="text-xs text-gray-500">
                  Tip: Go to Dashboard → Widgets → Customize tab to create your
                  custom widget configuration.
                </span>
              </p>
            </div>
          )}

          {/* Controls */}
          <div className="flex flex-wrap gap-3 mb-6">
            <button
              onClick={initWidget}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              Initialize Widget
            </button>
            <button
              onClick={openWidget}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              Open
            </button>
            <button
              onClick={closeWidget}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              Close
            </button>
            <button
              onClick={toggleWidget}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              Toggle
            </button>
            <button
              onClick={setUser}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              Set User
            </button>
            <button
              onClick={destroyWidget}
              className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
            >
              Destroy
            </button>
          </div>

          {/* Status */}
          <div className="bg-gray-50 rounded-lg p-4 mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Status</h3>
            <div className="font-mono text-sm text-gray-900">{status}</div>
          </div>

          {/* Events Log */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">
              Events Log
            </h3>
            <div className="font-mono text-xs text-gray-700 space-y-1">
              {events.length === 0 ? (
                <div className="text-gray-500">No events yet</div>
              ) : (
                events.map((event, idx) => (
                  <div key={idx} className="py-1">
                    {event}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
