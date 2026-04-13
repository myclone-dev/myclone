"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { User, Check, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useUsernameValidation } from "@/hooks/useUsernameValidation";

const profileSchema = z.object({
  username: z
    .string()
    .min(3, "Username must be at least 3 characters")
    .max(30, "Username must be at most 30 characters"),
});

type ProfileFormData = z.infer<typeof profileSchema>;

interface ProfileAndDataSourcesStepProps {
  defaultValues?: Partial<ProfileFormData>;
  onSubmit: (data: ProfileFormData) => void;
  isSubmitting?: boolean;
}

export function ProfileAndDataSourcesStep({
  defaultValues,
  onSubmit,
  isSubmitting = false,
}: ProfileAndDataSourcesStepProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { isValid },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: defaultValues || {
      username: "",
    },
    mode: "onChange",
  });

  // Watch username field for real-time validation
  const usernameValue = watch("username");
  const usernameValidation = useUsernameValidation(usernameValue || "");

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Username Section */}
      <div className="space-y-4">
        <div className="space-y-2">
          <Label
            htmlFor="username"
            className="text-sm font-medium text-gray-700"
          >
            Choose your username
          </Label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
            <Input
              id="username"
              type="text"
              placeholder="johndoe"
              className={`pl-10 pr-10 ${
                usernameValidation.error && usernameValue.length > 0
                  ? "border-red-500"
                  : usernameValidation.isValid
                    ? "border-green-500"
                    : ""
              }`}
              {...register("username")}
              minLength={3}
              maxLength={30}
              autoComplete="off"
            />
            {/* Validation indicator - translate="no" prevents browser translation from breaking React DOM */}
            <div
              className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5"
              translate="no"
            >
              {usernameValue && usernameValue.length > 0 ? (
                usernameValidation.isChecking ? (
                  <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                ) : usernameValidation.isValid ? (
                  <Check className="h-5 w-5 text-green-500" />
                ) : null
              ) : null}
            </div>
          </div>

          {/* Validation feedback - translate="no" prevents browser translation from breaking React DOM */}
          <div className="min-h-[20px]" translate="no">
            {usernameValue && usernameValue.length > 0 ? (
              usernameValidation.isChecking ? (
                <p className="flex items-center gap-1 text-xs text-blue-600 sm:text-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Checking availability...
                </p>
              ) : usernameValidation.error ? (
                <p className="text-xs text-red-600 sm:text-sm">
                  {usernameValidation.error}
                </p>
              ) : usernameValidation.isValid ? (
                <p className="flex items-center gap-1 text-xs text-green-600 sm:text-sm">
                  <Check className="h-4 w-4" />
                  Username is available!
                </p>
              ) : null
            ) : null}
          </div>

          <p className="text-xs text-gray-500 sm:text-sm">
            3-30 characters. Letters and numbers only.
          </p>
        </div>
      </div>

      {/* Submit Button */}
      <Button
        type="submit"
        disabled={
          !isValid ||
          !usernameValidation.isValid ||
          usernameValidation.isChecking ||
          isSubmitting
        }
        className="w-full"
        size="lg"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Creating your clone...
          </>
        ) : usernameValidation.isChecking ? (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Checking...
          </>
        ) : (
          "Create My Clone"
        )}
      </Button>
    </form>
  );
}
