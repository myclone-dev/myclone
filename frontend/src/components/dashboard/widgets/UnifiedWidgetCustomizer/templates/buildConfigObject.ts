import { WidgetConfig, DEFAULT_CONFIG, isChatbotModePosition } from "../types";

/**
 * Escape a string for safe embedding in JavaScript code.
 * Handles quotes, backslashes, newlines, and other special characters.
 */
export function escapeJsString(str: string, quote: string = '"'): string {
  if (!str) return str;

  return str
    .replace(/\\/g, "\\\\") // Escape backslashes first
    .replace(/\r/g, "\\r") // Carriage return
    .replace(/\n/g, "\\n") // Newline
    .replace(/\t/g, "\\t") // Tab
    .replace(new RegExp(quote, "g"), `\\${quote}`); // Escape the quote character
}

/**
 * Helper to wrap a string value with quotes and escape it.
 * Use this for single string values in templates.
 *
 * @example
 * `expertUsername: ${jsStr(username, quote)},`
 */
export const jsStr = (
  value: string | undefined,
  quote: string = '"',
): string => {
  if (!value) return `${quote}${quote}`;
  return `${quote}${escapeJsString(value, quote)}${quote}`;
};

/**
 * Converts a plain JavaScript object to an escaped JavaScript object literal string.
 * Automatically handles escaping strings, numbers, booleans, and nested objects.
 *
 * @param obj - The object to convert
 * @param quote - Quote character to use (" or ')
 * @param indentLevel - Current indentation level (for nested objects)
 * @returns Formatted JavaScript object string with proper escaping
 *
 * @example
 * const config = {
 *   mode: "bubble",
 *   expertUsername: username,
 *   widgetToken: token,
 *   enableVoice: true,
 *   count: 42
 * };
 * const code = `window.ConvoxAI({\n${buildJsObjectString(config, '"')}\n});`;
 */
export function buildJsObjectString(
  obj: Record<string, string | number | boolean | undefined | null | object>,
  quote: string = '"',
  indentLevel: number = 1,
): string {
  const indent = "  ".repeat(indentLevel);
  const entries: string[] = [];

  for (const [key, value] of Object.entries(obj)) {
    // Skip undefined/null values
    if (value === undefined || value === null) continue;

    let formattedValue: string;

    if (typeof value === "string") {
      // Escape and quote strings
      formattedValue = `${quote}${escapeJsString(value, quote)}${quote}`;
    } else if (typeof value === "boolean" || typeof value === "number") {
      // Booleans and numbers without quotes
      formattedValue = String(value);
    } else if (typeof value === "object" && !Array.isArray(value)) {
      // Nested objects (recursive)
      formattedValue = `{\n${buildJsObjectString(
        value as Record<
          string,
          string | number | boolean | undefined | null | object
        >,
        quote,
        indentLevel + 1,
      )}\n${indent}}`;
    } else {
      // Arrays or other types - convert to string
      formattedValue = JSON.stringify(value);
    }

    entries.push(`${indent}${key}: ${formattedValue}`);
  }

  return entries.join(",\n");
}

/**
 * Builds a customization config object string for embedding in templates.
 * Only includes options that differ from defaults.
 */
export function buildConfigObject(
  config: WidgetConfig,
  quote: string = '"',
  indentLevel: number = 1,
): string {
  const lines: string[] = [];
  const indent = "  ".repeat(indentLevel);
  const deepIndent = "  ".repeat(indentLevel + 2);

  // Size options (only if changed from defaults)
  const sizeOptions: string[] = [];
  if (config.width !== DEFAULT_CONFIG.width) {
    sizeOptions.push(
      `${deepIndent}width: ${quote}${escapeJsString(config.width, quote)}${quote}`,
    );
  }
  if (config.height !== DEFAULT_CONFIG.height) {
    sizeOptions.push(
      `${deepIndent}height: ${quote}${escapeJsString(config.height, quote)}${quote}`,
    );
  }
  if (config.bubbleSize !== DEFAULT_CONFIG.bubbleSize) {
    sizeOptions.push(
      `${deepIndent}bubbleSize: ${quote}${escapeJsString(config.bubbleSize, quote)}${quote}`,
    );
  }
  if (config.borderRadius !== DEFAULT_CONFIG.borderRadius) {
    sizeOptions.push(
      `${deepIndent}borderRadius: ${quote}${escapeJsString(config.borderRadius, quote)}${quote}`,
    );
  }
  // Chatbot size options (only include when modalPosition is set to a corner)
  const isChatbotMode = isChatbotModePosition(config.modalPosition);
  if (isChatbotMode) {
    if (config.chatbotWidth !== DEFAULT_CONFIG.chatbotWidth) {
      sizeOptions.push(
        `${deepIndent}chatbotWidth: ${quote}${config.chatbotWidth}${quote}`,
      );
    }
    if (config.chatbotHeight !== DEFAULT_CONFIG.chatbotHeight) {
      sizeOptions.push(
        `${deepIndent}chatbotHeight: ${quote}${config.chatbotHeight}${quote}`,
      );
    }
  }
  if (sizeOptions.length > 0) {
    lines.push(`${indent}size: {\n${sizeOptions.join(",\n")}\n${indent}},`);
  }

  // Theme options (only if changed from defaults)
  const themeOptions: string[] = [];
  if (config.primaryColor !== DEFAULT_CONFIG.primaryColor) {
    themeOptions.push(
      `${deepIndent}primaryColor: ${quote}${escapeJsString(config.primaryColor, quote)}${quote}`,
    );
  }
  if (config.backgroundColor !== DEFAULT_CONFIG.backgroundColor) {
    themeOptions.push(
      `${deepIndent}backgroundColor: ${quote}${escapeJsString(config.backgroundColor, quote)}${quote}`,
    );
  }
  if (
    config.headerBackground &&
    config.headerBackground !== DEFAULT_CONFIG.headerBackground
  ) {
    themeOptions.push(
      `${deepIndent}headerBackground: ${quote}${escapeJsString(config.headerBackground, quote)}${quote}`,
    );
  }
  if (config.textColor !== DEFAULT_CONFIG.textColor) {
    themeOptions.push(
      `${deepIndent}textColor: ${quote}${escapeJsString(config.textColor, quote)}${quote}`,
    );
  }
  if (config.textSecondaryColor !== DEFAULT_CONFIG.textSecondaryColor) {
    themeOptions.push(
      `${deepIndent}textSecondaryColor: ${quote}${escapeJsString(config.textSecondaryColor, quote)}${quote}`,
    );
  }
  if (
    config.bubbleBackgroundColor &&
    config.bubbleBackgroundColor !== DEFAULT_CONFIG.bubbleBackgroundColor
  ) {
    themeOptions.push(
      `${deepIndent}bubbleBackgroundColor: ${quote}${escapeJsString(config.bubbleBackgroundColor, quote)}${quote}`,
    );
  }
  if (config.bubbleTextColor !== DEFAULT_CONFIG.bubbleTextColor) {
    themeOptions.push(
      `${deepIndent}bubbleTextColor: ${quote}${escapeJsString(config.bubbleTextColor, quote)}${quote}`,
    );
  }
  if (
    config.userMessageBg &&
    config.userMessageBg !== DEFAULT_CONFIG.userMessageBg
  ) {
    themeOptions.push(
      `${deepIndent}userMessageBg: ${quote}${escapeJsString(config.userMessageBg, quote)}${quote}`,
    );
  }
  if (config.botMessageBg !== DEFAULT_CONFIG.botMessageBg) {
    themeOptions.push(
      `${deepIndent}botMessageBg: ${quote}${escapeJsString(config.botMessageBg, quote)}${quote}`,
    );
  }
  if (config.userMessageTextColor !== DEFAULT_CONFIG.userMessageTextColor) {
    themeOptions.push(
      `${deepIndent}userMessageTextColor: ${quote}${escapeJsString(config.userMessageTextColor, quote)}${quote}`,
    );
  }
  if (config.botMessageTextColor !== DEFAULT_CONFIG.botMessageTextColor) {
    themeOptions.push(
      `${deepIndent}botMessageTextColor: ${quote}${escapeJsString(config.botMessageTextColor, quote)}${quote}`,
    );
  }
  if (themeOptions.length > 0) {
    lines.push(`${indent}theme: {\n${themeOptions.join(",\n")}\n${indent}},`);
  }

  // Layout options (only if changed from defaults)
  const layoutOptions: string[] = [];
  if (config.offsetX !== DEFAULT_CONFIG.offsetX) {
    layoutOptions.push(
      `${deepIndent}offsetX: ${quote}${escapeJsString(config.offsetX, quote)}${quote}`,
    );
  }
  if (config.offsetY !== DEFAULT_CONFIG.offsetY) {
    layoutOptions.push(
      `${deepIndent}offsetY: ${quote}${escapeJsString(config.offsetY, quote)}${quote}`,
    );
  }
  // Always include modalPosition when in chatbot mode (even if it's the default "bottom-right")
  // This is necessary because the SDK's default is undefined (centered mode)
  // Without this, the iframe won't receive modalPosition and chatbot mode won't activate
  if (isChatbotMode) {
    layoutOptions.push(
      `${deepIndent}modalPosition: ${quote}${config.modalPosition}${quote}`,
    );
  }
  // Always include chatbotStyle when in chatbot mode (positioned modal)
  // This ensures the style is explicitly set even when it's the default "guide"
  if (isChatbotMode && config.chatbotStyle) {
    layoutOptions.push(
      `${deepIndent}chatbotStyle: ${quote}${config.chatbotStyle}${quote}`,
    );
  }
  if (layoutOptions.length > 0) {
    lines.push(`${indent}layout: {\n${layoutOptions.join(",\n")}\n${indent}},`);
  }

  // Branding options (only if changed from defaults)
  const brandingOptions: string[] = [];
  if (config.showBranding !== DEFAULT_CONFIG.showBranding) {
    brandingOptions.push(`${deepIndent}showBranding: ${config.showBranding}`);
  }
  if (config.headerTitle) {
    brandingOptions.push(
      `${deepIndent}headerTitle: ${quote}${escapeJsString(config.headerTitle, quote)}${quote}`,
    );
  }
  if (config.headerSubtitle) {
    brandingOptions.push(
      `${deepIndent}headerSubtitle: ${quote}${escapeJsString(config.headerSubtitle, quote)}${quote}`,
    );
  }
  if (config.avatarUrl) {
    brandingOptions.push(
      `${deepIndent}avatarUrl: ${quote}${escapeJsString(config.avatarUrl, quote)}${quote}`,
    );
  }
  if (config.bubbleIcon) {
    brandingOptions.push(
      `${deepIndent}bubbleIcon: ${quote}${escapeJsString(config.bubbleIcon, quote)}${quote}`,
    );
  }
  if (config.showAvatar !== DEFAULT_CONFIG.showAvatar) {
    brandingOptions.push(`${deepIndent}showAvatar: ${config.showAvatar}`);
  }
  if (config.simpleBubble) {
    brandingOptions.push(`${deepIndent}simpleBubble: true`);
  }
  // NOTE: welcomeMessage is now a top-level property in templates, not in branding
  if (brandingOptions.length > 0) {
    lines.push(
      `${indent}branding: {\n${brandingOptions.join(",\n")}\n${indent}},`,
    );
  }

  return lines.length > 0 ? ",\n" + lines.join("\n") : "";
}
