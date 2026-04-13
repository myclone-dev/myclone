import { Mail, Calendar, Users, Pencil, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { AccessControlUser } from "@/lib/queries/access-control";

interface AccessControlTableProps {
  users: AccessControlUser[];
  onEdit: (user: AccessControlUser) => void;
  onDelete: (user: AccessControlUser) => void;
}

export function AccessControlTable({
  users,
  onEdit,
  onDelete,
}: AccessControlTableProps) {
  // Empty state
  if (users.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-12 text-center">
        <Users className="mx-auto size-12 text-gray-400" />
        <h3 className="mt-4 text-lg font-semibold text-gray-900">
          No users added yet
        </h3>
        <p className="mt-2 text-sm text-gray-600">
          Get started by adding users who can access your private personas.
        </p>
      </div>
    );
  }

  return (
    <>
      {/* Desktop Table View (hidden on mobile) */}
      <div className="hidden rounded-xl border border-gray-200 bg-white shadow-sm md:block">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50 hover:bg-gray-50">
              <TableHead className="font-semibold">User</TableHead>
              <TableHead className="hidden font-semibold lg:table-cell">
                Notes
              </TableHead>
              <TableHead className="hidden font-semibold lg:table-cell">
                Last Access
              </TableHead>
              <TableHead className="font-semibold">Assigned Personas</TableHead>
              <TableHead className="w-[100px] text-right font-semibold">
                Actions
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => {
              const displayName =
                user.firstName && user.lastName
                  ? `${user.firstName} ${user.lastName}`
                  : user.firstName || user.email.split("@")[0];

              return (
                <TableRow key={user.id}>
                  {/* User Info */}
                  <TableCell>
                    <div className="flex items-start gap-3">
                      <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-yellow-100 text-yellow-700">
                        <Mail className="size-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-gray-900">
                          {displayName}
                        </p>
                        <p className="truncate text-sm text-gray-500">
                          {user.email}
                        </p>
                      </div>
                    </div>
                  </TableCell>

                  {/* Notes (hidden on tablet) */}
                  <TableCell className="hidden lg:table-cell">
                    {user.notes ? (
                      <p className="max-w-xs truncate text-sm text-gray-600">
                        {user.notes}
                      </p>
                    ) : (
                      <span className="text-sm text-gray-400">No notes</span>
                    )}
                  </TableCell>

                  {/* Last Access (hidden on tablet) */}
                  <TableCell className="hidden lg:table-cell">
                    {user.lastAccessedAt ? (
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <Calendar className="size-4 text-gray-400" />
                        {new Date(user.lastAccessedAt).toLocaleDateString(
                          "en-US",
                          {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          },
                        )}
                      </div>
                    ) : (
                      <span className="text-sm text-gray-400">Never</span>
                    )}
                  </TableCell>

                  {/* Assigned Personas Count */}
                  <TableCell>
                    <Badge
                      variant={
                        user.assignedPersonaCount > 0 ? "default" : "secondary"
                      }
                      className="font-medium"
                    >
                      {user.assignedPersonaCount}{" "}
                      {user.assignedPersonaCount === 1 ? "persona" : "personas"}
                    </Badge>
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onEdit(user)}
                        className="size-8 text-gray-600 hover:bg-yellow-light hover:text-gray-900 cursor-pointer"
                        title="Edit user"
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onDelete(user)}
                        className="size-8 text-gray-600 hover:bg-red-50 hover:text-red-600 cursor-pointer"
                        title="Delete user"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>

        {/* Table Footer */}
        <div className="border-t bg-gray-50 px-6 py-3">
          <p className="text-sm text-gray-600">
            Total:{" "}
            <span className="font-medium text-gray-900">{users.length}</span>{" "}
            {users.length === 1 ? "user" : "users"}
          </p>
        </div>
      </div>

      {/* Mobile Card View */}
      <div className="space-y-4 md:hidden">
        {users.map((user) => {
          const displayName =
            user.firstName && user.lastName
              ? `${user.firstName} ${user.lastName}`
              : user.firstName || user.email.split("@")[0];

          return (
            <div
              key={user.id}
              className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
            >
              {/* User Info */}
              <div className="mb-4 flex items-start gap-3">
                <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-yellow-100 text-yellow-700">
                  <Mail className="size-6" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-gray-900">
                    {displayName}
                  </p>
                  <p className="truncate text-sm text-gray-500">{user.email}</p>
                </div>
              </div>

              {/* Details Grid */}
              <div className="space-y-3 border-t border-gray-100 pt-4">
                {/* Assigned Personas */}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Personas</span>
                  <Badge
                    variant={
                      user.assignedPersonaCount > 0 ? "default" : "secondary"
                    }
                    className="font-medium"
                  >
                    {user.assignedPersonaCount}{" "}
                    {user.assignedPersonaCount === 1 ? "persona" : "personas"}
                  </Badge>
                </div>

                {/* Last Access */}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Last Access</span>
                  {user.lastAccessedAt ? (
                    <div className="flex items-center gap-2 text-sm text-gray-700">
                      <Calendar className="size-4 text-gray-400" />
                      {new Date(user.lastAccessedAt).toLocaleDateString(
                        "en-US",
                        {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        },
                      )}
                    </div>
                  ) : (
                    <span className="text-sm text-gray-400">Never</span>
                  )}
                </div>

                {/* Notes */}
                {user.notes && (
                  <div className="flex flex-col gap-1">
                    <span className="text-sm text-gray-600">Notes</span>
                    <p className="text-sm text-gray-700">{user.notes}</p>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="mt-4 flex gap-2 border-t border-gray-100 pt-4">
                <Button
                  variant="outline"
                  onClick={() => onEdit(user)}
                  className="flex-1 gap-2"
                >
                  <Pencil className="size-4" />
                  Edit
                </Button>
                <Button
                  variant="outline"
                  onClick={() => onDelete(user)}
                  className="flex-1 gap-2 hover:bg-red-50 hover:text-red-600 hover:border-red-200"
                >
                  <Trash2 className="size-4" />
                  Delete
                </Button>
              </div>
            </div>
          );
        })}

        {/* Mobile Footer */}
        <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
          <p className="text-sm text-gray-600">
            Total:{" "}
            <span className="font-medium text-gray-900">{users.length}</span>{" "}
            {users.length === 1 ? "user" : "users"}
          </p>
        </div>
      </div>
    </>
  );
}
