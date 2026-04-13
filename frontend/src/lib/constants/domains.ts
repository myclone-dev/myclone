/**
 * Platform domains - these are NOT custom domains
 * Used by middleware and OnboardingGuard to detect custom domains
 *
 * A custom domain is any domain NOT in this list.
 * Custom domains are white-labeled domains that users configure
 * to point to their expert profile (e.g., chat.example.com → /username)
 *
 * Configure via NEXT_PUBLIC_PLATFORM_DOMAINS env var (comma-separated).
 */

function loadPlatformDomains(): string[] {
  const defaults = ["localhost", "127.0.0.1"];
  const extra = process.env.NEXT_PUBLIC_PLATFORM_DOMAINS || "";
  if (extra) {
    for (const domain of extra.split(",")) {
      const trimmed = domain.trim();
      if (trimmed) defaults.push(trimmed);
    }
  }
  return defaults;
}

export const PLATFORM_DOMAINS = loadPlatformDomains();

export type PlatformDomain = string;

/**
 * Check if a hostname is a platform domain (not a custom domain)
 * @param hostname - The hostname to check (e.g., "app.myclone.is" or "example.com")
 * @returns true if it's a platform domain, false if it's a custom domain
 */
export function isPlatformDomain(hostname: string): boolean {
  const host = hostname.split(":")[0].toLowerCase();
  return PLATFORM_DOMAINS.some(
    (domain) => host === domain || host.endsWith(`.${domain}`),
  );
}

/**
 * Check if a hostname is a custom domain
 * @param hostname - The hostname to check
 * @returns true if it's a custom domain, false if it's a platform domain
 */
export function isCustomDomain(hostname: string): boolean {
  return !isPlatformDomain(hostname);
}
