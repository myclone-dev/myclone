import posthog from "posthog-js";

interface PostHogUserProperties {
  id: string;
  email: string;
  name: string;
  username?: string;
  account_type?: string;
}

/**
 * Identify user in PostHog for session replay and analytics
 * Call this when user logs in or when app loads with authenticated user
 *
 * @param user - User properties to identify
 */
export function identifyUser(user: PostHogUserProperties): void {
  if (typeof window === "undefined") return;

  try {
    // Check if PostHog is initialized
    if (!posthog.__loaded) {
      console.warn("PostHog not initialized, skipping identify");
      return;
    }

    // Only identify if not already identified with this user
    const currentDistinctId = posthog.get_distinct_id();
    if (currentDistinctId === user.id && posthog._isIdentified()) {
      return;
    }

    posthog.identify(user.id, {
      email: user.email,
      name: user.name,
      username: user.username,
      account_type: user.account_type,
    });
  } catch (error) {
    console.error("Failed to identify user in PostHog:", error);
  }
}

/**
 * Reset PostHog user identity on logout
 * This unlinks future events from the current user
 */
export function resetUserIdentity(): void {
  if (typeof window === "undefined") return;

  try {
    if (!posthog.__loaded) {
      return;
    }

    posthog.reset();
  } catch (error) {
    console.error("Failed to reset PostHog identity:", error);
  }
}

/**
 * Get the current session replay URL
 * Useful for linking to specific moments in support tickets
 *
 * @param withTimestamp - Include timestamp in URL (defaults to true)
 * @param timestampLookBack - Seconds to look back (defaults to 30)
 */
export function getSessionReplayUrl(
  withTimestamp = true,
  timestampLookBack = 30,
): string | null {
  if (typeof window === "undefined") return null;

  try {
    if (!posthog.__loaded) {
      return null;
    }

    return posthog.get_session_replay_url({
      withTimestamp,
      timestampLookBack,
    });
  } catch (error) {
    console.error("Failed to get session replay URL:", error);
    return null;
  }
}
