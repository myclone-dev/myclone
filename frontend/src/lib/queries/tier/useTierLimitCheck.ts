import { useUserUsage, useUserSubscription } from "./index";
import type { TierUsageResponse, UserSubscription } from "./interface";
import {
  isFreeTier,
  isPaidTier,
  isBusinessOrHigher,
  isEnterpriseTier,
} from "@/lib/constants/tiers";

export interface TierLimitCheckResult {
  // Loading states
  isLoading: boolean;

  // Usage data
  usage: TierUsageResponse | undefined;
  subscription: UserSubscription | undefined;

  // Document checks
  canUploadDocument: (fileSizeMB: number) => {
    allowed: boolean;
    reason?: string;
  };

  // Multimedia checks (audio/video)
  canUploadMultimedia: (
    fileSizeMB: number,
    durationHours?: number,
  ) => {
    allowed: boolean;
    reason?: string;
  };

  // YouTube checks
  canImportYouTubeVideo: (durationMinutes: number) => {
    allowed: boolean;
    reason?: string;
  };

  // YouTube access check (Pro+ only)
  canAccessYouTube: () => {
    allowed: boolean;
    reason?: string;
  };

  // Persona checks
  canCreatePersona: () => {
    allowed: boolean;
    reason?: string;
    current: number;
    limit: number;
  };

  // General checks
  hasReachedLimit: (
    category:
      | "documents"
      | "multimedia"
      | "youtube"
      | "personas"
      | "voice"
      | "text",
  ) => boolean;

  // Tier status helpers
  isFreeTier: boolean;
  isPaidTier: boolean;
  isBusinessOrHigher: boolean;
  isEnterprise: boolean;
  tierId: number | undefined;
  tierName: string | undefined;

  // Usage percentage helpers
  getUsagePercentage: (
    category:
      | "documents"
      | "multimedia"
      | "youtube"
      | "voice"
      | "text"
      | "personas",
  ) => number;

  // Voice and text specific checks
  canUseVoiceChat: () => {
    allowed: boolean;
    reason?: string;
    minutesRemaining: number;
  };

  canUseTextChat: () => {
    allowed: boolean;
    reason?: string;
    messagesRemaining: number;
  };
}

/**
 * Hook to check tier limits before upload/import
 * Returns validation functions for different upload types
 * Uses JWT authentication - no need to pass userId
 */
export const useTierLimitCheck = (): TierLimitCheckResult => {
  const { data: usage, isLoading: usageLoading } = useUserUsage();
  const { data: subscription, isLoading: subscriptionLoading } =
    useUserSubscription();

  const isLoading = usageLoading || subscriptionLoading;

  // Tier status helpers
  const tierId = subscription?.tier_id;
  const tierName = subscription?.tier_name;
  const isFree = isFreeTier(tierId);
  const isPaid = isPaidTier(tierId);
  const isBusiness = isBusinessOrHigher(tierId);
  const isEnterprise = isEnterpriseTier(tierId);

  // Check if user can upload a document
  const canUploadDocument = (
    fileSizeMB: number,
  ): { allowed: boolean; reason?: string } => {
    if (!usage) {
      return { allowed: false, reason: "Loading usage data..." };
    }

    // Check file count limit
    if (
      usage.documents.files.limit !== -1 &&
      usage.documents.files.used >= usage.documents.files.limit
    ) {
      return {
        allowed: false,
        reason: `Document file limit reached (${usage.documents.files.limit} files). Please upgrade your plan.`,
      };
    }

    // Check file size limit
    if (
      usage.documents.max_file_size_mb !== -1 &&
      fileSizeMB > usage.documents.max_file_size_mb
    ) {
      return {
        allowed: false,
        reason: `File size exceeds ${usage.documents.max_file_size_mb}MB limit. Please choose a smaller file or upgrade your plan.`,
      };
    }

    // Check storage limit
    if (
      usage.documents.storage.limit_mb !== -1 &&
      usage.documents.storage.used_mb + fileSizeMB >
        usage.documents.storage.limit_mb
    ) {
      const availableMB =
        usage.documents.storage.limit_mb - usage.documents.storage.used_mb;
      return {
        allowed: false,
        reason: `Not enough storage. Available: ${availableMB.toFixed(1)}MB, Required: ${fileSizeMB.toFixed(1)}MB. Please upgrade your plan.`,
      };
    }

    return { allowed: true };
  };

  // Check if user can upload multimedia (audio/video)
  const canUploadMultimedia = (
    fileSizeMB: number,
    durationHours: number = 0,
  ): { allowed: boolean; reason?: string } => {
    if (!usage) {
      return { allowed: false, reason: "Loading usage data..." };
    }

    // Check file count limit
    if (
      usage.multimedia.files.limit !== -1 &&
      usage.multimedia.files.used >= usage.multimedia.files.limit
    ) {
      return {
        allowed: false,
        reason: `Multimedia file limit reached (${usage.multimedia.files.limit} files). Please upgrade your plan.`,
      };
    }

    // Check file size limit
    if (
      usage.multimedia.max_file_size_mb !== -1 &&
      fileSizeMB > usage.multimedia.max_file_size_mb
    ) {
      return {
        allowed: false,
        reason: `File size exceeds ${usage.multimedia.max_file_size_mb}MB limit. Please choose a smaller file or upgrade your plan.`,
      };
    }

    // Check storage limit
    if (
      usage.multimedia.storage.limit_mb !== -1 &&
      usage.multimedia.storage.used_mb + fileSizeMB >
        usage.multimedia.storage.limit_mb
    ) {
      const availableMB =
        usage.multimedia.storage.limit_mb - usage.multimedia.storage.used_mb;
      return {
        allowed: false,
        reason: `Not enough storage. Available: ${availableMB.toFixed(1)}MB, Required: ${fileSizeMB.toFixed(1)}MB. Please upgrade your plan.`,
      };
    }

    // Check duration limit (if provided)
    if (durationHours > 0) {
      // Check soft limit
      if (
        usage.multimedia.duration.limit_hours !== -1 &&
        usage.multimedia.duration.used_hours + durationHours >
          usage.multimedia.duration.limit_hours
      ) {
        const availableHours =
          usage.multimedia.duration.limit_hours -
          usage.multimedia.duration.used_hours;
        return {
          allowed: false,
          reason: `Duration limit reached. Available: ${availableHours.toFixed(1)}h, Required: ${durationHours.toFixed(1)}h. Please upgrade your plan.`,
        };
      }

      // Check hard limit (applies to all tiers)
      if (
        usage.multimedia.duration.hard_limit_hours &&
        usage.multimedia.duration.used_hours + durationHours >
          usage.multimedia.duration.hard_limit_hours
      ) {
        return {
          allowed: false,
          reason: `Hard duration limit reached (${usage.multimedia.duration.hard_limit_hours}h total). This is a platform-wide limit.`,
        };
      }
    }

    return { allowed: true };
  };

  // Check if user can import a YouTube video
  const canImportYouTubeVideo = (
    durationMinutes: number,
  ): { allowed: boolean; reason?: string } => {
    if (!usage) {
      return { allowed: false, reason: "Loading usage data..." };
    }

    // Check video count limit
    if (
      usage.youtube.videos.limit !== -1 &&
      usage.youtube.videos.used >= usage.youtube.videos.limit
    ) {
      return {
        allowed: false,
        reason: `YouTube video limit reached (${usage.youtube.videos.limit} videos). Please upgrade your plan.`,
      };
    }

    // Check hard limit for video count (applies to all tiers)
    if (
      usage.youtube.videos.hard_limit &&
      usage.youtube.videos.used >= usage.youtube.videos.hard_limit
    ) {
      return {
        allowed: false,
        reason: `Hard video limit reached (${usage.youtube.videos.hard_limit} videos). This is a platform-wide limit.`,
      };
    }

    // Check individual video duration limit
    if (
      usage.youtube.max_video_duration_minutes !== -1 &&
      durationMinutes > usage.youtube.max_video_duration_minutes
    ) {
      return {
        allowed: false,
        reason: `Video duration exceeds ${usage.youtube.max_video_duration_minutes} minute limit. Please choose a shorter video or upgrade your plan.`,
      };
    }

    // Check hard limit for individual video duration
    if (
      usage.youtube.hard_limit_video_duration_minutes &&
      durationMinutes > usage.youtube.hard_limit_video_duration_minutes
    ) {
      return {
        allowed: false,
        reason: `Video duration exceeds hard limit (${usage.youtube.hard_limit_video_duration_minutes} minutes). This is a platform-wide limit.`,
      };
    }

    // Check total duration limit
    const durationHours = durationMinutes / 60;
    if (
      usage.youtube.duration.limit_hours !== -1 &&
      usage.youtube.duration.used_hours + durationHours >
        usage.youtube.duration.limit_hours
    ) {
      const availableHours =
        usage.youtube.duration.limit_hours - usage.youtube.duration.used_hours;
      return {
        allowed: false,
        reason: `Total duration limit reached. Available: ${availableHours.toFixed(1)}h, Required: ${durationHours.toFixed(1)}h. Please upgrade your plan.`,
      };
    }

    return { allowed: true };
  };

  // Check if user can access YouTube feature (Pro+ only)
  const canAccessYouTube = (): { allowed: boolean; reason?: string } => {
    // Free tier users cannot access YouTube import
    if (isFree) {
      return {
        allowed: false,
        reason:
          "YouTube import is a Pro feature. Upgrade to Pro to import YouTube videos.",
      };
    }

    return { allowed: true };
  };

  // Check if user can create a new persona
  const canCreatePersona = (): {
    allowed: boolean;
    reason?: string;
    current: number;
    limit: number;
  } => {
    if (!usage) {
      return {
        allowed: false,
        reason: "Loading usage data...",
        current: 0,
        limit: 0,
      };
    }

    // Handle case where personas field might not exist (older API response)
    if (!usage.personas) {
      return {
        allowed: true,
        current: 0,
        limit: -1,
      };
    }

    const { used, limit } = usage.personas;

    // -1 means unlimited
    if (limit === -1) {
      return {
        allowed: true,
        current: used,
        limit: limit,
      };
    }

    // Check if user has reached persona limit
    if (used >= limit) {
      return {
        allowed: false,
        reason: `Persona limit reached (${limit} personas). Please upgrade your plan to create more personas.`,
        current: used,
        limit: limit,
      };
    }

    return {
      allowed: true,
      current: used,
      limit: limit,
    };
  };

  // Check if user has reached the limit for a category
  const hasReachedLimit = (
    category:
      | "documents"
      | "multimedia"
      | "youtube"
      | "personas"
      | "voice"
      | "text",
  ): boolean => {
    if (!usage) return false;

    switch (category) {
      case "documents":
        return (
          usage.documents.files.limit !== -1 &&
          usage.documents.files.used >= usage.documents.files.limit
        );
      case "multimedia":
        return (
          usage.multimedia.files.limit !== -1 &&
          usage.multimedia.files.used >= usage.multimedia.files.limit
        );
      case "youtube":
        return (
          usage.youtube.videos.limit !== -1 &&
          usage.youtube.videos.used >= usage.youtube.videos.limit
        );
      case "personas":
        return (
          usage.personas &&
          usage.personas.limit !== -1 &&
          usage.personas.used >= usage.personas.limit
        );
      case "voice":
        return (
          usage.voice &&
          usage.voice.minutes_limit !== -1 &&
          usage.voice.minutes_used >= usage.voice.minutes_limit
        );
      case "text":
        return (
          usage.text &&
          usage.text.messages_limit !== -1 &&
          usage.text.messages_used >= usage.text.messages_limit
        );
      default:
        return false;
    }
  };

  // Get usage percentage for a category
  const getUsagePercentage = (
    category:
      | "documents"
      | "multimedia"
      | "youtube"
      | "voice"
      | "text"
      | "personas",
  ): number => {
    if (!usage) return 0;

    switch (category) {
      case "documents":
        return usage.documents.files.percentage || 0;
      case "multimedia":
        return usage.multimedia.files.percentage || 0;
      case "youtube":
        return usage.youtube.videos.percentage || 0;
      case "voice":
        return usage.voice?.percentage || 0;
      case "text":
        return usage.text?.percentage || 0;
      case "personas":
        return usage.personas?.percentage || 0;
      default:
        return 0;
    }
  };

  // Check if user can use voice chat
  const canUseVoiceChat = (): {
    allowed: boolean;
    reason?: string;
    minutesRemaining: number;
  } => {
    if (!usage?.voice) {
      return {
        allowed: true,
        minutesRemaining: -1,
      };
    }

    const { minutes_used, minutes_limit } = usage.voice;

    // -1 means unlimited
    if (minutes_limit === -1) {
      return {
        allowed: true,
        minutesRemaining: -1,
      };
    }

    const minutesRemaining = Math.max(0, minutes_limit - minutes_used);

    if (minutes_used >= minutes_limit) {
      return {
        allowed: false,
        reason: `Voice chat limit reached (${minutes_limit} minutes/month). Please upgrade your plan.`,
        minutesRemaining: 0,
      };
    }

    return {
      allowed: true,
      minutesRemaining,
    };
  };

  // Check if user can use text chat
  const canUseTextChat = (): {
    allowed: boolean;
    reason?: string;
    messagesRemaining: number;
  } => {
    if (!usage?.text) {
      return {
        allowed: true,
        messagesRemaining: -1,
      };
    }

    const { messages_used, messages_limit } = usage.text;

    // -1 means unlimited
    if (messages_limit === -1) {
      return {
        allowed: true,
        messagesRemaining: -1,
      };
    }

    const messagesRemaining = Math.max(0, messages_limit - messages_used);

    if (messages_used >= messages_limit) {
      return {
        allowed: false,
        reason: `Text chat limit reached (${messages_limit} messages/month). Please upgrade your plan.`,
        messagesRemaining: 0,
      };
    }

    return {
      allowed: true,
      messagesRemaining,
    };
  };

  return {
    isLoading,
    usage,
    subscription,
    canUploadDocument,
    canUploadMultimedia,
    canImportYouTubeVideo,
    canAccessYouTube,
    canCreatePersona,
    hasReachedLimit,
    // Tier status helpers
    isFreeTier: isFree,
    isPaidTier: isPaid,
    isBusinessOrHigher: isBusiness,
    isEnterprise,
    tierId,
    tierName,
    // Usage helpers
    getUsagePercentage,
    canUseVoiceChat,
    canUseTextChat,
  };
};
