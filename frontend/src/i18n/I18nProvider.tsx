"use client";

/**
 * I18nProvider Component
 * Provides i18n context to React components.
 * Works in both Next.js and Vite environments.
 */

import { useEffect, useRef, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import i18n, { initI18n, isRtlLanguage } from "./index";

interface I18nProviderProps {
  children: ReactNode;
  /** Override the detected language */
  locale?: string;
}

export function I18nProvider({ children, locale }: I18nProviderProps) {
  // Initialize i18n synchronously BEFORE first render
  // This ensures translations are available when children render
  // Using null pattern as required by react-hooks/refs ESLint rule
  const isInitialized = useRef<true | null>(null);
  if (isInitialized.current == null) {
    initI18n(locale);
    isInitialized.current = true;
  }

  useEffect(() => {
    // Handle locale changes after initial render
    if (locale && i18n.language !== locale && locale !== "auto") {
      i18n.changeLanguage(locale);
    }

    // Update document direction for RTL languages
    const updateDirection = () => {
      const currentLang = i18n.language;
      document.documentElement.dir = isRtlLanguage(currentLang) ? "rtl" : "ltr";
      document.documentElement.lang = currentLang;
    };

    updateDirection();

    // Listen for language changes
    i18n.on("languageChanged", updateDirection);

    return () => {
      i18n.off("languageChanged", updateDirection);
    };
  }, [locale]);

  // Always render children - i18n loads translations synchronously from bundled JSON
  // Returning null causes hydration mismatches with Next.js
  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>;
}

/**
 * Hook to change the current language
 */
export function useChangeLanguage() {
  const changeLanguage = (lang: string) => {
    i18n.changeLanguage(lang);
  };

  return { changeLanguage, currentLanguage: i18n.language };
}
