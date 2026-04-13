import * as Sentry from "@sentry/nextjs";

/**
 * Track user actions in dashboard for monitoring
 * Use this for critical user flows and feature interactions
 */
export const trackUserAction = (
  action: string,
  data?: Record<string, unknown>,
) => {
  Sentry.addBreadcrumb({
    category: "user-action",
    message: action,
    level: "info",
    data,
  });
};

/**
 * Track API operations with performance monitoring
 */
export const trackApiOperation = async <T>(
  operationName: string,
  operation: () => Promise<T>,
  metadata?: Record<string, string | number | boolean>,
): Promise<T> => {
  const transaction = Sentry.startInactiveSpan({
    name: operationName,
    op: "api.operation",
    attributes: metadata as Record<string, string | number | boolean>,
  });

  try {
    const result = await operation();
    transaction?.end();
    return result;
  } catch (error) {
    Sentry.captureException(error, {
      tags: {
        operation: operationName,
      },
      contexts: {
        operation: {
          name: operationName,
          ...metadata,
        },
      },
    });
    transaction?.end();
    throw error;
  }
};

/**
 * Track critical dashboard operations
 * Examples: Data source uploads, persona creation, widget generation
 */
export const trackDashboardOperation = (
  operation:
    | "linkedin_import"
    | "twitter_import"
    | "website_scrape"
    | "pdf_upload"
    | "batch_upload"
    | "raw_text_upload"
    | "widget_token_create"
    | "widget_token_revoke"
    | "widget_config_save"
    | "widget_config_delete"
    | "webhook_create"
    | "webhook_update"
    | "webhook_delete"
    | "persona_create"
    | "persona_update"
    | "persona_delete"
    | "persona_avatar_upload"
    | "persona_avatar_resize"
    | "persona_avatar_delete"
    | "profile_update"
    | "voice_clone_create"
    | "voice_clone_delete"
    | "conversation_view"
    | "persona_monetization_enable"
    | "persona_monetization_update"
    | "persona_monetization_disable"
    | "persona_monetization_toggle"
    | "persona_access_purchase"
    | "chat_config_generate"
    | "knowledge_source_delete"
    | "expert_onboarding"
    | "custom_domain_add"
    | "custom_domain_verify"
    | "custom_domain_delete"
    | "email_domain_create"
    | "email_domain_verify"
    | "email_domain_delete"
    | "stripe_connect_onboard"
    | "stripe_connect_dashboard"
    | "stripe_connect_complete"
    | "stripe_connect_refresh"
    | "workflow_template_enable"
    | "workflow_create"
    | "workflow_update"
    | "workflow_delete",
  status: "started" | "success" | "error",
  metadata?: Record<string, unknown>,
) => {
  const message = `${operation}_${status}`;

  if (status === "error") {
    Sentry.captureMessage(message, {
      level: "error",
      tags: {
        dashboard_operation: operation,
        operation_status: status,
      },
      contexts: {
        operation: {
          type: operation,
          status,
          ...metadata,
        },
      },
    });
  } else {
    Sentry.addBreadcrumb({
      category: "dashboard",
      message,
      level: status === "success" ? "info" : "debug",
      data: {
        operation,
        status,
        ...metadata,
      },
    });
  }
};

/**
 * Set user context for better error tracking
 */
export const setUserContext = (user: {
  id?: string;
  email?: string;
  username?: string;
}) => {
  Sentry.setUser({
    id: user.id,
    email: user.email,
    username: user.username,
  });
};

/**
 * Clear user context on logout
 */
export const clearUserContext = () => {
  Sentry.setUser(null);
};

/**
 * Track form submissions and validation errors
 */
export const trackFormEvent = (
  formName: string,
  event: "submit" | "validation_error" | "success",
  errors?: Record<string, unknown>,
) => {
  Sentry.addBreadcrumb({
    category: "form",
    message: `${formName}_${event}`,
    level: event === "validation_error" ? "warning" : "info",
    data: {
      form: formName,
      event,
      errors,
    },
  });
};

/**
 * Track file upload operations
 */
export const trackFileUpload = (
  fileType: "pdf" | "audio" | "image" | "avatar" | "attachment",
  status: "started" | "progress" | "success" | "error",
  metadata?: {
    fileName?: string;
    fileSize?: number;
    fileType?: string;
    progress?: number;
    error?: string;
    extractionStatus?: string;
    action?: string;
  },
) => {
  const level = status === "error" ? "error" : "info";

  Sentry.addBreadcrumb({
    category: "file-upload",
    message: `${fileType}_upload_${status}`,
    level,
    data: {
      fileType,
      status,
      ...metadata,
    },
  });

  if (status === "error" && metadata?.error) {
    Sentry.captureMessage(`File upload failed: ${metadata.error}`, {
      level: "error",
      tags: {
        file_type: fileType,
        upload_status: status,
      },
      contexts: {
        upload: {
          fileType,
          ...metadata,
        },
      },
    });
  }
};

/**
 * Track LiveKit voice/video session events
 */
export const trackLiveKitEvent = (
  event:
    | "session_start"
    | "session_end"
    | "session_connected"
    | "session_init_error"
    | "connection_error"
    | "audio_track_subscribed"
    | "video_track_subscribed"
    | "voice_limit_exceeded"
    | "voice_limit_exceeded_mid_call"
    // Inactivity timeout events
    | "inactivity_warning_shown"
    | "inactivity_warning_dismissed"
    | "session_disconnected_inactivity"
    | "session_ended_manual"
    | "session_reconnect_attempt"
    | "session_reconnect_success"
    // Session time limit events
    | "session_time_limit_warning_shown"
    | "session_time_limit_warning_dismissed"
    | "session_time_limit_reached"
    | "session_new_after_time_limit",
  metadata?: Record<string, unknown>,
) => {
  const isError =
    event === "connection_error" || event === "session_init_error";
  const isVoiceLimitEvent =
    event === "voice_limit_exceeded" ||
    event === "voice_limit_exceeded_mid_call";
  const isInactivityEvent =
    event === "inactivity_warning_shown" ||
    event === "inactivity_warning_dismissed" ||
    event === "session_disconnected_inactivity" ||
    event === "session_ended_manual";
  const isSessionTimeLimitEvent =
    event === "session_time_limit_warning_shown" ||
    event === "session_time_limit_warning_dismissed" ||
    event === "session_time_limit_reached" ||
    event === "session_new_after_time_limit";
  const level = isError
    ? "error"
    : isVoiceLimitEvent || isInactivityEvent || isSessionTimeLimitEvent
      ? "warning"
      : "info";

  Sentry.addBreadcrumb({
    category: "livekit",
    message: event,
    level,
    data: metadata,
  });

  if (isError) {
    Sentry.captureMessage(`LiveKit ${event.replace(/_/g, " ")}`, {
      level: "error",
      tags: {
        livekit_event: event,
      },
      contexts: {
        livekit: metadata,
      },
    });
  }

  // Capture voice limit events as warnings for tracking
  if (isVoiceLimitEvent) {
    Sentry.captureMessage(`Voice limit: ${event.replace(/_/g, " ")}`, {
      level: "warning",
      tags: {
        livekit_event: event,
        voice_limit: "exceeded",
      },
      contexts: {
        voice_usage: metadata,
      },
    });
  }

  // Capture inactivity events as warnings for tracking session management
  if (isInactivityEvent) {
    Sentry.captureMessage(`Session: ${event.replace(/_/g, " ")}`, {
      level: "warning",
      tags: {
        livekit_event: event,
        session_event: "inactivity",
      },
      contexts: {
        session_info: metadata,
      },
    });
  }
};

/**
 * Track voice usage events for monitoring quota consumption
 * Use this for tracking voice minutes usage and quota warnings
 */
export const trackVoiceUsageEvent = (
  event:
    | "usage_checked"
    | "usage_warning_75"
    | "usage_warning_90"
    | "quota_near_limit"
    | "heartbeat_sent"
    | "heartbeat_failed"
    | "session_started"
    | "session_ended"
    | "session_duration_updated",
  metadata?: {
    minutesUsed?: number;
    minutesLimit?: number;
    percentage?: number;
    sessionId?: string;
    durationSeconds?: number;
    personaId?: string;
    personaName?: string;
    username?: string;
    error?: string;
  },
) => {
  const isWarning =
    event === "usage_warning_75" ||
    event === "usage_warning_90" ||
    event === "quota_near_limit";
  const isError = event === "heartbeat_failed";
  const level = isError ? "error" : isWarning ? "warning" : "info";

  Sentry.addBreadcrumb({
    category: "voice-usage",
    message: event,
    level,
    data: metadata,
  });

  // Capture warnings for usage threshold events
  if (isWarning && metadata?.percentage) {
    Sentry.captureMessage(`Voice usage at ${metadata.percentage}%`, {
      level: "warning",
      tags: {
        voice_usage_event: event,
        usage_percentage: String(Math.round(metadata.percentage)),
      },
      contexts: {
        voice_usage: {
          minutes_used: metadata.minutesUsed,
          minutes_limit: metadata.minutesLimit,
          percentage: metadata.percentage,
        },
      },
    });
  }

  if (isError) {
    Sentry.captureMessage(
      `Voice heartbeat failed: ${metadata?.error || "Unknown"}`,
      {
        level: "error",
        tags: {
          voice_usage_event: event,
        },
        contexts: {
          voice_session: metadata,
        },
      },
    );
  }
};

/**
 * Track text chat usage events for monitoring quota consumption
 * Use this for tracking message count usage and quota warnings
 */
export const trackTextUsageEvent = (
  event:
    | "usage_checked"
    | "usage_warning_75"
    | "usage_warning_90"
    | "quota_near_limit"
    | "message_sent"
    | "limit_exceeded",
  metadata?: {
    messagesUsed?: number;
    messagesLimit?: number;
    percentage?: number;
    personaId?: string;
    personaName?: string;
    username?: string;
    error?: string;
  },
) => {
  const isWarning =
    event === "usage_warning_75" ||
    event === "usage_warning_90" ||
    event === "quota_near_limit";
  const isError = event === "limit_exceeded";
  const level = isError ? "error" : isWarning ? "warning" : "info";

  Sentry.addBreadcrumb({
    category: "text-usage",
    message: event,
    level,
    data: metadata,
  });

  // Capture warnings for usage threshold events
  if (isWarning && metadata?.percentage) {
    Sentry.captureMessage(`Text chat usage at ${metadata.percentage}%`, {
      level: "warning",
      tags: {
        text_usage_event: event,
        usage_percentage: String(Math.round(metadata.percentage)),
      },
      contexts: {
        text_usage: {
          messages_used: metadata.messagesUsed,
          messages_limit: metadata.messagesLimit,
          percentage: metadata.percentage,
        },
      },
    });
  }

  if (isError) {
    Sentry.captureMessage(
      `Text chat limit exceeded: ${metadata?.error || "Monthly quota reached"}`,
      {
        level: "warning",
        tags: {
          text_usage_event: event,
        },
        contexts: {
          text_usage: metadata,
        },
      },
    );
  }
};
