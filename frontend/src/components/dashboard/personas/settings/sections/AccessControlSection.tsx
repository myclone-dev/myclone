"use client";

import { useState } from "react";
import { Shield, Mail, AlertCircle, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SectionHeader } from "../components/SectionHeader";
import { AddUserDialog } from "@/components/dashboard/access-control/AddUserDialog";
import {
  useAccessControlToggle,
  useAccessControlUsers,
  usePersonaAccessControlUsers,
  useAssignUsers,
  useRemovePersonaUser,
} from "@/lib/queries/access-control";
import { cn } from "@/lib/utils";
import type { Persona } from "../../PersonaSettingsDialog/types";

interface AccessControlSectionProps {
  personaId: string;
  persona: Persona;
}

export function AccessControlSection({
  personaId,
  persona,
}: AccessControlSectionProps) {
  const [addUserDialogOpen, setAddUserDialogOpen] = useState(false);

  const { data: allUsersData, isLoading: allUsersLoading } =
    useAccessControlUsers();
  const { data: assignedUsersData, isLoading: assignedUsersLoading } =
    usePersonaAccessControlUsers(personaId);

  const toggleAccessControl = useAccessControlToggle();
  const assignUsers = useAssignUsers();
  const removeUser = useRemovePersonaUser();

  const allUsers = allUsersData?.visitors || [];
  const assignedUsers = assignedUsersData?.visitors || [];
  const assignedUserIds = new Set(assignedUsers.map((u) => u.id));

  const handleTogglePrivacy = async (isPrivate: boolean) => {
    try {
      await toggleAccessControl.mutateAsync({ personaId, isPrivate });
      toast.success(
        isPrivate
          ? "Access control enabled - persona is now private"
          : "Access control disabled - persona is now public",
      );
    } catch (error) {
      const err = error as { message?: string };
      toast.error("Failed to update access control", {
        description: err.message,
      });
    }
  };

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

  const handleUserAdded = (userId: string) => {
    // Automatically assign the newly added user to this persona
    assignUsers.mutate(
      { personaId, visitorIds: [userId] },
      {
        onSuccess: () => {
          toast.success("User added and assigned to this persona");
        },
        onError: (error: Error) => {
          toast.error("User added but failed to assign to persona", {
            description: error.message,
          });
        },
      },
    );
  };

  const isPrivate = persona.is_private;
  const isMutating =
    toggleAccessControl.isPending ||
    assignUsers.isPending ||
    removeUser.isPending;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Access Control"
        description="Control who can access this persona"
        isSaving={isMutating}
      />

      {/* Privacy Toggle */}
      <Card className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-violet-100">
              <Shield className="size-5 text-violet-600" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Require Access Control</h3>
              <p className="text-xs text-muted-foreground mt-1">
                When enabled, only approved users can access this persona
              </p>
            </div>
          </div>
          <Switch
            checked={isPrivate}
            onCheckedChange={handleTogglePrivacy}
            disabled={toggleAccessControl.isPending}
          />
        </div>
      </Card>

      {/* Email Verification Notice (only when private) */}
      {isPrivate && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="flex gap-3">
            <AlertCircle className="size-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-semibold text-amber-900">
                Email verification required
              </h4>
              <p className="text-xs text-amber-800 mt-1">
                Visitors will receive a one-time password (OTP) via email to
                verify their identity before accessing this persona.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* User Access Management (only when private) */}
      {isPrivate && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold">Manage User Access</h3>
              <p className="text-sm text-muted-foreground">
                {assignedUsers.length} of {allUsers.length} user(s) have access
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAddUserDialogOpen(true)}
            >
              <Plus className="size-4 mr-2" />
              Add User
            </Button>
          </div>

          {allUsersLoading || assignedUsersLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 rounded-lg" />
              ))}
            </div>
          ) : allUsers.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <Shield className="size-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm font-medium mb-1">
                No users in access control list
              </p>
              <p className="text-xs text-muted-foreground mb-4">
                Add users to start controlling access to this persona. Users
                will be available for all your personas.
              </p>
              <Button
                variant="outline"
                onClick={() => setAddUserDialogOpen(true)}
              >
                <Plus className="size-4 mr-2" />
                Add First User
              </Button>
            </div>
          ) : (
            <ScrollArea
              className={cn(
                "rounded-lg border",
                allUsers.length <= 3 && "max-h-[300px]",
                allUsers.length > 3 && allUsers.length <= 5 && "h-[400px]",
                allUsers.length > 5 && "h-96",
              )}
            >
              <div className="p-2 space-y-2">
                {allUsers.map((user) => {
                  const hasAccess = assignedUserIds.has(user.id);
                  return (
                    <Card
                      key={user.id}
                      className={cn(
                        "p-3 transition-colors",
                        hasAccess
                          ? "bg-white border-gray-200"
                          : "bg-card hover:bg-muted/50",
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            "flex size-10 shrink-0 items-center justify-center rounded-full",
                            hasAccess ? "bg-yellow-100" : "bg-slate-100",
                          )}
                        >
                          <Mail
                            className={cn(
                              "size-4",
                              hasAccess ? "text-yellow-600" : "text-slate-400",
                            )}
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {user.firstName && user.lastName
                              ? `${user.firstName} ${user.lastName}`
                              : user.email}
                          </p>
                          <p className="text-xs text-muted-foreground truncate">
                            {user.email}
                          </p>
                        </div>
                        <Switch
                          checked={hasAccess}
                          onCheckedChange={() =>
                            handleToggleUserAccess(user.id, hasAccess)
                          }
                          disabled={isMutating}
                        />
                      </div>
                    </Card>
                  );
                })}
              </div>
            </ScrollArea>
          )}
        </div>
      )}

      {/* Public Persona Message (only when public) */}
      {!isPrivate && (
        <div className="rounded-lg border-2 border-dashed p-6 text-center">
          <Shield className="size-8 text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">
            This persona is currently public. Enable "Require Access Control"
            above to manage user access.
          </p>
        </div>
      )}

      {/* Add User Dialog */}
      <AddUserDialog
        open={addUserDialogOpen}
        onOpenChange={setAddUserDialogOpen}
        onUserAdded={handleUserAdded}
      />
    </div>
  );
}
