"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import {
  useRemoveAccessControlUser,
  type AccessControlUser,
} from "@/lib/queries/access-control";

interface DeleteConfirmDialogProps {
  user: AccessControlUser | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteConfirmDialog({
  user,
  open,
  onOpenChange,
}: DeleteConfirmDialogProps) {
  const { mutate: deleteUser, isPending } = useRemoveAccessControlUser();

  const handleDelete = () => {
    if (!user) return;

    deleteUser(user.id, {
      onSuccess: () => {
        toast.success("User removed successfully!");
        onOpenChange(false);
      },
      onError: (error: Error) => {
        const message =
          (error as { response?: { data?: { detail?: string } } })?.response
            ?.data?.detail ||
          error.message ||
          "Failed to remove user. Please try again.";
        toast.error(message);
      },
    });
  };

  if (!user) return null;

  const displayName =
    user.firstName && user.lastName
      ? `${user.firstName} ${user.lastName}`
      : user.firstName || user.email;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-red-100">
              <AlertTriangle className="size-6 text-red-600" />
            </div>
            <div className="flex-1">
              <AlertDialogTitle>Remove User</AlertDialogTitle>
              <AlertDialogDescription className="mt-1">
                Are you sure you want to remove <strong>{displayName}</strong>?
              </AlertDialogDescription>
            </div>
          </div>
        </AlertDialogHeader>

        <div className="space-y-3 py-2">
          {/* User Info */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-sm font-medium text-gray-900">{user.email}</p>
            {user.assignedPersonaCount > 0 && (
              <p className="mt-1 text-sm text-gray-600">
                Currently assigned to{" "}
                <strong>
                  {user.assignedPersonaCount}{" "}
                  {user.assignedPersonaCount === 1 ? "persona" : "personas"}
                </strong>
              </p>
            )}
          </div>

          {/* Warning Message */}
          <div className="rounded-lg border border-red-200 bg-red-50 p-3">
            <p className="text-sm font-medium text-red-900">
              This action cannot be undone
            </p>
            <ul className="mt-2 space-y-1 text-sm text-red-800">
              <li className="flex items-start gap-2">
                <span className="mt-0.5 text-red-600">•</span>
                <span>
                  User will be removed from{" "}
                  <strong>all assigned personas</strong>
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 text-red-600">•</span>
                <span>
                  They will <strong>immediately lose access</strong> to private
                  personas
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 text-red-600">•</span>
                <span>You&apos;ll need to re-add them to restore access</span>
              </li>
            </ul>
          </div>
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleDelete}
            disabled={isPending}
            className="gap-2 bg-red-600 hover:bg-red-700"
          >
            {isPending && <Loader2 className="size-4 animate-spin" />}
            Remove User
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
