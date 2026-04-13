"use client";

import { motion } from "framer-motion";
import { Check, MapPin, Briefcase } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { LinkedInProfile } from "@/lib/queries/expert";

interface LinkedInProfileCardProps {
  profile: LinkedInProfile;
  isSelected: boolean;
  onSelect: () => void;
  matchScore?: number;
  index?: number;
}

export function LinkedInProfileCard({
  profile,
  isSelected,
  onSelect,
  matchScore,
  index = 0,
}: LinkedInProfileCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
    >
      <button
        onClick={onSelect}
        className={`w-full p-3 sm:p-4 rounded-xl border-2 transition-all duration-200 text-left ${
          isSelected
            ? "border-primary bg-yellow-light"
            : "border-gray-200 hover:border-primary/50 bg-white hover:bg-yellow-light/30"
        }`}
      >
        <div className="flex items-start gap-3 sm:gap-3 sm:p-4">
          {/* Avatar */}
          <Avatar className="w-12 h-12 sm:w-16 sm:h-16 border-2 border-white shadow-sm">
            <AvatarImage src={profile.avatarUrl} alt={profile.name} />
            <AvatarFallback className="bg-primary text-primary-foreground text-lg">
              {profile.name.charAt(0).toUpperCase()}
            </AvatarFallback>
          </Avatar>

          {/* Profile Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-gray-900 truncate">
                  {profile.name}
                </h3>
                <p className="text-sm text-gray-600 line-clamp-2 mt-0.5">
                  {profile.headline}
                </p>
              </div>

              {/* Match Score Badge */}
              {matchScore !== undefined && (
                <div className="flex-shrink-0">
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                    {Math.round(matchScore * 100)}% match
                  </span>
                </div>
              )}
            </div>

            {/* Company & Location */}
            <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-gray-500">
              {profile.company && (
                <div className="flex items-center gap-1">
                  <Briefcase className="w-3.5 h-3.5" />
                  <span>{profile.company}</span>
                </div>
              )}
              {profile.location && (
                <div className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" />
                  <span>{profile.location}</span>
                </div>
              )}
            </div>
          </div>

          {/* Selection Indicator */}
          {isSelected && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="flex-shrink-0"
            >
              <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center">
                <Check className="w-4 h-4 text-primary-foreground" />
              </div>
            </motion.div>
          )}
        </div>

        {/* View Profile Link */}
        <div className="mt-3 pt-3 border-t border-gray-200">
          <span className="text-xs text-primary hover:text-primary/80 font-medium">
            View LinkedIn Profile →
          </span>
        </div>
      </button>
    </motion.div>
  );
}
