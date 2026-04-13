"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  User,
  Briefcase,
  Building2,
  ArrowRight,
  Check,
  Loader2,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useUsernameValidation } from "@/hooks/useUsernameValidation";

const usernameSchema = z.object({
  username: z
    .string()
    .min(3, "Username must be at least 3 characters")
    .max(30, "Username must be at most 30 characters"),
  currentRole: z
    .string()
    .min(2, "Role must be at least 2 characters")
    .max(100, "Role must be at most 100 characters"),
  currentCompany: z
    .string()
    .min(2, "Company must be at least 2 characters")
    .max(100, "Company must be at most 100 characters"),
});

type UsernameFormData = z.infer<typeof usernameSchema>;

interface UsernameStepProps {
  defaultValues?: UsernameFormData;
  onNext: (data: UsernameFormData) => void;
}

export function UsernameStep({ defaultValues, onNext }: UsernameStepProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isValid },
  } = useForm<UsernameFormData>({
    resolver: zodResolver(usernameSchema),
    defaultValues: defaultValues || {
      username: "",
      currentRole: "",
      currentCompany: "",
    },
    mode: "onChange",
  });

  // Watch username field for real-time validation
  const usernameValue = watch("username");
  const usernameValidation = useUsernameValidation(usernameValue || "");

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4 sm:space-y-6">
      {/* Username Field */}
      <div className="space-y-2">
        <Label htmlFor="username" className="text-sm font-medium text-gray-700">
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

      {/* Current Role Field */}
      <div className="space-y-2">
        <Label
          htmlFor="currentRole"
          className="text-sm font-medium text-gray-700"
        >
          What is your current role?
        </Label>
        <div className="relative">
          <Briefcase className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
          <Input
            id="currentRole"
            type="text"
            placeholder="Senior Software Engineer"
            className={`pl-10 ${errors.currentRole ? "border-red-500" : ""}`}
            {...register("currentRole")}
          />
        </div>
        {errors.currentRole && (
          <p className="text-xs text-red-600 sm:text-sm">
            {errors.currentRole.message}
          </p>
        )}
      </div>

      {/* Current Company Field */}
      <div className="space-y-2">
        <Label
          htmlFor="currentCompany"
          className="text-sm font-medium text-gray-700"
        >
          Where do you currently work?
        </Label>
        <div className="relative">
          <Building2 className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
          <Input
            id="currentCompany"
            type="text"
            placeholder="Tech Corp"
            className={`pl-10 ${errors.currentCompany ? "border-red-500" : ""}`}
            {...register("currentCompany")}
          />
        </div>
        {errors.currentCompany && (
          <p className="text-xs text-red-600 sm:text-sm">
            {errors.currentCompany.message}
          </p>
        )}
      </div>

      {/* Submit Button */}
      <Button
        type="submit"
        disabled={
          !isValid ||
          !usernameValidation.isValid ||
          usernameValidation.isChecking
        }
        className="w-full"
        size="lg"
      >
        {usernameValidation.isChecking ? (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Checking...
          </>
        ) : (
          <>
            Continue
            <ArrowRight className="ml-2 h-5 w-5" />
          </>
        )}
      </Button>
    </form>
  );
}
