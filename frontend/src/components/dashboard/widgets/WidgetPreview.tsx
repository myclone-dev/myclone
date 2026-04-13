"use client";

import { useEffect, useState } from "react";
import {
  ExternalLink,
  Palette,
  Check,
  Code2,
  Play,
  AlertCircle,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

// Same storage key as WidgetCustomizer
const WIDGET_CONFIG_STORAGE_KEY = "myclone_widget_config";

interface SavedConfig {
  expertUsername?: string;
  primaryColor?: string;
  backgroundColor?: string;
  position?: string;
  enableVoice?: boolean;
  bubbleText?: string;
  width?: string;
  height?: string;
  widgetToken?: string;
  bubbleSize?: string;
  borderRadius?: string;
  headerBackground?: string;
  textColor?: string;
  textSecondaryColor?: string;
  bubbleBackgroundColor?: string;
  bubbleTextColor?: string;
  userMessageBg?: string;
  botMessageBg?: string;
  userMessageTextColor?: string;
  botMessageTextColor?: string;
  offsetX?: string;
  offsetY?: string;
  showBranding?: boolean;
  headerTitle?: string;
  headerSubtitle?: string;
  avatarUrl?: string;
  showAvatar?: boolean;
  [key: string]: unknown;
}

interface WidgetPreviewProps {
  username: string;
}

// Helper to extract a string value from the script
function extractStringValue(script: string, key: string): string | undefined {
  // Match patterns like: key: "value" or key: 'value'
  const regex = new RegExp(`${key}:\\s*["']([^"']+)["']`, "i");
  const match = script.match(regex);
  return match?.[1];
}

// Helper to extract a boolean value from the script
function extractBooleanValue(script: string, key: string): boolean | undefined {
  const regex = new RegExp(`${key}:\\s*(true|false)`, "i");
  const match = script.match(regex);
  if (match) {
    return match[1].toLowerCase() === "true";
  }
  return undefined;
}

// Parse the pasted script to extract config values using regex extraction
function parseScriptConfig(script: string): SavedConfig | null {
  try {
    // Check if it contains window.MyClone
    if (!script.includes("window.MyClone") && !script.includes("MyClone(")) {
      return null;
    }

    const config: SavedConfig = {};

    // Extract top-level values
    const expertUsername = extractStringValue(script, "expertUsername");
    if (expertUsername) config.expertUsername = expertUsername;

    const widgetToken = extractStringValue(script, "widgetToken");
    if (widgetToken && widgetToken !== "YOUR_WIDGET_TOKEN") {
      config.widgetToken = widgetToken;
    }

    const position = extractStringValue(script, "position");
    if (position) config.position = position;

    const bubbleText = extractStringValue(script, "bubbleText");
    if (bubbleText) config.bubbleText = bubbleText;

    const enableVoice = extractBooleanValue(script, "enableVoice");
    if (enableVoice !== undefined) config.enableVoice = enableVoice;

    // Extract size values
    const width = extractStringValue(script, "width");
    if (width) config.width = width;

    const height = extractStringValue(script, "height");
    if (height) config.height = height;

    const bubbleSize = extractStringValue(script, "bubbleSize");
    if (bubbleSize) config.bubbleSize = bubbleSize;

    const borderRadius = extractStringValue(script, "borderRadius");
    if (borderRadius) config.borderRadius = borderRadius;

    // Extract theme values
    const primaryColor = extractStringValue(script, "primaryColor");
    if (primaryColor) config.primaryColor = primaryColor;

    const backgroundColor = extractStringValue(script, "backgroundColor");
    if (backgroundColor) config.backgroundColor = backgroundColor;

    const headerBackground = extractStringValue(script, "headerBackground");
    if (headerBackground) config.headerBackground = headerBackground;

    const textColor = extractStringValue(script, "textColor");
    if (textColor) config.textColor = textColor;

    const textSecondaryColor = extractStringValue(script, "textSecondaryColor");
    if (textSecondaryColor) config.textSecondaryColor = textSecondaryColor;

    const bubbleBackgroundColor = extractStringValue(
      script,
      "bubbleBackgroundColor",
    );
    if (bubbleBackgroundColor)
      config.bubbleBackgroundColor = bubbleBackgroundColor;

    const bubbleTextColor = extractStringValue(script, "bubbleTextColor");
    if (bubbleTextColor) config.bubbleTextColor = bubbleTextColor;

    const userMessageBg = extractStringValue(script, "userMessageBg");
    if (userMessageBg) config.userMessageBg = userMessageBg;

    const botMessageBg = extractStringValue(script, "botMessageBg");
    if (botMessageBg) config.botMessageBg = botMessageBg;

    const userMessageTextColor = extractStringValue(
      script,
      "userMessageTextColor",
    );
    if (userMessageTextColor)
      config.userMessageTextColor = userMessageTextColor;

    const botMessageTextColor = extractStringValue(
      script,
      "botMessageTextColor",
    );
    if (botMessageTextColor) config.botMessageTextColor = botMessageTextColor;

    // Extract layout values
    const offsetX = extractStringValue(script, "offsetX");
    if (offsetX) config.offsetX = offsetX;

    const offsetY = extractStringValue(script, "offsetY");
    if (offsetY) config.offsetY = offsetY;

    // Extract branding values
    const showBranding = extractBooleanValue(script, "showBranding");
    if (showBranding !== undefined) config.showBranding = showBranding;

    const headerTitle = extractStringValue(script, "headerTitle");
    if (headerTitle) config.headerTitle = headerTitle;

    const headerSubtitle = extractStringValue(script, "headerSubtitle");
    if (headerSubtitle) config.headerSubtitle = headerSubtitle;

    const avatarUrl = extractStringValue(script, "avatarUrl");
    if (avatarUrl) config.avatarUrl = avatarUrl;

    const showAvatar = extractBooleanValue(script, "showAvatar");
    if (showAvatar !== undefined) config.showAvatar = showAvatar;

    // Check if we extracted at least the username
    if (!config.expertUsername) {
      return null;
    }

    return config;
  } catch {
    return null;
  }
}

export function WidgetPreview({ username }: WidgetPreviewProps) {
  const publicUrl = `/${username}`;
  const [savedConfig, setSavedConfig] = useState<SavedConfig | null>(null);
  const [hasCustomizations, setHasCustomizations] = useState(false);
  const [pastedScript, setPastedScript] = useState("");
  const [parsedScript, setParsedScript] = useState<SavedConfig | null>(null);
  const [parseError, setParseError] = useState(false);
  const [useCustomScript, setUseCustomScript] = useState(false);

  // Load saved config to show preview
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(WIDGET_CONFIG_STORAGE_KEY);
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          setSavedConfig(parsed);
          // Check if there are customizations (anything different from defaults)
          const hasCustom =
            parsed.primaryColor !== "#f59e0b" ||
            parsed.backgroundColor !== "#fff4eb" ||
            parsed.position !== "bottom-right";
          setHasCustomizations(hasCustom);
        } catch {
          // Ignore parse errors
        }
      }
    }
  }, []);

  // Parse pasted script when it changes
  useEffect(() => {
    if (pastedScript.trim()) {
      const parsed = parseScriptConfig(pastedScript);
      if (parsed) {
        setParsedScript(parsed);
        setParseError(false);
      } else {
        setParsedScript(null);
        setParseError(true);
      }
    } else {
      setParsedScript(null);
      setParseError(false);
    }
  }, [pastedScript]);

  // Handle preview with custom script
  const handlePreviewWithScript = () => {
    if (parsedScript) {
      // Save parsed config to localStorage so test page can use it
      localStorage.setItem(
        WIDGET_CONFIG_STORAGE_KEY,
        JSON.stringify(parsedScript),
      );
      setSavedConfig(parsedScript);
      setUseCustomScript(true);
      // Open test page
      window.open("/test-embed", "_blank");
    }
  };

  // Get the active config (either from pasted script or saved)
  const activeConfig =
    useCustomScript && parsedScript ? parsedScript : savedConfig;

  return (
    <div className="space-y-6">
      <Alert>
        <AlertDescription className="flex items-center gap-2">
          <Check className="size-4 shrink-0 text-green-600" />
          <span>
            Your customizations from the <strong>Customize tab</strong> are
            automatically saved and will be applied when you open the test page.
            You can also paste a custom script below to preview it.
          </span>
        </AlertDescription>
      </Alert>

      {/* Paste Script Section */}
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <Code2 className="size-4 text-indigo-600" />
          <h4 className="text-sm font-semibold text-slate-900">
            Paste Script to Preview
          </h4>
          <Badge variant="outline" className="text-xs">
            Optional
          </Badge>
        </div>
        <p className="mb-3 text-xs text-slate-500">
          Paste your widget embed script here to preview it. The configuration
          will be extracted and used for the preview.
        </p>
        <div className="space-y-3">
          <div>
            <Label htmlFor="pasteScript" className="sr-only">
              Paste Script
            </Label>
            <Textarea
              id="pasteScript"
              value={pastedScript}
              onChange={(e) => setPastedScript(e.target.value)}
              placeholder={`<script src="https://..."></script>
<script>
  window.MyClone({
    mode: "bubble",
    expertUsername: "your-username",
    widgetToken: "...",
    size: { width: "900px", height: "820px" },
    theme: { primaryColor: "#f59e0b" },
    // ... other options
  });
</script>`}
              className="min-h-[120px] font-mono text-xs"
            />
          </div>

          {parseError && pastedScript.trim() && (
            <div className="flex items-center gap-2 text-xs text-red-600">
              <AlertCircle className="size-3" />
              Could not parse the script. Make sure it contains
              &quot;expertUsername&quot; in a valid MyClone widget script.
            </div>
          )}

          {parsedScript && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3">
              <div className="mb-2 flex items-center gap-2">
                <Check className="size-4 text-green-600" />
                <span className="text-sm font-medium text-green-800">
                  Script parsed successfully
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
                {parsedScript.expertUsername && (
                  <div>
                    <span className="text-green-700">Username:</span>
                    <span className="ml-1 font-medium text-green-900">
                      {parsedScript.expertUsername}
                    </span>
                  </div>
                )}
                {parsedScript.primaryColor && (
                  <div className="flex items-center gap-1">
                    <span className="text-green-700">Primary:</span>
                    <div
                      className="size-3 rounded border border-green-300"
                      style={{ backgroundColor: parsedScript.primaryColor }}
                    />
                    <span className="font-mono text-green-900">
                      {parsedScript.primaryColor}
                    </span>
                  </div>
                )}
                {(parsedScript.width || parsedScript.height) && (
                  <div>
                    <span className="text-green-700">Size:</span>
                    <span className="ml-1 font-medium text-green-900">
                      {parsedScript.width || "900px"} ×{" "}
                      {parsedScript.height || "820px"}
                    </span>
                  </div>
                )}
                {parsedScript.position && (
                  <div>
                    <span className="text-green-700">Position:</span>
                    <span className="ml-1 font-medium text-green-900">
                      {parsedScript.position}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          <Button
            variant="default"
            className="w-full gap-2"
            onClick={handlePreviewWithScript}
            disabled={!parsedScript}
          >
            <Play className="size-4" />
            Preview Pasted Script
          </Button>
        </div>
      </Card>

      {/* Current Config Summary */}
      {activeConfig && (
        <Card className="bg-slate-50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Palette className="size-4 text-amber-600" />
              {useCustomScript
                ? "Pasted Script Configuration"
                : "Current Configuration"}
            </h4>
            {(hasCustomizations || useCustomScript) && (
              <Badge
                variant="secondary"
                className="bg-amber-100 text-amber-800"
              >
                {useCustomScript ? "From Script" : "Customized"}
              </Badge>
            )}
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            {activeConfig.expertUsername && (
              <div className="flex items-center gap-2">
                <span className="text-slate-600">Username:</span>
                <span className="font-medium text-slate-700">
                  {activeConfig.expertUsername}
                </span>
              </div>
            )}
            {activeConfig.primaryColor && (
              <div className="flex items-center gap-2">
                <span className="text-slate-600">Primary:</span>
                <div
                  className="size-4 rounded border border-slate-200"
                  style={{ backgroundColor: activeConfig.primaryColor }}
                />
                <span className="font-mono text-slate-700">
                  {activeConfig.primaryColor}
                </span>
              </div>
            )}
            {activeConfig.backgroundColor && (
              <div className="flex items-center gap-2">
                <span className="text-slate-600">Background:</span>
                <div
                  className="size-4 rounded border border-slate-200"
                  style={{ backgroundColor: activeConfig.backgroundColor }}
                />
                <span className="font-mono text-slate-700">
                  {activeConfig.backgroundColor}
                </span>
              </div>
            )}
            {activeConfig.position && (
              <div className="flex justify-between">
                <span className="text-slate-600">Position:</span>
                <span className="font-medium text-slate-700">
                  {activeConfig.position?.replace("-", " ")}
                </span>
              </div>
            )}
            {(activeConfig.width || activeConfig.height) && (
              <div className="flex justify-between">
                <span className="text-slate-600">Size:</span>
                <span className="font-medium text-slate-700">
                  {activeConfig.width || "900px"} ×{" "}
                  {activeConfig.height || "820px"}
                </span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-slate-600">Voice:</span>
              <span className="font-medium text-slate-700">
                {activeConfig.enableVoice !== false ? "Enabled" : "Disabled"}
              </span>
            </div>
          </div>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Test Page */}
        <Card className="p-6">
          <h3 className="mb-4 text-lg font-semibold text-slate-900">
            Test Page
          </h3>
          <p className="mb-4 text-sm text-slate-600">
            Open the dedicated test page to interact with your widget with your
            custom settings. All customizations from the Customize tab will be
            applied.
          </p>
          <Button
            variant="default"
            className="w-full gap-2"
            onClick={() => window.open("/test-embed", "_blank")}
          >
            <ExternalLink className="size-4" />
            Open Test Page
          </Button>
        </Card>

        {/* Public Profile */}
        <Card className="p-6">
          <h3 className="mb-4 text-lg font-semibold text-slate-900">
            Your Public Profile
          </h3>
          <p className="mb-4 text-sm text-slate-600">
            View your public profile page where users can chat with your AI
            clone directly.
          </p>
          <Button
            variant="outline"
            className="w-full gap-2"
            onClick={() => window.open(publicUrl, "_blank")}
          >
            <ExternalLink className="size-4" />
            View Public Profile
          </Button>
        </Card>
      </div>

      {/* Widget Features */}
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          Widget Features
        </h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <div className="font-medium text-slate-900">✅ Text Chat</div>
            <p className="text-sm text-slate-600">
              Real-time conversation with your AI clone
            </p>
          </div>

          <div className="space-y-2">
            <div className="font-medium text-slate-900">✅ Voice Chat</div>
            <p className="text-sm text-slate-600">
              Speak directly with your AI clone (optional)
            </p>
          </div>

          <div className="space-y-2">
            <div className="font-medium text-slate-900">✅ Email Capture</div>
            <p className="text-sm text-slate-600">
              Collect user emails for follow-up
            </p>
          </div>

          <div className="space-y-2">
            <div className="font-medium text-slate-900">
              ✅ Mobile Responsive
            </div>
            <p className="text-sm text-slate-600">
              Works perfectly on all devices
            </p>
          </div>

          <div className="space-y-2">
            <div className="font-medium text-slate-900">✅ Customizable</div>
            <p className="text-sm text-slate-600">Brand colors and messaging</p>
          </div>

          <div className="space-y-2">
            <div className="font-medium text-slate-900">
              ✅ Easy Integration
            </div>
            <p className="text-sm text-slate-600">
              Just copy and paste the code
            </p>
          </div>
        </div>
      </Card>

      {/* Integration Examples */}
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          Where to Use Your Widget
        </h3>
        <div className="space-y-3 text-sm">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-full bg-orange-100 px-2 py-1 text-xs font-medium text-amber-700">
              Personal
            </div>
            <span className="text-slate-700">
              Add to your personal website or blog
            </span>
          </div>
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-full bg-orange-100 px-2 py-1 text-xs font-medium text-amber-700">
              Portfolio
            </div>
            <span className="text-slate-700">
              Showcase your expertise on your portfolio
            </span>
          </div>
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-full bg-orange-100 px-2 py-1 text-xs font-medium text-amber-700">
              Business
            </div>
            <span className="text-slate-700">
              Provide 24/7 customer support on your business site
            </span>
          </div>
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-full bg-orange-100 px-2 py-1 text-xs font-medium text-amber-700">
              Landing Page
            </div>
            <span className="text-slate-700">
              Engage visitors on landing pages
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}
