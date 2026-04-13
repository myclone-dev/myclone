"use client";

import { useEffect, useMemo } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { isCustomDomain } from "@/lib/constants/domains";

interface OnboardingGuardProps {
  children: React.ReactNode;
}

/**
 * Guards all routes and redirects users based on onboarding status
 * - Home page (/) → redirects to /expert/onboarding if not onboarded, /dashboard if onboarded
 * - NOT_STARTED or PARTIAL → ONLY /expert/onboarding, public routes, and username routes allowed
 * - FULLY_ONBOARDED → allowed everywhere
 * - Username routes (/[username], /[username]/[persona]) are always public
 * - Custom domains are treated as public username routes (no redirects)
 */
export function OnboardingGuard({ children }: OnboardingGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: currentUser, isLoading } = useUserMe();

  // Check for custom domain - memoized to avoid recalculation
  // Returns false during SSR (window undefined), true/false on client
  const isCustomDomainHost = useMemo(() => {
    if (typeof window === "undefined") return false;
    return isCustomDomain(window.location.hostname);
  }, []);

  useEffect(() => {
    // Custom domains should never trigger redirects - they're always public
    // The middleware handles routing custom domains to the correct username page
    if (isCustomDomainHost) {
      return;
    }

    // Public routes that don't require authentication
    const publicRoutes = ["/login", "/signup", "/terms", "/privacy"];
    const isOnboardingPage = pathname.startsWith("/expert/onboarding");
    const isPublicRoute = publicRoutes.includes(pathname);
    const isHomePage = pathname === "/";
    const isVisitorPage = pathname === "/visitor";

    // Check if it's a username profile route (e.g., /johndoe or /johndoe/persona-name)
    // These are public pages accessible without authentication
    // Exclude known app routes like /dashboard, /expert, etc.
    // Also allow payment routes (/username/persona/payment/success or /cancel)
    const isUsernameRoute =
      (pathname.match(/^\/[^\/]+(?:\/[^\/]+)?$/) || // Matches /username or /username/persona
        pathname.match(/^\/[^\/]+\/[^\/]+\/payment\/(success|cancel)$/)) && // Matches payment routes
      !publicRoutes.includes(pathname) &&
      !isHomePage &&
      !pathname.startsWith("/dashboard") &&
      !pathname.startsWith("/expert") &&
      !pathname.startsWith("/visitor");

    if (!isLoading && currentUser) {
      const needsOnboarding =
        currentUser.onboarding_status !== "FULLY_ONBOARDED";
      const isVisitor = currentUser.account_type === "visitor";

      // If on home page, redirect based on account type and onboarding status
      if (isHomePage) {
        // Homepage redirect logic
        if (isVisitor) {
          router.push("/visitor");
        } else if (needsOnboarding) {
          router.push("/expert/onboarding");
        } else {
          router.push("/dashboard");
        }
        return;
      }

      // Visitors should stay on visitor page or access username routes only
      if (isVisitor && !isVisitorPage && !isUsernameRoute && !isPublicRoute) {
        router.push("/visitor");
        return;
      }

      // If not onboarded, ONLY allow onboarding page, public routes, and username routes
      if (
        needsOnboarding &&
        !isOnboardingPage &&
        !isPublicRoute &&
        !isUsernameRoute
      ) {
        router.push("/expert/onboarding");
      }

      // Redirect away from onboarding if already complete
      if (!needsOnboarding && isOnboardingPage) {
        router.push("/dashboard");
      }
    }

    // Redirect unauthenticated users to login (except on public/username routes)
    if (!isLoading && !currentUser && !isPublicRoute && !isUsernameRoute) {
      router.push("/login");
    }
  }, [currentUser, isLoading, pathname, router, isCustomDomainHost]);

  return <>{children}</>;
}
