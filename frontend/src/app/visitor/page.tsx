"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { useLogout } from "@/lib/queries/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/page-loader";
import { Sparkles, LogOut } from "lucide-react";
import { env } from "@/env";

/**
 * Visitor Welcome Page
 * Shows visitors how to access personas via URLs
 * Redirects creators to dashboard
 */
export default function VisitorPage() {
  const router = useRouter();
  const { data: user, isLoading } = useUserMe();
  const logoutMutation = useLogout();
  const [pendingPersona, setPendingPersona] = useState<string | null>(null);

  useEffect(() => {
    // Check for pending purchase
    if (typeof window !== "undefined") {
      const pending = localStorage.getItem("pending_purchase");
      setPendingPersona(pending);
    }
  }, []);

  // Redirect unauthenticated users to login
  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  // Redirect creators to dashboard
  useEffect(() => {
    if (user && user.account_type !== "visitor") {
      router.push("/dashboard");
    }
  }, [user, router]);

  const handleLogout = () => {
    logoutMutation.mutate(undefined, {
      onSettled: () => {
        // Redirect to login after logout (success or error)
        router.push("/login");
      },
    });
  };

  const handleContinueToPurchase = () => {
    if (pendingPersona && typeof window !== "undefined") {
      localStorage.removeItem("pending_purchase");
      // Redirect to persona page - you may need to adjust this route
      router.push(`/persona/${pendingPersona}`);
    }
  };

  // Show loading while checking user
  if (isLoading) {
    return <PageLoader text="Loading..." />;
  }

  // Show loading if not authenticated (will redirect to login)
  if (!user) {
    return <PageLoader text="Redirecting..." />;
  }

  // Show loading if user is creator (will redirect to dashboard)
  if (user.account_type !== "visitor") {
    return <PageLoader text="Redirecting to dashboard..." />;
  }

  // Format app URL (remove trailing slash if present)
  const appUrl = env.NEXT_PUBLIC_APP_URL.endsWith("/")
    ? env.NEXT_PUBLIC_APP_URL.slice(0, -1)
    : env.NEXT_PUBLIC_APP_URL;

  return (
    <div className="min-h-screen bg-gradient-to-br from-yellow-light via-peach-cream to-peach-light flex items-center justify-center p-4">
      <Card className="max-w-2xl w-full p-8 space-y-6">
        {/* Header */}
        <div className="text-center space-y-3">
          <div className="flex justify-center">
            <div className="relative">
              <div className="absolute inset-0 bg-amber-400/20 blur-xl rounded-full" />
              <div className="relative bg-gradient-to-br from-amber-400 to-orange-500 p-4 rounded-full">
                <Sparkles className="w-8 h-8 text-white" />
              </div>
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">
            Welcome to ConvoxAI!
          </h1>
          <p className="text-gray-600">
            Chat with AI personas powered by real expertise
          </p>
        </div>

        {/* How to Access Section */}
        <div className="bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            How to Access Personas
          </h2>
          <p className="text-gray-700">
            You can chat with any available persona by visiting their URL:
          </p>
          <div className="bg-white border border-amber-300 rounded-md p-4">
            <code className="text-sm font-mono text-amber-700 break-all">
              {appUrl}/<span className="text-gray-500">username</span>/
              <span className="text-gray-500">persona-name</span>
            </code>
          </div>
          <p className="text-sm text-gray-600">
            Each persona has a unique URL. Ask the creator for their persona
            link to start chatting.
          </p>
        </div>

        {/* Continue to Purchase (if pending) */}
        {pendingPersona && (
          <div className="space-y-3">
            <Button
              onClick={handleContinueToPurchase}
              size="lg"
              className="w-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
            >
              Continue to Persona
            </Button>
          </div>
        )}

        {/* Logout Button */}
        <div className="pt-4 border-t">
          <Button
            onClick={handleLogout}
            variant="outline"
            className="w-full"
            size="lg"
            disabled={logoutMutation.isPending}
          >
            <LogOut className="w-4 h-4 mr-2" />
            {logoutMutation.isPending ? "Logging out..." : "Logout"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
