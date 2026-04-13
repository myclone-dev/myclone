/**
 * Root page - Redirects based on authentication status
 *
 * OnboardingGuard handles the redirect logic:
 * - Not authenticated → /login
 * - Authenticated + not onboarded → /expert/onboarding
 * - Authenticated + onboarded → /dashboard
 *
 * Returns null to avoid flashing content before redirect
 */
export default function Home() {
  return null;
}
