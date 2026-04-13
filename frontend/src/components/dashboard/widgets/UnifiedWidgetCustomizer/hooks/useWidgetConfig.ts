"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { toast } from "sonner";
import { WidgetConfig, DEFAULT_CONFIG, EffectiveColors } from "../types";
import { trackUserAction } from "@/lib/monitoring/sentry";
import {
  useWidgetConfigQuery,
  useUpdateWidgetConfig,
  useDeleteWidgetConfig,
  type WidgetConfigData,
} from "@/lib/queries/users";

// LocalStorage key for persisting widget config (as backup/cache)
const WIDGET_CONFIG_STORAGE_KEY = "myclone_widget_config";

// Debounce delay for saving to server (ms)
const SAVE_DEBOUNCE_MS = 1500;

interface UseWidgetConfigOptions {
  username: string;
  widgetToken?: string;
}

/**
 * Convert frontend WidgetConfig to API WidgetConfigData format.
 *
 * Currently the types are compatible, but this function provides a clear
 * boundary for any future transformations needed between frontend and API formats.
 *
 * @param config - The frontend widget configuration
 * @returns The API-compatible widget configuration data
 */
function toApiConfig(config: WidgetConfig): WidgetConfigData {
  return { ...config };
}

/**
 * Convert API WidgetConfigData to frontend WidgetConfig format.
 *
 * Merges the API config with DEFAULT_CONFIG to ensure all required fields
 * are present, even if the API returns a partial config.
 *
 * @param apiConfig - The configuration data from the API (may be null)
 * @returns The frontend widget configuration, or null if input is null
 */
function fromApiConfig(
  apiConfig: WidgetConfigData | null,
): WidgetConfig | null {
  if (!apiConfig) return null;
  return { ...DEFAULT_CONFIG, ...apiConfig } as WidgetConfig;
}

export function useWidgetConfig({
  username,
  widgetToken,
}: UseWidgetConfigOptions) {
  const [config, setConfigState] = useState<WidgetConfig>(DEFAULT_CONFIG);
  const [isInitialized, setIsInitialized] = useState(false);

  // Server sync hooks
  const {
    data: serverConfig,
    isLoading: isLoadingFromServer,
    isError: isServerError,
  } = useWidgetConfigQuery();
  const { mutate: saveToServer, isPending: isSaving } = useUpdateWidgetConfig();
  const { mutate: deleteFromServer } = useDeleteWidgetConfig();

  // Debounce timer ref
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track pending config for flushing on unmount
  const pendingConfigRef = useRef<WidgetConfig | null>(null);

  // Track if we've already loaded from server to avoid re-initializing
  const hasLoadedFromServerRef = useRef(false);

  // Track if we've already loaded from localStorage to prevent race condition
  const hasLoadedFromLocalStorageRef = useRef(false);

  // Load config: prioritize server, fallback to localStorage
  useEffect(() => {
    // Skip if already initialized or still loading
    if (isInitialized || isLoadingFromServer) return;

    // If server config is available, use it
    if (serverConfig?.config && !hasLoadedFromServerRef.current) {
      hasLoadedFromServerRef.current = true;
      const parsedConfig = fromApiConfig(serverConfig.config);
      if (parsedConfig) {
        setConfigState(parsedConfig);
        // Also save to localStorage as cache
        if (typeof window !== "undefined") {
          localStorage.setItem(
            WIDGET_CONFIG_STORAGE_KEY,
            JSON.stringify(parsedConfig),
          );
        }
        setIsInitialized(true);
        return;
      }
    }

    // Fallback to localStorage if server has no config (and hasn't already loaded)
    if (
      !isLoadingFromServer &&
      !serverConfig?.config &&
      !hasLoadedFromLocalStorageRef.current
    ) {
      hasLoadedFromLocalStorageRef.current = true;
      if (typeof window !== "undefined") {
        const savedConfig = localStorage.getItem(WIDGET_CONFIG_STORAGE_KEY);
        if (savedConfig) {
          try {
            const parsed = JSON.parse(savedConfig);
            setConfigState({ ...DEFAULT_CONFIG, ...parsed });
          } catch (error) {
            console.error("Failed to parse saved widget config:", error);
            trackUserAction("widget_config_load_error", {
              error: error instanceof Error ? error.message : "Parse error",
            });
          }
        }
      }
      setIsInitialized(true);
    }
  }, [serverConfig, isLoadingFromServer, isInitialized]);

  // Handle server error - fall back to localStorage immediately
  useEffect(() => {
    if (
      isServerError &&
      !isInitialized &&
      !hasLoadedFromLocalStorageRef.current
    ) {
      hasLoadedFromLocalStorageRef.current = true;
      if (typeof window !== "undefined") {
        const savedConfig = localStorage.getItem(WIDGET_CONFIG_STORAGE_KEY);
        if (savedConfig) {
          try {
            const parsed = JSON.parse(savedConfig);
            setConfigState({ ...DEFAULT_CONFIG, ...parsed });
          } catch {
            // If parse fails, just use defaults
          }
        }
      }
      setIsInitialized(true);
    }
  }, [isServerError, isInitialized]);

  // Debounced save to server
  const saveConfigToServer = useCallback(
    (newConfig: WidgetConfig) => {
      // Track pending config for potential flush on unmount
      pendingConfigRef.current = newConfig;

      // Clear any pending save
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }

      // Debounce the save
      saveTimerRef.current = setTimeout(() => {
        const apiConfig = toApiConfig(newConfig);
        saveToServer(apiConfig, {
          onSuccess: () => {
            pendingConfigRef.current = null;
          },
          onError: (error) => {
            console.error("Failed to save widget config to server:", error);
            toast.error(
              "Failed to save widget settings. Changes saved locally.",
            );
            // Config is still saved in localStorage, so user won't lose their changes
          },
        });
      }, SAVE_DEBOUNCE_MS);
    },
    [saveToServer],
  );

  // Wrapper for setConfig that also saves to localStorage and server
  const setConfig = useCallback(
    (newConfig: WidgetConfig) => {
      setConfigState(newConfig);

      // Save to localStorage immediately (as backup)
      if (typeof window !== "undefined") {
        const configWithMeta = {
          ...newConfig,
          expertUsername: username,
          widgetToken: widgetToken || "",
        };
        localStorage.setItem(
          WIDGET_CONFIG_STORAGE_KEY,
          JSON.stringify(configWithMeta),
        );
      }

      // Debounced save to server
      saveConfigToServer(newConfig);
    },
    [username, widgetToken, saveConfigToServer],
  );

  // Reset to defaults - also clears server config
  const resetToDefaults = useCallback(() => {
    setConfigState(DEFAULT_CONFIG);
    pendingConfigRef.current = null;

    // Clear localStorage
    if (typeof window !== "undefined") {
      localStorage.removeItem(WIDGET_CONFIG_STORAGE_KEY);
    }

    // Delete from server
    deleteFromServer(undefined, {
      onError: (error) => {
        console.error("Failed to delete widget config from server:", error);
        toast.error("Failed to reset widget settings on server.");
      },
    });

    trackUserAction("widget_config_reset");
  }, [deleteFromServer]);

  // Cleanup: flush pending saves on unmount
  useEffect(() => {
    return () => {
      // Clear the debounce timer
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }

      // If there's a pending config, save it immediately
      if (pendingConfigRef.current) {
        const apiConfig = toApiConfig(pendingConfigRef.current);
        // Use fire-and-forget save (can't await in cleanup)
        saveToServer(apiConfig, {
          onError: () => {
            // Silent fail - localStorage has the backup
          },
        });
      }
    };
  }, [saveToServer]);

  // Memoized effective colors (fallback to primary when empty)
  const effectiveColors = useMemo<EffectiveColors>(
    () => ({
      primary: config.primaryColor,
      background: config.backgroundColor,
      headerBg: config.headerBackground || "rgba(255, 255, 255, 0.8)",
      text: config.textColor,
      textSecondary: config.textSecondaryColor,
      bubbleBg: config.bubbleBackgroundColor || config.primaryColor,
      bubbleText: config.bubbleTextColor,
      userMsgBg: config.userMessageBg || config.primaryColor,
      botMsgBg: config.botMessageBg,
      userMsgText: config.userMessageTextColor,
      botMsgText: config.botMessageTextColor,
    }),
    [
      config.primaryColor,
      config.backgroundColor,
      config.headerBackground,
      config.textColor,
      config.textSecondaryColor,
      config.bubbleBackgroundColor,
      config.bubbleTextColor,
      config.userMessageBg,
      config.botMessageBg,
      config.userMessageTextColor,
      config.botMessageTextColor,
    ],
  );

  return {
    config,
    setConfig,
    resetToDefaults,
    effectiveColors,
    // Expose loading/saving states for UI feedback
    isLoading: isLoadingFromServer && !isInitialized,
    isSaving,
  };
}
