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

  // Ignore common errors that don't need tracking
  ignoreErrors: [
    // Generic error messages
    "ECONNREFUSED",
    "ETIMEDOUT",
    "ENOTFOUND",
  ],

  // Add custom tags
  initialScope: {
    tags: {
      app: "myclone-frontend",
      runtime: "server",
    },
  },

  // Configure Slack webhook integration
  beforeSend(event) {
    // Send critical errors to Slack
    if (process.env.SLACK_WEBHOOK_URL && event.level === "error") {
      // Fire and forget - don't block error reporting
      fetch(process.env.SLACK_WEBHOOK_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: `🚨 Error in ${process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development"}`,
          blocks: [
            {
              type: "header",
              text: {
                type: "plain_text",
                text: `🚨 ${event.exception?.values?.[0]?.type || "Error"} in ${process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development"}`,
              },
            },
            {
              type: "section",
              text: {
                type: "mrkdwn",
                text: `*Message:* ${event.exception?.values?.[0]?.value || event.message || "Unknown error"}\n*Environment:* ${event.environment}\n*Event ID:* ${event.event_id}`,
              },
            },
            {
              type: "section",
              fields: [
                {
                  type: "mrkdwn",
                  text: `*Level:* ${event.level}`,
                },
                {
                  type: "mrkdwn",
                  text: `*Platform:* ${event.platform}`,
                },
              ],
            },
            ...(event.request?.url
              ? [
                  {
                    type: "section",
                    text: {
                      type: "mrkdwn",
                      text: `*URL:* ${event.request.url}`,
                    },
                  },
                ]
              : []),
          ],
        }),
      }).catch((error) => {
        console.error("Failed to send Slack notification:", error);
      });
    }

    return event;
  },
});
