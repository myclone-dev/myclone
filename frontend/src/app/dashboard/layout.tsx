"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useUserMe } from "@/lib/queries/users";
import { PageLoader } from "@/components/ui/page-loader";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { setHasOnboardedCookie } from "@/lib/utils/cookieSync";
import { AssistantWidget } from "@/components/dashboard/personas/AssistantWidget";
import { I18nProvider } from "@/i18n/I18nProvider";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

/**
 * Dashboard Layout
 * Protected route that requires authentication via cookies
 * Middleware ensures only authenticated users reach this layout
 * Includes sidebar navigation and header
 */
export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter();
  const { data: user, isLoading, error } = useUserMe();

  // Redirect to login if user fetch fails (401/403)
  useEffect(() => {
    if (error) {
      const errorWithStatus = error as Error & { status?: number };
      if (errorWithStatus.status === 401 || errorWithStatus.status === 403) {
        router.push("/login");
      }
    }
  }, [error, router]);

  // Redirect visitors - they cannot access dashboard
  useEffect(() => {
    if (user && user.account_type === "visitor") {
      router.push("/visitor");
    }
  }, [user, router]);

  // Redirect to onboarding if user hasn't completed it
  useEffect(() => {
    if (user && user.onboarding_status !== "FULLY_ONBOARDED") {
      router.push("/expert/onboarding");
    }
  }, [user, router]);

  // Set hasOnboarded cookie for cross-domain CTA experience
  useEffect(() => {
    // Only set once when dashboard loads
    setHasOnboardedCookie();
  }, []);

  // Show loading state while fetching user data
  if (isLoading) {
    return <PageLoader text="Loading dashboard..." />;
  }

  // If there's an error or no user, show redirecting state
  if (!user || error) {
    return <PageLoader text="Redirecting..." />;
  }

  return (
    <I18nProvider locale="en">
      <div className="min-h-screen bg-background">
        {/* Sidebar - Desktop */}
        <Sidebar />

        {/* Main Content - Will adjust based on sidebar width via CSS variable */}
        <div className="transition-all duration-300 md:pl-[var(--sidebar-width,256px)]">
          {/* Header */}
          <DashboardHeader user={user} />

          {/* Page Content */}
          <main className="min-h-screen p-4 sm:p-6 lg:p-8">{children}</main>
        </div>

        {/* Assistant Widget - Floating help bubble */}
        <AssistantWidget />
      </div>
    </I18nProvider>
  );
}
