import { env } from "@/env";

const GOOGLE_OAUTH_ENDPOINT = "/auth/google";

const getGoogleOAuthUrl = (params?: Record<string, string>): string => {
  const endpoint = GOOGLE_OAUTH_ENDPOINT;
  const query = params
    ? new URLSearchParams(params).toString()
    : "";

  return query
    ? `${env.NEXT_PUBLIC_API_URL}${endpoint}?${query}`
    : `${env.NEXT_PUBLIC_API_URL}${endpoint}`;
};

/**
 * Redirect user to Google OAuth flow.
 * Safe to call from SSR - returns early if not in browser.
 */
export const redirectToGoogleAuth = (timezone?: string): void => {
  // Early return for SSR safety - avoid generating URL on server
  if (typeof window === "undefined") return;

  const authUrl = getGoogleOAuthUrl(timezone ? { timezone } : undefined);
  window.location.href = authUrl;
};
