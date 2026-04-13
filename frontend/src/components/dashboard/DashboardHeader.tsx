"use client";

import { LogOut, Settings, Crown } from "lucide-react";
import { useRouter } from "next/navigation";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout } from "@/lib/queries/auth/useAuth";
import { useUserSubscription } from "@/lib/queries/tier";
import { isFreeTier } from "@/lib/constants/tiers";
import type { UserMeResponse } from "@/lib/queries/users/useUserMe";
import { UsageIndicator } from "./UsageIndicator";
import { TierBadge } from "@/components/tier";

interface DashboardHeaderProps {
  user: UserMeResponse;
}

export function DashboardHeader({ user }: DashboardHeaderProps) {
  const router = useRouter();
  const logoutMutation = useLogout();
  const { data: subscription } = useUserSubscription();

  const isFree = isFreeTier(subscription?.tier_id);

  const handleLogout = () => {
    logoutMutation.mutate(undefined, {
      onSettled: () => {
        // Redirect to login after logout (success or failure)
        router.push("/login");
      },
    });
  };

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white md:top-0">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Left side - can add breadcrumbs or search */}
        <div className="flex-1" />

        {/* Right side - Tier badge, Usage indicator and User menu */}
        <div className="flex items-center gap-3">
          {/* Tier Badge with upgrade link for free users */}
          {subscription && (
            <div className="hidden sm:block">
              {isFree ? (
                <a
                  href="/pricing"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-center gap-1.5 rounded-full border border-yellow-200 bg-yellow-50 px-3 py-1.5 text-xs font-medium text-yellow-800 transition-colors hover:border-yellow-300 hover:bg-yellow-100"
                >
                  <Crown className="size-3.5" />
                  <span>Free Plan</span>
                  <span className="text-yellow-600 group-hover:text-yellow-800">
                    - Upgrade
                  </span>
                </a>
              ) : (
                <TierBadge tierId={subscription.tier_id} size="sm" />
              )}
            </div>
          )}

          {/* Combined Usage Indicator */}
          <UsageIndicator />

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="relative h-10 w-10 rounded-full"
              >
                <Avatar className="size-10">
                  <AvatarImage
                    src={user.avatar || undefined}
                    alt={user.fullname}
                  />
                  <AvatarFallback className="bg-orange-100 text-ai-brown 700">
                    {user.fullname.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium">{user.fullname}</p>
                  <p className="text-xs text-slate-500">{user.email}</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => router.push("/dashboard/profile")}
              >
                <Settings className="mr-2 size-4" />
                Profile Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout} className="text-red-600">
                <LogOut className="mr-2 size-4" />
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
