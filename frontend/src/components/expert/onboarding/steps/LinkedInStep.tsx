"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { ArrowRight, ArrowLeft, Linkedin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchResultsSkeleton } from "@/components/ui/loading-state";
import { LinkedInProfileCard } from "../LinkedInProfileCard";
import type {
  LinkedInProfile,
  LinkedInSearchResult,
} from "@/lib/queries/expert";

const linkedInUrlSchema = z.object({
  linkedinUrl: z
    .string()
    .min(1, "LinkedIn URL is required")
    .refine(
      (val) =>
        /^https?:\/\/(www\.)?linkedin\.com\/in\/[a-zA-Z0-9-]+\/?$/.test(val),
      "Please enter a valid LinkedIn profile URL (e.g., https://linkedin.com/in/your-profile)",
    ),
});

type LinkedInUrlFormData = z.infer<typeof linkedInUrlSchema>;

interface LinkedInStepProps {
  searchResults: LinkedInSearchResult[];
  isSearching: boolean;
  selectedProfile: LinkedInProfile | null;
  onSelectProfile: (profile: LinkedInProfile) => void;
  onNext: () => void;
  onBack: () => void;
  onManualSubmit: (profile: LinkedInProfile) => void;
  currentRole: string;
  currentCompany: string;
  fullName: string;
}

export function LinkedInStep({
  searchResults,
  isSearching,
  selectedProfile,
  onSelectProfile,
  onNext,
  onBack,
  onManualSubmit,
  currentRole,
  currentCompany,
  fullName,
}: LinkedInStepProps) {
  const [showManualForm, setShowManualForm] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<LinkedInUrlFormData>({
    resolver: zodResolver(linkedInUrlSchema),
    defaultValues: {
      linkedinUrl: "",
    },
    mode: "onChange",
  });

  const handleManualSubmit = (data: LinkedInUrlFormData) => {
    const manualProfile: LinkedInProfile = {
      id: "manual",
      name: fullName,
      headline: `${currentRole} at ${currentCompany}`,
      profileUrl: data.linkedinUrl,
      avatarUrl: "",
      company: currentCompany,
      location: "Unknown",
    };
    onManualSubmit(manualProfile);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-blue-100 flex items-center justify-center">
          <Linkedin className="w-8 h-8 text-blue-600" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Connect your LinkedIn Profile
        </h2>
        <p className="text-gray-600">
          We found some profiles that might be you. Select the correct one.
        </p>
      </div>

      {/* Search Results */}
      {isSearching ? (
        <SearchResultsSkeleton count={3} />
      ) : searchResults.length > 0 ? (
        <div className="space-y-3">
          {searchResults.map((result, index) => {
            const profile: LinkedInProfile = {
              id: `profile-${index}`,
              name: result.name,
              headline: result.title,
              profileUrl: result.linkedin_url,
              avatarUrl: result.profile_picture_url || "",
              company: result.company || undefined,
              location: result.location,
            };

            return (
              <LinkedInProfileCard
                key={profile.id}
                profile={profile}
                isSelected={selectedProfile?.id === profile.id}
                onSelect={() => onSelectProfile(profile)}
                matchScore={result.similarity_score}
                index={index}
              />
            );
          })}
        </div>
      ) : (
        <div className="text-center py-8">
          <p className="text-gray-600 mb-4">
            No profiles found. Please enter your LinkedIn URL manually.
          </p>
        </div>
      )}

      {/* Manual LinkedIn URL Form */}
      {!isSearching && (
        <div className="border-t border-gray-200 pt-6">
          {!showManualForm ? (
            <button
              onClick={() => setShowManualForm(true)}
              className="w-full text-sm text-primary hover:text-primary/80 font-medium"
            >
              Can&apos;t find your profile? Enter LinkedIn URL manually
            </button>
          ) : (
            <form
              onSubmit={handleSubmit(handleManualSubmit)}
              className="space-y-4"
            >
              <div className="space-y-2">
                <Label
                  htmlFor="linkedinUrl"
                  className="text-sm font-medium text-gray-700"
                >
                  LinkedIn Profile URL
                </Label>
                <Input
                  id="linkedinUrl"
                  type="url"
                  placeholder="https://linkedin.com/in/your-profile"
                  className={errors.linkedinUrl ? "border-red-500" : ""}
                  {...register("linkedinUrl")}
                />
                {errors.linkedinUrl && (
                  <p className="text-sm text-red-600">
                    {errors.linkedinUrl.message}
                  </p>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowManualForm(false)}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={!isValid} className="flex-1">
                  Use This URL
                </Button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Navigation Buttons */}
      <div className="flex gap-3 pt-4">
        <Button type="button" variant="outline" onClick={onBack} size="lg">
          <ArrowLeft className="w-5 h-5 mr-2" />
          Back
        </Button>
        <Button
          type="button"
          onClick={onNext}
          disabled={!selectedProfile}
          className="flex-1"
          size="lg"
        >
          Continue
          <ArrowRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </div>
  );
}
