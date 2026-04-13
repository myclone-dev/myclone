/**
 * Expert onboarding and LinkedIn search type definitions
 */

// LinkedIn Profile Types
export interface LinkedInProfile {
  id: string;
  name: string;
  headline: string;
  profileUrl: string;
  avatarUrl: string;
  company?: string;
  location?: string;
}

// Actual API response structure from /users/linkedin/search
export interface LinkedInSearchResult {
  name: string;
  title: string;
  company: string | null;
  location: string;
  linkedin_url: string;
  profile_picture_url: string | null;
  similarity_score: number;
}

// LinkedIn Search Request/Response
export interface LinkedInSearchRequest {
  name: string;
  current_company?: string;
  role?: string;
  location?: string;
  skills?: string[];
  previous_companies?: string[];
  industry?: string;
  linkedin_hint?: string;
}

export interface LinkedInSearchResponse {
  success: boolean;
  results: LinkedInSearchResult[];
  total_results: number;
}

// Legacy types (kept for backward compatibility)
export interface LinkedInCrustDataProfile {
  name: string;
  linkedin_profile_url?: string;
  linkedin_flagship_url: string;
  location: string;
  headline: string;
  profile_picture_url?: string;
  last_updated: string;
  enriched_realtime: boolean;
  query_linkedin_profile_urn_or_slug?: string[];
}

export interface LinkedInSearchProfileResult {
  linkedin_url: string;
  profile: LinkedInCrustDataProfile;
  search_score: number;
  matched_on: string[];
}

// Expert Onboarding Submission
export interface ExpertOnboardingSubmitRequest {
  username: string;
  linkedinUrl?: string;
  websiteUrl?: string[] | null;
  twitterUsername?: string | null;
  email?: string | null;
  userId?: string;
}

export interface ExpertOnboardingSubmitResponse {
  success: boolean;
  message: string;
  user_id: string;
  username: string;
  persona_id: string;
  total_jobs: number;
  jobs_queued: {
    linkedin?: string;
    twitter?: string;
    website?: string;
  };
}

// Legacy types (kept for backward compatibility)
export interface ExpertOnboardingUser {
  id: string;
  email: string;
  firstname: string;
  lastname: string;
  fullname: string;
  linkedin_url: string;
  username: string;
  website_url: string | null;
  role: string;
  onboarding_status: string;
  created_at: string;
  updated_at: string;
}

// Onboarding Data (used in components)
export interface OnboardingData {
  username: string;
  linkedinUrl: string;
  websiteUrl: string;
  twitterUrl: string;
}

/**
 * Extract Twitter/X username from URL
 * Supports: https://twitter.com/username, https://x.com/username
 */
export function extractTwitterUsername(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) return "";

  const urlPattern =
    /^https?:\/\/(?:www\.)?(?:twitter\.com|x\.com)\/([A-Za-z0-9_]{1,15})\/?(?:\?.*)?$/;
  const urlMatch = trimmed.match(urlPattern);
  if (urlMatch) {
    return urlMatch[1];
  }

  return "";
}
