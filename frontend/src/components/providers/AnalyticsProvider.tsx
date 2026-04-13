"use client";

import { useEffect, Suspense, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import posthog from "posthog-js";
import { Analytics } from "@vercel/analytics/react";
import ReactGA from "react-ga4";
import { env } from "@/env";
import { useAuthStore } from "@/store/auth.store";
import { identifyUser } from "@/lib/analytics/posthog";

function AnalyticsTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user, isAuthenticated } = useAuthStore();
  const hasIdentifiedRef = useRef(false);

  // Initialize PostHog
  useEffect(() => {
    if (
      typeof window !== "undefined" &&
      env.NEXT_PUBLIC_POSTHOG_KEY &&
      env.NEXT_PUBLIC_POSTHOG_HOST
    ) {
      posthog.init(env.NEXT_PUBLIC_POSTHOG_KEY, {
        api_host: env.NEXT_PUBLIC_POSTHOG_HOST,
        person_profiles: "identified_only",
        capture_pageview: false, // We'll manually capture pageviews
        capture_pageleave: true,
        session_recording: {
          maskAllInputs: false,
          maskInputOptions: {
            password: true, // Always keep passwords masked
          },
        },
        persistence: "localStorage+cookie",
        // Use modern defaults
        bootstrap: {
          featureFlags: {},
        },
      });
    } else {
      console.warn(
        "PostHog not initialized. Missing API key or host configuration.",
      );
    }
  }, []);

  // Initialize Google Analytics
  useEffect(() => {
    if (typeof window !== "undefined" && env.NEXT_PUBLIC_GA_MEASUREMENT_ID) {
      ReactGA.initialize(env.NEXT_PUBLIC_GA_MEASUREMENT_ID);
    }
  }, []);

  // Track page views
  useEffect(() => {
    if (pathname) {
      const url =
        pathname +
        (searchParams?.toString() ? `?${searchParams.toString()}` : "");

      // PostHog pageview
      if (
        typeof window !== "undefined" &&
        env.NEXT_PUBLIC_POSTHOG_KEY &&
        env.NEXT_PUBLIC_POSTHOG_HOST
      ) {
        posthog.capture("$pageview", {
          $current_url: url,
        });
      }

      // Google Analytics pageview
      if (typeof window !== "undefined" && env.NEXT_PUBLIC_GA_MEASUREMENT_ID) {
        ReactGA.send({ hitType: "pageview", page: url });
      }
    }
  }, [pathname, searchParams]);

  // Identify authenticated users in PostHog on app load
  // This handles returning users with persisted auth state
  useEffect(() => {
    if (
      isAuthenticated &&
      user &&
      !hasIdentifiedRef.current &&
      typeof window !== "undefined" &&
      env.NEXT_PUBLIC_POSTHOG_KEY
    ) {
      identifyUser({
        id: user.id,
        email: user.email,
        name: user.name,
        username: user.username,
        account_type: user.account_type,
      });
      hasIdentifiedRef.current = true;
    }

    // Reset ref when user logs out
    if (!isAuthenticated) {
      hasIdentifiedRef.current = false;
    }
  }, [isAuthenticated, user]);

  return null;
}

export function AnalyticsProvider({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Suspense fallback={null}>
        <AnalyticsTracker />
      </Suspense>
      {children}
      {/* Vercel Analytics */}
      <Analytics />
    </>
  );
}
