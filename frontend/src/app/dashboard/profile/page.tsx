"use client";

import { User } from "lucide-react";
import { useUserMe } from "@/lib/queries/users";
import { ProfileCard } from "@/components/dashboard/profile/ProfileCard";
import { AccountInfo } from "@/components/dashboard/profile/AccountInfo";
import { PageLoader } from "@/components/ui/page-loader";
import { Alert, AlertDescription } from "@/components/ui/alert";

/**
 * User Profile Page
 * View and manage user profile settings
 */
export default function ProfilePage() {
  const { data: user, isLoading } = useUserMe();

  if (isLoading || !user) {
    return <PageLoader />;
  }

  return (
    <div className="max-w-4xl mx-auto py-8 space-y-8 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="flex size-12 items-center justify-center rounded-lg bg-orange-100">
            <User className="size-6 text-ai-brown" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Profile</h1>
            <p className="text-sm text-slate-600">
              Manage your account information and settings
            </p>
          </div>
        </div>
      </div>

      {/* Profile Card */}
      <ProfileCard user={user} />

      {/* Account Info (includes tier plan) */}
      <AccountInfo user={user} />

      {/* Info Alert */}
      <Alert>
        <AlertDescription>
          Your profile information is synced from your LinkedIn account. To
          update your details, please reconnect your LinkedIn profile or contact
          support.
        </AlertDescription>
      </Alert>
    </div>
  );
}
