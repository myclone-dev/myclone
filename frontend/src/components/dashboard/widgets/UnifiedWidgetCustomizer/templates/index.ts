import { Framework, WidgetMode, WidgetConfig } from "../types";
import { getBubbleTemplate } from "./bubbleTemplates";
import { getInlineTemplate } from "./inlineTemplates";
import { getFullpageTemplate } from "./fullpageTemplates";

export { buildConfigObject } from "./buildConfigObject";

interface GenerateEmbedCodeParams {
  framework: Framework;
  mode: WidgetMode;
  baseUrl: string;
  username: string;
  config: WidgetConfig;
}

/**
 * Generates embed code for the widget based on framework and mode
 */
export function generateEmbedCode({
  framework,
  mode,
  baseUrl,
  username,
  config,
}: GenerateEmbedCodeParams): string {
  const templateParams = { baseUrl, username, config };

  switch (mode) {
    case "inline":
      return getInlineTemplate(framework, templateParams);
    case "fullpage":
      return getFullpageTemplate(framework, templateParams);
    case "bubble":
    default:
      return getBubbleTemplate(framework, templateParams);
  }
}
