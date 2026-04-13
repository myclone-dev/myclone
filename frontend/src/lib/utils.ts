import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Decodes HTML entities in a string to their corresponding characters.
 * Handles common entities like:
 * - &#x27; → ' (apostrophe)
 * - &apos; → '
 * - &quot; → "
 * - &amp; → &
 * - &lt; → <
 * - &gt; → >
 * - &#39; → '
 * - And all other HTML numeric and named entities
 *
 * @param text - The text containing HTML entities
 * @returns The decoded text with actual characters
 */
/**
 * Extract up to 2 initials from a name (e.g. "Jane Doe" → "JD").
 * Falls back to "?" if name is empty.
 */
export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2)
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return (parts[0]?.[0] || "?").toUpperCase();
}

export function decodeHtmlEntities(text: string): string {
  if (typeof window === "undefined") {
    // Server-side: Use basic regex replacements
    const entities: Record<string, string> = {
      "&amp;": "&",
      "&lt;": "<",
      "&gt;": ">",
      "&quot;": '"',
      "&apos;": "'",
      "&#39;": "'",
      "&#x27;": "'",
      "&#x2F;": "/",
      "&#x60;": "`",
      "&#x3D;": "=",
    };

    return text.replace(
      /&(?:amp|lt|gt|quot|apos|#39|#x27|#x2F|#x60|#x3D);/gi,
      (match) => entities[match] || match,
    );
  }

  // Client-side: Use browser's built-in decoder (most reliable)
  const textarea = document.createElement("textarea");
  textarea.innerHTML = text;
  return textarea.value;
}
