"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Shield,
  UserPlus,
  Mail,
  AlertCircle,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import {
  useAccessControlUsers,
  usePersonaAccessControlUsers,
  useAssignUsers,
  useRemovePersonaUser,
} from "@/lib/queries/access-control";
import Link from "next/link";

interface PersonaAccessControlDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  personaId: string;
  personaName: string;
  isPrivate: boolean;
}

export function PersonaAccessControlDialog({
  open,
  onOpenChange,
  personaId,
  personaName,
  isPrivate,
}: PersonaAccessControlDialogProps) {
  // Queries
  const { data: allUsersData, isLoading: allUsersLoading } =
    useAccessControlUsers();
  const { data: assignedUsersData, isLoading: assignedUsersLoading } =
    usePersonaAccessControlUsers(personaId);

  // Mutations
  const assignUsers = useAssignUsers();
  const removeUser = useRemovePersonaUser();

  const allUsers = allUsersData?.visitors || [];
  const assignedUsers = assignedUsersData?.visitors || [];
  const assignedUserIds = new Set(assignedUsers.map((u) => u.id));

  const handleToggleUserAccess = (userId: string, hasAccess: boolean) => {
    if (hasAccess) {
      // Remove access
      removeUser.mutate(
        { personaId, userId },
        {
          onSuccess: () => {
            toast.success("User access removed");
          },
          onError: (error: Error) => {
            toast.error("Failed to remove user access", {
              description: error.message,
            });
          },
        },
      );
    } else {
      // Grant access
      assignUsers.mutate(
        { personaId, visitorIds: [userId] },
        {
          onSuccess: () => {
            toast.success("User access granted");
          },
          onError: (error: Error) => {
            toast.error("Failed to grant user access", {
              description: error.message,
            });
          },
        },
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[650px] max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="size-5 text-yellow-600" />
            Access Control: {personaName}
          </DialogTitle>
          <DialogDescription>
            Control who can access this persona. Toggle users ON to grant access
            or OFF to remove access.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Info Banner when Private */}
          {isPrivate && (
            <div className="flex items-start gap-3 rounded-lg border border-yellow-200/50 bg-yellow-50/30 p-3">
              <AlertCircle className="size-4 text-yellow-600/60 mt-0.5 shrink-0" />
              <div className="flex-1 text-sm text-gray-600">
                <p className="font-medium text-gray-700">
                  Email verification required
                </p>
                <p className="mt-1">
                  Visitors will receive a one-time password (OTP) via email to
                  verify their identity before accessing this persona.
                </p>
              </div>
            </div>
          )}

          {/* User Access Management */}
          {isPrivate && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold">Manage User Access</h3>
                  <p className="text-sm text-muted-foreground">
                    {assignedUsers.length} of {allUsers.length} user(s) have
                    access
                  </p>
                </div>
                {allUsers.length === 0 && (
                  <Button variant="outline" size="sm" asChild>
                    <Link
                      href="/dashboard/access-control"
                      className="gap-2"
                      onClick={() => onOpenChange(false)}
                    >
                      <UserPlus className="size-4" />
                      Add Users
                      <ExternalLink className="size-3" />
                    </Link>
                  </Button>
                )}
              </div>

              {allUsersLoading || assignedUsersLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 rounded-lg" />
                  ))}
                </div>
              ) : allUsers.length === 0 ? (
                <div className="rounded-lg border border-dashed p-6 text-center">
                  <Shield className="mx-auto mb-3 size-12 text-muted-foreground" />
                  <p className="text-sm font-medium text-muted-foreground mb-2">
                    No users in access control list
                  </p>
                  <p className="text-xs text-muted-foreground mb-4">
                    Add users to your global access control list first, then
                    toggle them ON to grant access to this persona.
                  </p>
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/dashboard/access-control" className="gap-2">
                      <UserPlus className="size-4" />
                      Go to Access Control
                      <ExternalLink className="size-3" />
                    </Link>
                  </Button>
                </div>
              ) : (
                <ScrollArea
                  className={`rounded-lg border ${
                    allUsers.length <= 3
                      ? "max-h-[300px]"
                      : allUsers.length <= 5
                        ? "h-[400px]"
                        : "h-96"
                  }`}
                >
                  <div className="p-2 space-y-2">
                    {allUsers.map((user) => {
                      const hasAccess = assignedUserIds.has(user.id);
                      return (
                        <div
                          key={user.id}
                          className={`flex items-center justify-between rounded-lg border p-3 transition-colors ${
                            hasAccess
                              ? "bg-white border-gray-200"
                              : "bg-card hover:bg-muted/50"
                          }`}
                        >
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <div
                              className={`flex size-10 shrink-0 items-center justify-center rounded-full ${
                                hasAccess ? "bg-yellow-100" : "bg-slate-100"
                              }`}
                            >
                              <Mail
                                className={`size-5 ${
                                  hasAccess
                                    ? "text-yellow-600"
                                    : "text-slate-600"
                                }`}
                              />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm truncate">
                                {user.firstName && user.lastName
                                  ? `${user.firstName} ${user.lastName}`
                                  : user.email}
                              </p>
                              <p className="text-xs text-muted-foreground truncate">
                                {user.email}
                              </p>
                            </div>
                          </div>
                          <Switch
                            checked={hasAccess}
                            onCheckedChange={() =>
                              handleToggleUserAccess(user.id, hasAccess)
                            }
                            disabled={
                              assignUsers.isPending || removeUser.isPending
                            }
                            className="shrink-0"
                          />
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              )}
            </div>
          )}

          {/* Show message when persona is public */}
          {!isPrivate && (
            <div className="rounded-lg border border-dashed p-6 text-center">
              <Shield className="mx-auto mb-3 size-12 text-muted-foreground" />
              <p className="text-sm font-medium text-muted-foreground mb-2">
                Persona is currently public
              </p>
              <p className="text-xs text-muted-foreground">
                Enable &quot;Require Access Control&quot; on the persona card to
                manage user access.
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
