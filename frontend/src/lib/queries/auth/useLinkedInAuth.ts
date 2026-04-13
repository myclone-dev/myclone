import { env } from "@/env";

const LINKEDIN_OAUTH_ENDPOINT = "/auth/linkedin";

const getLinkedInOAuthUrl = (params?: Record<string, string>): string => {
  const endpoint = LINKEDIN_OAUTH_ENDPOINT;
  const query = params
    ? new URLSearchParams(params).toString()
    : "";

  return query
    ? `${env.NEXT_PUBLIC_API_URL}${endpoint}?${query}`
    : `${env.NEXT_PUBLIC_API_URL}${endpoint}`;
};

/**
 * Redirect user to LinkedIn OAuth flow.
 * Safe to call from SSR - returns early if not in browser.
 */
export const redirectToLinkedInAuth = (timezone?: string): void => {
  // Early return for SSR safety - avoid generating URL on server
  if (typeof window === "undefined") return;

  const authUrl = getLinkedInOAuthUrl(timezone ? { timezone } : undefined);
  window.location.href = authUrl;
};
