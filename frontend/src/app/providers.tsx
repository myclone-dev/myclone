"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { AnalyticsProvider } from "@/components/providers/AnalyticsProvider";
import { OnboardingGuard } from "@/components/guards/OnboardingGuard";
import { Toaster } from "sonner";
import { NextStepProvider, NextStep } from "nextstepjs";
import { dashboardTours } from "@/config/dashboard-tours";
import { TourCard } from "@/components/dashboard/TourCard";

// Client-only devtools wrapper
function DevTools() {
  const [mounted, setMounted] = useState(false);
  const [Devtools, setDevtools] = useState<React.ComponentType<{
    initialIsOpen: boolean;
  }> | null>(null);

  useEffect(() => {
    setMounted(true);
    if (process.env.NODE_ENV !== "production") {
      import("@tanstack/react-query-devtools").then((mod) => {
        setDevtools(() => mod.ReactQueryDevtools);
      });
    }
  }, []);

  if (!mounted || !Devtools) {
    return null;
  }

  return <Devtools initialIsOpen={false} />;
}

/**
 * Client-side providers wrapper
 * Sets up TanStack Query with optimal defaults
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Data is considered fresh for 1 minute
            staleTime: 60 * 1000,
            // Don't refetch on window focus (can be annoying during development)
            refetchOnWindowFocus: false,
            // Retry failed requests once
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AnalyticsProvider>
        <OnboardingGuard>
          <NextStepProvider>
            <NextStep steps={dashboardTours} cardComponent={TourCard}>
              {children}
            </NextStep>
          </NextStepProvider>
          <Toaster richColors />
          <DevTools />
        </OnboardingGuard>
      </AnalyticsProvider>
    </QueryClientProvider>
  );
}
