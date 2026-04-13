/**
 * ConvoxAI Embed SDK
 * Global window API for the widget
 */

import { ConvoxAILoader } from "./loader";
import type { ConvoxAIConfig, ConvoxAIWidget } from "./types";

/**
 * Global ConvoxAI function
 * Creates a new widget instance or returns existing one
 */
function ConvoxAI(config: ConvoxAIConfig): ConvoxAIWidget {
  if (!config || !config.expertUsername) {
    throw new Error("ConvoxAI: Configuration with expertUsername is required");
  }

  // Generate unique key based on mode:
  // - Bubble mode: one per expertUsername (only one bubble allowed per expert)
  // - Inline mode: one per container (allow multiple inline widgets)
  const instanceKey =
    config.mode === "inline" && config.container
      ? `inline:${config.container}`
      : `bubble:${config.expertUsername}`;

  // Check if instance already exists
  const existingInstance = ConvoxAI.instances.get(instanceKey);
  if (existingInstance) {
    console.warn(
      `ConvoxAI: Widget already initialized with key "${instanceKey}". Returning existing instance.`,
    );
    return existingInstance;
  }

  // Create new instance
  const instance = new ConvoxAILoader(config);

  // Store instance
  ConvoxAI.instances.set(instanceKey, instance);

  return instance;
}

/**
 * Store for widget instances
 * Key format: "bubble:{username}" or "inline:{container}"
 */
ConvoxAI.instances = new Map<string, ConvoxAIWidget>();

/**
 * Attach to window object
 */
if (typeof window !== "undefined") {
  window.ConvoxAI = ConvoxAI;
}

/**
 * Export for module usage
 */
export { ConvoxAI };
export type { ConvoxAIConfig, ConvoxAIWidget } from "./types";
