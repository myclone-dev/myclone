"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Globe, AtSign, ArrowRight, ArrowLeft, Linkedin } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const contactSchema = z.object({
  linkedinUrl: z
    .string()
    .optional()
    .refine(
      (val) =>
        !val ||
        val === "" ||
        /^https?:\/\/(www\.)?linkedin\.com\/(in|company)\/[a-zA-Z0-9_-]+\/?/.test(
          val,
        ),
      "Please enter a valid LinkedIn profile URL",
    ),
  websiteUrl: z
    .string()
    .optional()
    .refine(
      (val) => !val || val === "" || /^https?:\/\/.+\..+/.test(val),
      "Please enter a valid URL starting with http:// or https://",
    ),
  twitterUsername: z
    .string()
    .optional()
    .refine(
      (val) => !val || val === "" || /^@?[A-Za-z0-9_]{1,15}$/.test(val),
      "Please enter a valid Twitter username (1-15 characters)",
    ),
});

type ContactFormData = z.infer<typeof contactSchema>;

interface ContactStepProps {
  defaultValues?: ContactFormData;
  onNext: (data: ContactFormData) => void;
  onBack: () => void;
}

export function ContactStep({
  defaultValues,
  onNext,
  onBack,
}: ContactStepProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ContactFormData>({
    resolver: zodResolver(contactSchema),
    defaultValues: defaultValues || {
      linkedinUrl: "",
      websiteUrl: "",
      twitterUsername: "",
    },
    mode: "onChange",
  });

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-xl font-bold sm:text-2xl text-gray-900 mb-2">
          Add your social profiles
        </h2>
        <p className="text-gray-600">
          These are optional but help others connect with you
        </p>
      </div>

      {/* LinkedIn URL Field */}
      <div className="space-y-2">
        <Label
          htmlFor="linkedinUrl"
          className="text-sm font-medium text-gray-700"
        >
          LinkedIn Profile
          <span className="text-gray-400 font-normal ml-1">(Optional)</span>
        </Label>
        <div className="relative">
          <Linkedin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <Input
            id="linkedinUrl"
            type="url"
            placeholder="https://linkedin.com/in/yourprofile"
            className={`pl-10 ${errors.linkedinUrl ? "border-red-500" : ""}`}
            {...register("linkedinUrl")}
          />
        </div>
        {errors.linkedinUrl && (
          <p className="text-xs text-red-600 sm:text-sm">
            {errors.linkedinUrl.message}
          </p>
        )}
        <p className="text-xs text-gray-500">
          Your LinkedIn profile URL (e.g., linkedin.com/in/yourname)
        </p>
      </div>

      {/* Website URL Field */}
      <div className="space-y-2">
        <Label
          htmlFor="websiteUrl"
          className="text-sm font-medium text-gray-700"
        >
          Personal Website
          <span className="text-gray-400 font-normal ml-1">(Optional)</span>
        </Label>
        <div className="relative">
          <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <Input
            id="websiteUrl"
            type="url"
            placeholder="https://yourwebsite.com"
            className={`pl-10 ${errors.websiteUrl ? "border-red-500" : ""}`}
            {...register("websiteUrl")}
          />
        </div>
        {errors.websiteUrl && (
          <p className="text-xs text-red-600 sm:text-sm">
            {errors.websiteUrl.message}
          </p>
        )}
        <p className="text-xs text-gray-500">
          Share your portfolio, blog, or personal website
        </p>
      </div>

      {/* Twitter Username Field */}
      <div className="space-y-2">
        <Label
          htmlFor="twitterUsername"
          className="text-sm font-medium text-gray-700"
        >
          Twitter/X Username
          <span className="text-gray-400 font-normal ml-1">(Optional)</span>
        </Label>
        <div className="relative">
          <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <Input
            id="twitterUsername"
            type="text"
            placeholder="@yourusername"
            className={`pl-10 ${errors.twitterUsername ? "border-red-500" : ""}`}
            {...register("twitterUsername")}
          />
        </div>
        {errors.twitterUsername && (
          <p className="text-xs text-red-600 sm:text-sm">
            {errors.twitterUsername.message}
          </p>
        )}
        <p className="text-xs text-gray-500">
          Your Twitter/X handle without the @ symbol
        </p>
      </div>

      {/* Info Box */}
      <div className="bg-yellow-light border border-yellow-bright/30 rounded-lg p-4">
        <p className="text-sm text-gray-800">
          <strong>Why we ask:</strong> Adding your website and social profiles
          helps build trust with users who want to chat with you.
        </p>
      </div>

      {/* Navigation Buttons */}
      <div className="flex gap-3 pt-4">
        <Button type="button" variant="outline" onClick={onBack} size="lg">
          <ArrowLeft className="w-5 h-5 mr-2" />
          Back
        </Button>
        <Button type="submit" className="flex-1" size="lg">
          Continue
          <ArrowRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </form>
  );
}
