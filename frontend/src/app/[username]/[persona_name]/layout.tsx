"use client";

import { I18nProvider } from "@/i18n/I18nProvider";

/**
 * Persona Page Layout
 * Wraps persona pages with i18n support for internationalization.
 * Language is determined by persona settings (set by persona owner).
 * Defaults to English if not set or set to "auto".
 */
export default function PersonaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <I18nProvider>{children}</I18nProvider>;
}
