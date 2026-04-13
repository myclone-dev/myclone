"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { Pencil } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { useUpdateProfile } from "@/lib/queries/users";
import type { UpdateProfileRequest } from "@/lib/queries/users";

interface ProfileEditDialogProps {
  currentCompany?: string | null;
  currentRole?: string | null;
}

export function ProfileEditDialog({
  currentCompany,
  currentRole,
}: ProfileEditDialogProps) {
  const [open, setOpen] = useState(false);
  const updateProfile = useUpdateProfile();

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
    reset,
  } = useForm<UpdateProfileRequest>({
    defaultValues: {
      company: currentCompany || "",
      role: currentRole || "",
    },
  });

  const onSubmit = async (data: UpdateProfileRequest) => {
    trackDashboardOperation("profile_update", "started", {
      hasCompany: !!data.company,
      hasRole: !!data.role,
    });

    try {
      await updateProfile.mutateAsync(data);

      trackDashboardOperation("profile_update", "success", {
        hasCompany: !!data.company,
        hasRole: !!data.role,
      });

      toast.success("Profile updated successfully!");
      setOpen(false);
      reset(data); // Reset form with new values
    } catch (error) {
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to update profile";

      trackDashboardOperation("profile_update", "error", {
        error: errorMessage,
      });

      toast.error(errorMessage);
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      // Reset form when closing
      reset({
        company: currentCompany || "",
        role: currentRole || "",
      });
    }
    setOpen(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Pencil className="size-4" />
          Edit Profile
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit Profile</DialogTitle>
            <DialogDescription>
              Update your company and role information
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Company */}
            <div className="space-y-2">
              <Label htmlFor="company">Company</Label>
              <Input
                id="company"
                placeholder="e.g., Acme Corp"
                {...register("company", {
                  maxLength: {
                    value: 200,
                    message: "Company name must be less than 200 characters",
                  },
                })}
                className={errors.company ? "border-red-500" : ""}
              />
              {errors.company && (
                <p className="text-sm text-red-500">{errors.company.message}</p>
              )}
            </div>

            {/* Role */}
            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <Input
                id="role"
                placeholder="e.g., Senior Software Engineer"
                {...register("role", {
                  maxLength: {
                    value: 200,
                    message: "Role must be less than 200 characters",
                  },
                })}
                className={errors.role ? "border-red-500" : ""}
              />
              {errors.role && (
                <p className="text-sm text-red-500">{errors.role.message}</p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!isDirty || updateProfile.isPending}
            >
              {updateProfile.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
