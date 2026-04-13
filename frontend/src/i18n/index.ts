/**
 * i18n Configuration
 * Works for both Next.js app and Vite widget
 */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";

// Import translation files
import en from "./locales/en.json";
import es from "./locales/es.json";
import fr from "./locales/fr.json";
import ar from "./locales/ar.json";
import de from "./locales/de.json";
import it from "./locales/it.json";
import pt from "./locales/pt.json";
import nl from "./locales/nl.json";
import pl from "./locales/pl.json";
import hi from "./locales/hi.json";
import ja from "./locales/ja.json";
import ko from "./locales/ko.json";
import el from "./locales/el.json";
import cs from "./locales/cs.json";
import sv from "./locales/sv.json";

// Supported languages
export const supportedLanguages = [
  "en",
  "es",
  "fr",
  "ar",
  "de",
  "it",
  "pt",
  "nl",
  "pl",
  "hi",
  "ja",
  "ko",
  "el",
  "cs",
  "sv",
] as const;
export type SupportedLanguage = (typeof supportedLanguages)[number];

// Language metadata for UI display
export const languageNames: Record<SupportedLanguage, string> = {
  en: "English",
  es: "Español",
  fr: "Français",
  ar: "العربية",
  de: "Deutsch",
  it: "Italiano",
  pt: "Português",
  nl: "Nederlands",
  pl: "Polski",
  hi: "हिन्दी",
  ja: "日本語",
  ko: "한국어",
  el: "Ελληνικά",
  cs: "Čeština",
  sv: "Svenska",
};

// RTL languages
export const rtlLanguages: SupportedLanguage[] = ["ar"];

export const isRtlLanguage = (lang: string): boolean => {
  return rtlLanguages.includes(lang as SupportedLanguage);
};

// Resources
const resources = {
  en: { translation: en },
  es: { translation: es },
  fr: { translation: fr },
  ar: { translation: ar },
  de: { translation: de },
  it: { translation: it },
  pt: { translation: pt },
  nl: { translation: nl },
  pl: { translation: pl },
  hi: { translation: hi },
  ja: { translation: ja },
  ko: { translation: ko },
  el: { translation: el },
  cs: { translation: cs },
  sv: { translation: sv },
};

// Initialize i18n only once
let initialized = false;

/**
 * Initialize i18n with the specified language.
 * Language priority:
 * 1. Explicit `defaultLanguage` param (from persona settings)
 * 2. Fallback to English ("en")
 *
 * Note: Browser language detection is intentionally DISABLED.
 * Language is determined by persona settings only.
 *
 * @param defaultLanguage - Language code from persona settings. "auto" or undefined defaults to "en"
 */
export const initI18n = (defaultLanguage?: string) => {
  // Determine the language to use
  // "auto" or undefined means default to English
  const languageToUse =
    defaultLanguage && defaultLanguage !== "auto" ? defaultLanguage : "en";

  if (initialized) {
    // If already initialized but language changed, update it
    if (i18n.language !== languageToUse) {
      i18n.changeLanguage(languageToUse);
    }
    return i18n;
  }

  i18n.use(initReactI18next).init({
    resources,
    fallbackLng: "en",
    lng: languageToUse, // Use explicit language, defaulting to English
    debug: process.env.NODE_ENV === "development",

    interpolation: {
      escapeValue: false, // React already escapes
    },

    // No language detection - language is determined by persona settings only
    // This prevents browser language from overriding the intended language
  });

  initialized = true;
  return i18n;
};

// Export i18n instance
export default i18n;

// Re-export useTranslation for convenience
export { useTranslation } from "react-i18next";
