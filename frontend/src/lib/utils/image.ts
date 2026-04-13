/**
 * Image utility functions
 */

/**
 * Get proxied avatar URL with smart fallback strategy:
 * 1. S3 URLs (already in our storage) - return as-is, no proxy needed
 * 2. External URLs (LinkedIn, etc.) - proxy through /api/image-proxy to bypass hotlink protection
 * 3. Local paths - return as-is
 */
export function getProxiedAvatarUrl(
  avatarUrl: string | null | undefined,
): string | undefined {
  if (!avatarUrl) return undefined;

  // Local paths - return as-is
  if (avatarUrl.startsWith("/")) {
    return avatarUrl;
  }

  // S3 URLs - return as-is (no proxy needed)
  // Handles both standard and regional S3 URLs:
  // - https://bucket.s3.amazonaws.com/key
  // - https://bucket.s3.region.amazonaws.com/key
  // - https://s3.region.amazonaws.com/bucket/key
  if (avatarUrl.includes("s3.amazonaws.com") || avatarUrl.includes("s3-")) {
    return avatarUrl;
  }

  // External URLs (LinkedIn, etc.) - proxy to bypass hotlink protection
  if (avatarUrl.startsWith("http://") || avatarUrl.startsWith("https://")) {
    return `/api/image-proxy?url=${encodeURIComponent(avatarUrl)}`;
  }

  // Fallback - return as-is
  return avatarUrl;
}
