"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  Linkedin,
  Globe,
  AtSign,
  ArrowRight,
  ArrowLeft,
  Info,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const dataSourcesSchema = z.object({
  linkedinUrl: z
    .string()
    .optional()
    .refine(
      (val) =>
        !val ||
        val === "" ||
        /^https?:\/\/(www\.)?linkedin\.com\/in\/[a-zA-Z0-9-]+\/?$/.test(val),
      "Please enter a valid LinkedIn profile URL (e.g., https://linkedin.com/in/username)",
    ),
  websiteUrl: z
    .string()
    .optional()
    .refine(
      (val) => !val || val === "" || /^https?:\/\/.+\..+/.test(val),
      "Please enter a valid URL starting with http:// or https://",
    ),
  twitterUrl: z
    .string()
    .optional()
    .refine(
      (val) =>
        !val ||
        val === "" ||
        /^https?:\/\/(?:www\.)?(?:twitter\.com|x\.com)\/[A-Za-z0-9_]{1,15}\/?(?:\?.*)?$/.test(
          val,
        ),
      "Please enter a valid Twitter/X profile URL (e.g., https://x.com/username)",
    ),
});

type DataSourcesFormData = z.infer<typeof dataSourcesSchema>;

interface DataSourcesStepProps {
  defaultValues?: Partial<DataSourcesFormData>;
  onNext: (data: DataSourcesFormData) => void;
  onBack: () => void;
}

export function DataSourcesStep({
  defaultValues,
  onNext,
  onBack,
}: DataSourcesStepProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<DataSourcesFormData>({
    resolver: zodResolver(dataSourcesSchema),
    defaultValues: defaultValues || {
      linkedinUrl: "",
      websiteUrl: "",
      twitterUrl: "",
    },
    mode: "onChange",
  });

  // Watch all fields to show validation message
  const linkedinUrl = watch("linkedinUrl");
  const websiteUrl = watch("websiteUrl");
  const twitterUrl = watch("twitterUrl");

  const hasAnyValue =
    (linkedinUrl && linkedinUrl.length > 0) ||
    (websiteUrl && websiteUrl.length > 0) ||
    (twitterUrl && twitterUrl.length > 0);

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Connect Your Data Sources
        </h2>
        <p className="text-gray-600 mb-2">
          Add data sources to train your AI clone (optional)
        </p>
        <p className="text-sm text-gray-500 italic">
          You can skip this for now and add sources later from your dashboard
        </p>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex gap-3">
        <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-900">
          <p className="font-medium mb-1">How this works</p>
          <p className="text-blue-800">
            We&apos;ll scrape your public profiles to train your AI clone. This
            process runs in the background and typically takes 5-15 minutes.
            You&apos;ll be able to use your clone once the training is complete.
          </p>
        </div>
      </div>

      {/* LinkedIn URL Field */}
      <div className="space-y-2">
        <Label
          htmlFor="linkedinUrl"
          className="text-sm font-medium text-gray-700 flex items-center gap-2"
        >
          <Linkedin className="w-4 h-4 text-[#0A66C2]" />
          LinkedIn Profile
          <span className="text-gray-400 font-normal text-xs">(Optional)</span>
        </Label>
        <div className="relative">
          <Input
            id="linkedinUrl"
            type="url"
            placeholder="https://linkedin.com/in/yourusername"
            className={`${errors.linkedinUrl ? "border-red-500" : ""}`}
            {...register("linkedinUrl")}
          />
        </div>
        {errors.linkedinUrl && (
          <p className="text-sm text-red-600">{errors.linkedinUrl.message}</p>
        )}
        <p className="text-xs text-gray-500">
          We&apos;ll import your work experience, skills, and professional
          background
        </p>
      </div>

      {/* Website URL Field */}
      <div className="space-y-2">
        <Label
          htmlFor="websiteUrl"
          className="text-sm font-medium text-gray-700 flex items-center gap-2"
        >
          <Globe className="w-4 h-4 text-gray-600" />
          Personal Website
          <span className="text-gray-400 font-normal text-xs">(Optional)</span>
        </Label>
        <div className="relative">
          <Input
            id="websiteUrl"
            type="url"
            placeholder="https://yourwebsite.com"
            className={`${errors.websiteUrl ? "border-red-500" : ""}`}
            {...register("websiteUrl")}
          />
        </div>
        {errors.websiteUrl && (
          <p className="text-sm text-red-600">{errors.websiteUrl.message}</p>
        )}
        <p className="text-xs text-gray-500">
          We&apos;ll scrape content from your portfolio, blog, or personal
          website
        </p>
      </div>

      {/* Twitter/X URL Field */}
      <div className="space-y-2">
        <Label
          htmlFor="twitterUrl"
          className="text-sm font-medium text-gray-700 flex items-center gap-2"
        >
          <AtSign className="w-4 h-4 text-gray-600" />
          Twitter/X Profile
          <span className="text-gray-400 font-normal text-xs">(Optional)</span>
        </Label>
        <div className="relative">
          <Input
            id="twitterUrl"
            type="url"
            placeholder="https://x.com/yourusername"
            className={`${errors.twitterUrl ? "border-red-500" : ""}`}
            {...register("twitterUrl")}
          />
        </div>
        {errors.twitterUrl && (
          <p className="text-sm text-red-600">{errors.twitterUrl.message}</p>
        )}
        <p className="text-xs text-gray-500">
          We&apos;ll import your tweets and engagement to understand your voice
        </p>
      </div>

      {/* Status message */}
      {!hasAnyValue ? (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-900 font-medium flex items-center gap-2">
            <Info className="w-5 h-5 flex-shrink-0" />
            <span>
              You can skip adding data sources now and complete your profile
              setup. Add them later from your dashboard to train your AI clone.
            </span>
          </p>
        </div>
      ) : (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-sm text-green-800 font-medium flex items-center gap-2">
            <svg
              className="w-5 h-5 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
            Great! You&apos;ve added{" "}
            {
              [linkedinUrl, websiteUrl, twitterUrl].filter(
                (v) => v && v.length > 0,
              ).length
            }{" "}
            data source(s)
          </p>
        </div>
      )}

      {/* Navigation Buttons */}
      <div className="flex gap-3 pt-4">
        <Button type="button" variant="outline" onClick={onBack} size="lg">
          <ArrowLeft className="w-5 h-5 mr-2" />
          Back
        </Button>
        <Button type="submit" className="flex-1" size="lg">
          {!hasAnyValue ? "Skip for now" : "Continue"}
          <ArrowRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </form>
  );
}
