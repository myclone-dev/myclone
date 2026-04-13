/**
 * Simple utility to set hasOnboarded cookie via API
 * Keeps it simple - just call the API endpoint
 */

import * as Sentry from "@sentry/nextjs";

/**
 * Set hasOnboarded cookie via API
 * Call this after successful authentication
 */
export async function setHasOnboardedCookie(): Promise<void> {
  if (typeof window === "undefined") return;

  try {
    const response = await fetch("/api/cookies/set-onboarded", {
      method: "POST",
      credentials: "include",
    });

    if (!response.ok) {
      throw new Error("Failed to set cookie");
    }

    console.log("✅ hasOnboarded cookie set successfully");
  } catch (error) {
    Sentry.captureException(error, {
      tags: { operation: "cookie_sync" },
      contexts: {
        cookie: {
          action: "set_has_onboarded",
          error: error instanceof Error ? error.message : "Unknown error",
        },
      },
    });
    console.error("❌ Failed to set hasOnboarded cookie:", error);
  }
}
