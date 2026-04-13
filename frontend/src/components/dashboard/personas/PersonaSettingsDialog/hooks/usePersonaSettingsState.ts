import { useState, useEffect } from "react";
import type {
  Persona,
  BasicInfoFormData,
  EmailCaptureSettings,
  CalendarSettings,
  SessionTimeLimitSettings,
  MonetizationSettings,
  PersonaLanguage,
} from "../types";
import {
  DEFAULT_EMAIL_THRESHOLD,
  DEFAULT_EMAIL_CAPTURE_REQUIRE_FULLNAME,
  DEFAULT_EMAIL_CAPTURE_REQUIRE_PHONE,
  DEFAULT_PRICE_CENTS,
  DEFAULT_SESSION_LIMIT_MINUTES,
  DEFAULT_SESSION_WARNING_MINUTES,
} from "../utils";
import { useGetPersonaMonetization } from "@/lib/queries/stripe";
import { formatPriceInput } from "../utils/formatting";

/**
 * Centralized state management for PersonaSettings Dialog
 * Replaces 30+ scattered useState hooks
 */
export function usePersonaSettingsState(persona: Persona) {
  // ===== BASIC INFO STATE =====
  const [basicInfo, setBasicInfo] = useState<BasicInfoFormData>({
    name: persona.name,
    role: persona.role,
    expertise: persona.expertise || "",
    description: persona.description || "",
    greetingMessage: persona.greeting_message || "",
  });

  // ===== VOICE STATE =====
  const [voiceId, setVoiceId] = useState<string | undefined>(persona.voice_id);
  const [voiceEnabled, setVoiceEnabled] = useState(
    persona.voice_enabled ?? true,
  );

  // ===== LANGUAGE STATE =====
  const [language, setLanguage] = useState<PersonaLanguage>(
    persona.language || "auto",
  );

  // ===== EMAIL CAPTURE STATE =====
  const [emailCapture, setEmailCapture] = useState<EmailCaptureSettings>({
    enabled: persona.email_capture_enabled ?? false,
    threshold:
      persona.email_capture_message_threshold ?? DEFAULT_EMAIL_THRESHOLD,
    requireFullname:
      persona.email_capture_require_fullname ??
      DEFAULT_EMAIL_CAPTURE_REQUIRE_FULLNAME,
    requirePhone:
      persona.email_capture_require_phone ??
      DEFAULT_EMAIL_CAPTURE_REQUIRE_PHONE,
    defaultLeadCaptureEnabled: persona.default_lead_capture_enabled ?? false,
  });

  // For numeric input display (separate from actual value)
  const [emailThresholdDisplay, setEmailThresholdDisplay] = useState(
    String(emailCapture.threshold),
  );

  // ===== CONVERSATION SUMMARY EMAIL STATE =====
  const [sendSummaryEmailEnabled, setSendSummaryEmailEnabled] = useState(
    persona.send_summary_email_enabled ?? true, // Default to true as per backend
  );

  // ===== CALENDAR STATE =====
  const [calendar, setCalendar] = useState<CalendarSettings>({
    enabled: persona.calendar_enabled ?? false,
    url: persona.calendar_url ?? "",
    displayName: persona.calendar_display_name ?? "",
  });

  const [calendarUrlError, setCalendarUrlError] = useState<string | null>(null);

  // ===== SESSION TIME LIMIT STATE =====
  const [sessionTimeLimit, setSessionTimeLimit] =
    useState<SessionTimeLimitSettings>({
      enabled: persona.session_time_limit_enabled ?? false,
      limitMinutes:
        persona.session_time_limit_minutes ?? DEFAULT_SESSION_LIMIT_MINUTES,
      warningMinutes:
        persona.session_time_limit_warning_minutes ??
        DEFAULT_SESSION_WARNING_MINUTES,
    });

  // ===== MONETIZATION STATE =====
  const [monetization, setMonetization] = useState<MonetizationSettings>({
    isActive: false,
    pricingModel: "one_time_lifetime",
    priceInCents: DEFAULT_PRICE_CENTS,
    accessDurationDays: null,
  });

  // For price input display (separate from cents)
  const [priceDisplay, setPriceDisplay] = useState(
    formatPriceInput(DEFAULT_PRICE_CENTS),
  );

  // Fetch monetization data from API
  const { data: monetizationData, isSuccess: isMonetizationDataLoaded } =
    useGetPersonaMonetization(persona.id);

  // ===== SYNC STATE WITH PERSONA PROP =====
  // Update state when persona prop changes
  useEffect(() => {
    setBasicInfo({
      name: persona.name,
      role: persona.role,
      expertise: persona.expertise || "",
      description: persona.description || "",
      greetingMessage: persona.greeting_message || "",
    });

    setVoiceId(persona.voice_id);
    setVoiceEnabled(persona.voice_enabled ?? true);

    setLanguage((prev) => {
      const next = persona.language || "auto";
      return next !== prev ? next : prev;
    });

    const threshold =
      persona.email_capture_message_threshold ?? DEFAULT_EMAIL_THRESHOLD;
    setEmailCapture({
      enabled: persona.email_capture_enabled ?? false,
      threshold,
      requireFullname:
        persona.email_capture_require_fullname ??
        DEFAULT_EMAIL_CAPTURE_REQUIRE_FULLNAME,
      requirePhone:
        persona.email_capture_require_phone ??
        DEFAULT_EMAIL_CAPTURE_REQUIRE_PHONE,
      defaultLeadCaptureEnabled: persona.default_lead_capture_enabled ?? false,
    });
    setEmailThresholdDisplay(String(threshold));

    setCalendar({
      enabled: persona.calendar_enabled ?? false,
      url: persona.calendar_url ?? "",
      displayName: persona.calendar_display_name ?? "",
    });

    setSessionTimeLimit({
      enabled: persona.session_time_limit_enabled ?? false,
      limitMinutes:
        persona.session_time_limit_minutes ?? DEFAULT_SESSION_LIMIT_MINUTES,
      warningMinutes:
        persona.session_time_limit_warning_minutes ??
        DEFAULT_SESSION_WARNING_MINUTES,
    });

    setSendSummaryEmailEnabled(persona.send_summary_email_enabled ?? true);
  }, [
    persona.language,
    persona.voice_id,
    persona.voice_enabled,
    persona.name,
    persona.role,
    persona.expertise,
    persona.description,
    persona.greeting_message,
    persona.email_capture_enabled,
    persona.email_capture_message_threshold,
    persona.email_capture_require_fullname,
    persona.email_capture_require_phone,
    persona.default_lead_capture_enabled,
    persona.calendar_enabled,
    persona.calendar_url,
    persona.calendar_display_name,
    persona.session_time_limit_enabled,
    persona.session_time_limit_minutes,
    persona.session_time_limit_warning_minutes,
    persona.send_summary_email_enabled,
  ]);

  // ===== SYNC MONETIZATION DATA FROM API =====
  useEffect(() => {
    if (monetizationData) {
      setMonetization({
        isActive: monetizationData.is_active ?? false,
        pricingModel: monetizationData.pricing_model,
        priceInCents: monetizationData.price_cents ?? DEFAULT_PRICE_CENTS,
        accessDurationDays: monetizationData.access_duration_days ?? null,
      });
      setPriceDisplay(
        formatPriceInput(monetizationData.price_cents ?? DEFAULT_PRICE_CENTS),
      );
    }
  }, [monetizationData]);

  // ===== UPDATE HELPERS =====
  // Type-safe update functions
  const updateBasicInfo = (updates: Partial<BasicInfoFormData>) => {
    setBasicInfo((prev) => ({ ...prev, ...updates }));
  };

  const updateEmailCapture = (updates: Partial<EmailCaptureSettings>) => {
    setEmailCapture((prev) => ({ ...prev, ...updates }));
  };

  const updateCalendar = (updates: Partial<CalendarSettings>) => {
    setCalendar((prev) => ({ ...prev, ...updates }));
  };

  const updateSessionTimeLimit = (
    updates: Partial<SessionTimeLimitSettings>,
  ) => {
    setSessionTimeLimit((prev) => ({ ...prev, ...updates }));
  };

  const updateMonetization = (updates: Partial<MonetizationSettings>) => {
    setMonetization((prev) => ({ ...prev, ...updates }));
  };

  // ===== RETURN INTERFACE =====
  return {
    // Basic info
    basicInfo,
    setBasicInfo,
    updateBasicInfo,

    // Voice
    voiceId,
    setVoiceId,
    voiceEnabled,
    setVoiceEnabled,

    // Language
    language,
    setLanguage,

    // Email capture
    emailCapture,
    setEmailCapture,
    updateEmailCapture,
    emailThresholdDisplay,
    setEmailThresholdDisplay,

    // Calendar
    calendar,
    setCalendar,
    updateCalendar,
    calendarUrlError,
    setCalendarUrlError,

    // Session Time Limit
    sessionTimeLimit,
    setSessionTimeLimit,
    updateSessionTimeLimit,

    // Monetization
    monetization,
    setMonetization,
    updateMonetization,
    priceDisplay,
    setPriceDisplay,
    monetizationData, // Pass through for Stripe connection status
    isMonetizationDataLoaded, // TRUE when API data loaded AND effect has run

    // Conversation Summary Email
    sendSummaryEmailEnabled,
    setSendSummaryEmailEnabled,
  };
}
