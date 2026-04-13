import { createEnv } from "@t3-oss/env-nextjs";
import { z } from "zod";

/**
 * Create base env with t3-env validation
 */
const baseEnv = createEnv({
  server: {
    NODE_ENV: z.enum(["development", "test", "production"]),
    SENTRY_AUTH_TOKEN: z.string().optional(),
    SENTRY_ORG: z.string().optional(),
    SENTRY_PROJECT: z.string().optional(),
    SLACK_WEBHOOK_URL: z.string().url().optional(),
  },

  client: {
    NEXT_PUBLIC_API_URL: z.string().url(),
    NEXT_PUBLIC_APP_URL: z.string().url(),
    NEXT_PUBLIC_LANDING_PAGE_URL: z.string().url().optional(),
    NEXT_PUBLIC_API_KEY: z.string().optional(),
    NEXT_PUBLIC_LIVEKIT_URL: z.string().url().optional(),
    NEXT_PUBLIC_POSTHOG_KEY: z.string().optional(),
    NEXT_PUBLIC_POSTHOG_HOST: z.string().url().optional(),
    NEXT_PUBLIC_GA_MEASUREMENT_ID: z.string().optional(),
    NEXT_PUBLIC_SENTRY_DSN: z.string().url().optional(),
    NEXT_PUBLIC_SENTRY_ENVIRONMENT: z
      .enum(["development", "staging", "production"])
      .optional(),
  },

  runtimeEnv: {
    NODE_ENV: process.env.NODE_ENV,
    SENTRY_AUTH_TOKEN: process.env.SENTRY_AUTH_TOKEN,
    SENTRY_ORG: process.env.SENTRY_ORG,
    SENTRY_PROJECT: process.env.SENTRY_PROJECT,
    SLACK_WEBHOOK_URL: process.env.SLACK_WEBHOOK_URL,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
    NEXT_PUBLIC_LANDING_PAGE_URL: process.env.NEXT_PUBLIC_LANDING_PAGE_URL,
    NEXT_PUBLIC_API_KEY: process.env.NEXT_PUBLIC_API_KEY || "",
    NEXT_PUBLIC_LIVEKIT_URL: process.env.NEXT_PUBLIC_LIVEKIT_URL,
    NEXT_PUBLIC_POSTHOG_KEY: process.env.NEXT_PUBLIC_POSTHOG_KEY,
    NEXT_PUBLIC_POSTHOG_HOST: process.env.NEXT_PUBLIC_POSTHOG_HOST,
    NEXT_PUBLIC_GA_MEASUREMENT_ID: process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID,
    NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
    NEXT_PUBLIC_SENTRY_ENVIRONMENT: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
  },

  skipValidation: !!process.env.SKIP_ENV_VALIDATION,
  emptyStringAsUndefined: true,
});

/**
 * Export env with dynamic getters for embed context
 * If running in embed iframe, check window globals first
 */
export const env = {
  ...baseEnv,

  // Override with dynamic getters for embed support
  get NEXT_PUBLIC_API_URL() {
    if (typeof window !== "undefined") {
      const embedUrl = (window as { EMBED_API_URL?: string }).EMBED_API_URL;
      if (embedUrl) return embedUrl;
    }
    return baseEnv.NEXT_PUBLIC_API_URL;
  },

  get NEXT_PUBLIC_LIVEKIT_URL() {
    if (typeof window !== "undefined") {
      const embedUrl = (window as { EMBED_LIVEKIT_URL?: string })
        .EMBED_LIVEKIT_URL;
      if (embedUrl) return embedUrl;
    }
    return baseEnv.NEXT_PUBLIC_LIVEKIT_URL;
  },
};
