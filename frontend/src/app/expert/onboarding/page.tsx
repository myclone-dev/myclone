"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useUserMe } from "@/lib/queries/users";
import { PageLoader } from "@/components/ui/page-loader";
import ExpertOnboarding from "@/components/expert/onboarding/ExpertOnboarding";

export default function ExpertOnboardingPage() {
  const router = useRouter();
  const { data: user, isLoading } = useUserMe();

  // Redirect visitors - they cannot access onboarding
  useEffect(() => {
    if (user && user.account_type === "visitor") {
      router.push("/visitor");
    }
  }, [user, router]);

  // Show loading state while checking user
  if (isLoading) {
    return <PageLoader text="Loading..." />;
  }

  // If visitor, show loading while redirecting
  if (user && user.account_type === "visitor") {
    return <PageLoader text="Redirecting..." />;
  }

  // Note: This page is accessible to authenticated creator users only
  // The expert role will be set after completing onboarding
  return <ExpertOnboarding />;
}
