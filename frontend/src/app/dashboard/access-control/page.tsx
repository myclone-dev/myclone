"use client";

import { useState } from "react";
import { Shield, UserPlus, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAccessControlUsers } from "@/lib/queries/access-control";
import { PageLoader } from "@/components/ui/page-loader";
import { AccessControlTable } from "@/components/dashboard/access-control/AccessControlTable";
import { AddUserDialog } from "@/components/dashboard/access-control/AddUserDialog";
import { EditUserDialog } from "@/components/dashboard/access-control/EditUserDialog";
import { DeleteConfirmDialog } from "@/components/dashboard/access-control/DeleteConfirmDialog";
import type { AccessControlUser } from "@/lib/queries/access-control";

/**
 * Access Control Page
 * Manage global list of users who can access private personas
 */
export default function AccessControlPage() {
  const { data: usersData, isLoading } = useAccessControlUsers();
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AccessControlUser | null>(
    null,
  );
  const [deletingUser, setDeletingUser] = useState<AccessControlUser | null>(
    null,
  );

  if (isLoading) {
    return <PageLoader />;
  }

  const users = usersData?.visitors || [];

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Shield className="size-8 text-yellow-600" />
            Access Control
          </h1>
          <p className="text-muted-foreground">
            Manage users who can access your private personas. Add users here,
            then assign them to specific personas.
          </p>
        </div>
        <Button
          onClick={() => setAddDialogOpen(true)}
          className="gap-2 bg-yellow-bright text-black hover:bg-yellow-bright/90 cursor-pointer"
        >
          <UserPlus className="size-4" />
          Add User
        </Button>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-yellow-50 border border-yellow-300">
        <Info className="size-5 text-yellow-600 mt-0.5 shrink-0" />
        <div className="flex-1">
          <h3 className="text-sm font-medium text-yellow-900">
            How Access Control Works
          </h3>
          <p className="text-sm text-yellow-700 mt-1">
            This is your global access list. Users added here can be assigned to
            one or more private personas. <strong>To assign users:</strong>{" "}
            Personas → Select a persona → Access Control → Choose users from
            this list.
          </p>
        </div>
      </div>

      {/* Users Table */}
      <AccessControlTable
        users={users}
        onEdit={(user) => setEditingUser(user)}
        onDelete={(user) => setDeletingUser(user)}
      />

      {/* Dialogs */}
      <AddUserDialog open={addDialogOpen} onOpenChange={setAddDialogOpen} />
      <EditUserDialog
        user={editingUser}
        open={!!editingUser}
        onOpenChange={(open) => !open && setEditingUser(null)}
      />
      <DeleteConfirmDialog
        user={deletingUser}
        open={!!deletingUser}
        onOpenChange={(open) => !open && setDeletingUser(null)}
      />
    </div>
  );
}
