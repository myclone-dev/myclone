"use client";

import { useState, useCallback } from "react";
import { Framework, WidgetMode, WidgetConfig } from "../types";
import { generateEmbedCode } from "../templates";
import { env } from "@/env";
import { trackUserAction } from "@/lib/monitoring/sentry";

interface UseCodeGeneratorOptions {
  username: string;
  config: WidgetConfig;
}

export function useCodeGenerator({
  username,
  config,
}: UseCodeGeneratorOptions) {
  const [copied, setCopied] = useState(false);
  const [selectedFramework, setSelectedFramework] = useState<Framework>("html");
  const [widgetMode, setWidgetMode] = useState<WidgetMode>("bubble");

  const baseUrl = env.NEXT_PUBLIC_APP_URL;

  const getCode = useCallback(() => {
    return generateEmbedCode({
      framework: selectedFramework,
      mode: widgetMode,
      baseUrl,
      username,
      config,
    });
  }, [selectedFramework, widgetMode, baseUrl, username, config]);

  const handleCopy = useCallback(async () => {
    const code = getCode();
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);

      trackUserAction("widget_code_copied", {
        framework: selectedFramework,
        mode: widgetMode,
      });

      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error("Failed to copy to clipboard:", error);
      trackUserAction("widget_code_copy_failed", {
        framework: selectedFramework,
        mode: widgetMode,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }, [getCode, selectedFramework, widgetMode]);

  return {
    copied,
    selectedFramework,
    setSelectedFramework,
    widgetMode,
    setWidgetMode,
    getCode,
    handleCopy,
  };
}
