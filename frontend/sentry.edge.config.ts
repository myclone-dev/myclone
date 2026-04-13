import * as Sentry from "@sentry/nextjs";

// NOTE: Don't use @/env here - Sentry configs load before Next.js env validation
// Using process.env directly ensures Sentry initializes properly
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Set environment
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",

  // Adjust this value in production, or use tracesSampler for greater control
  tracesSampleRate:
    process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT === "production" ? 0.1 : 1.0,

  // Setting this option to true will print useful information to the console while you're setting up Sentry.
  debug: false,

  // Add custom tags
  initialScope: {
    tags: {
      app: "myclone-frontend",
      runtime: "edge",
    },
  },
});
