"use client";

import {
  User,
  Linkedin,
  Globe,
  AtSign,
  Edit2,
  Sparkles,
  ArrowLeft,
} from "lucide-react";
import { LoadingDots } from "@/components/ui/loading-spinner";
import { Button } from "@/components/ui/button";
import {
  extractTwitterUsername,
  type OnboardingData,
} from "@/lib/queries/expert";
import { env } from "@/env";

interface ReviewStepProps {
  data: OnboardingData;
  onEdit: (step: number) => void;
  onSubmit: () => void;
  onBack: () => void;
  isSubmitting: boolean;
}

export function ReviewStep({
  data,
  onEdit,
  onSubmit,
  onBack,
  isSubmitting,
}: ReviewStepProps) {
  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="text-center mb-6 sm:mb-8">
        <div className="w-14 h-14 sm:w-16 sm:h-16 mx-auto mb-3 sm:mb-4 rounded-full bg-primary flex items-center justify-center">
          <Sparkles className="w-7 h-7 sm:w-8 sm:h-8 text-primary-foreground" />
        </div>
        <h2 className="text-lg font-bold sm:text-2xl text-gray-900 mb-2">
          Review your profile
        </h2>
        <p className="text-sm sm:text-base text-gray-600 px-2">
          Make sure everything looks good before we create your expert profile
        </p>
      </div>

      {/* Profile Preview Card */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 sm:p-6 space-y-4 sm:space-y-6">
        {/* Username Section */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-0">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
              <User className="w-5 h-5 text-primary" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs sm:text-sm text-gray-500">Username</p>
              <p className="font-semibold text-sm sm:text-base text-gray-900 truncate">
                @{data.username}
              </p>
              <p className="text-xs text-gray-400 mt-0.5 truncate">
                {env.NEXT_PUBLIC_APP_URL}/{data.username}
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onEdit(1)}
            className="text-primary hover:text-primary hover:bg-primary/10 transition-colors shrink-0 h-8 px-2 sm:h-9 sm:px-3"
          >
            <Edit2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 sm:mr-1" />
            <span className="hidden sm:inline">Edit</span>
          </Button>
        </div>

        {/* Data Sources Section */}
        {data.linkedinUrl || data.websiteUrl || data.twitterUrl ? (
          <div className="flex items-start justify-between gap-2 pt-4 border-t border-gray-200">
            <div className="flex-1 space-y-3 min-w-0">
              <p className="text-xs sm:text-sm text-gray-500 font-medium mb-2">
                Connected Data Sources
              </p>
              {data.linkedinUrl && (
                <div className="flex items-center gap-2 sm:gap-3">
                  <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                    <Linkedin className="w-5 h-5 text-blue-600" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs sm:text-sm text-gray-500">
                      LinkedIn Profile
                    </p>
                    <p className="font-semibold text-sm sm:text-base text-gray-900 truncate">
                      {data.linkedinUrl}
                    </p>
                  </div>
                </div>
              )}
              {data.websiteUrl && (
                <div className="flex items-center gap-2 sm:gap-3">
                  <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center shrink-0">
                    <Globe className="w-5 h-5 text-orange-600" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs sm:text-sm text-gray-500">Website</p>
                    <p className="font-medium text-sm text-gray-900 truncate">
                      {data.websiteUrl}
                    </p>
                  </div>
                </div>
              )}

              {data.twitterUrl && (
                <div className="flex items-center gap-2 sm:gap-3">
                  <div className="w-10 h-10 rounded-full bg-sky-100 flex items-center justify-center shrink-0">
                    <AtSign className="w-5 h-5 text-sky-600" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs sm:text-sm text-gray-500">
                      Twitter/X
                    </p>
                    <p className="font-medium text-sm text-gray-900 truncate">
                      @{extractTwitterUsername(data.twitterUrl)}
                    </p>
                  </div>
                </div>
              )}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onEdit(1)}
              className="text-primary hover:text-primary hover:bg-primary/10 transition-colors shrink-0 h-8 px-2 sm:h-9 sm:px-3"
            >
              <Edit2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 sm:mr-1" />
              <span className="hidden sm:inline">Edit</span>
            </Button>
          </div>
        ) : (
          <div className="flex items-start justify-between gap-2 pt-4 border-t border-gray-200">
            <div className="flex-1">
              <p className="text-sm text-gray-600">
                No data sources connected. You can add them later from your
                dashboard to train your AI clone.
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onEdit(1)}
              className="text-primary hover:text-primary hover:bg-primary/10 transition-colors shrink-0 h-8 px-2 sm:h-9 sm:px-3"
            >
              <Edit2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 sm:mr-1" />
              <span className="hidden sm:inline">Add</span>
            </Button>
          </div>
        )}
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 sm:p-4">
        <p className="text-xs sm:text-sm text-blue-900 leading-relaxed">
          <strong className="font-semibold">What happens next?</strong> Your
          expert profile will be created and you&apos;ll be able to chat with
          users who need your expertise.{" "}
          {data.linkedinUrl &&
            "We'll also enrich your profile with data from LinkedIn."}
        </p>
      </div>

      {/* Navigation Buttons */}
      <div className="flex flex-col gap-2 sm:flex-row sm:gap-3 pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={onBack}
          disabled={isSubmitting}
          className="h-11 sm:h-12"
        >
          <ArrowLeft className="w-4 h-4 mr-2 sm:w-5 sm:h-5" />
          <span className="text-sm sm:text-base">Back</span>
        </Button>
        <Button
          type="button"
          onClick={onSubmit}
          disabled={isSubmitting}
          className="flex-1 h-11 sm:h-12 text-sm sm:text-base"
        >
          {isSubmitting ? (
            <>
              <LoadingDots className="mr-2" />
              <span className="text-sm sm:text-base">Creating Profile...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 mr-2 sm:w-5 sm:h-5" />
              <span className="text-sm sm:text-base">
                Create Expert Profile
              </span>
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
