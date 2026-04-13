/**
 * Fullpage Layout for White-Label Deployments
 * Mirrors the layout from /[username]/page.tsx for a consistent experience
 */

import React, { useEffect } from "react";
import { Sparkles } from "lucide-react";
import { useTranslation } from "../../i18n";
import { ExpertChatInterface } from "../../components/expert/ExpertChatInterface";

interface PersonaData {
  id?: string;
  name?: string;
  fullname?: string;
  role?: string;
  company?: string;
  avatar?: string;
  suggested_questions?: string[];
  email_capture_enabled?: boolean;
  email_capture_message_threshold?: number;
  email_capture_require_fullname?: boolean;
  email_capture_require_phone?: boolean;
  session_time_limit_enabled?: boolean;
  session_time_limit_minutes?: number;
  session_time_limit_warning_minutes?: number;
  calendar_display_name?: string | null;
}

interface EmbedFullpageProps {
  expertUsername: string;
  personaName?: string;
  widgetToken: string;
  persona?: PersonaData | null;
  primaryColor?: string;
  enableVoice?: boolean;
}

export const EmbedFullpage: React.FC<EmbedFullpageProps> = ({
  expertUsername,
  personaName,
  widgetToken,
  persona,
  // primaryColor can be used for future customization
  primaryColor: _primaryColor = "#6366f1",
  enableVoice = true,
}) => {
  const { t } = useTranslation();
  const displayName =
    persona?.fullname || persona?.name || `@${expertUsername}`;
  const avatarUrl = persona?.avatar;
  const fallbackInitial = displayName.charAt(0).toUpperCase();

  // Store widget token in sessionStorage for API client interceptor
  useEffect(() => {
    if (widgetToken) {
      sessionStorage.setItem("widget_token", widgetToken);
    }
  }, [widgetToken]);

  return (
    <div className="h-screen relative bg-white overflow-y-auto">
      {/* Video Background */}
      <div className="absolute inset-0 pointer-events-none">
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 w-full h-full object-cover opacity-30"
        >
          <source src="/wave-animation.mp4" type="video/mp4" />
        </video>
      </div>

      {/* Split Background Overlay - Top 60% peach-light, bottom 40% white */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute top-0 left-0 right-0 h-[60%]"
          style={{ backgroundColor: "#FFF4EB" }}
        />
        <div className="absolute bottom-0 left-0 right-0 h-[40%] bg-white" />
      </div>

      {/* Powered by - Bottom Right */}
      <div className="absolute bottom-4 right-4 z-20">
        <a
          href="/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-gray-500 hover:text-gray-700 transition-colors"
        >
          <span className="text-xs font-medium">Powered by</span>
          <img
            src="/myclone-logo.svg"
            alt="MyClone"
            className="h-5 w-auto"
            onError={(e) => {
              // Fallback if SVG doesn't load - show text instead
              e.currentTarget.style.display = "none";
              const parent = e.currentTarget.parentElement;
              if (parent) {
                const textSpan = document.createElement("span");
                textSpan.className = "text-xs font-semibold";
                textSpan.textContent = "MyClone";
                parent.appendChild(textSpan);
              }
            }}
          />
        </a>
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Profile Header */}
        <div className="flex flex-col items-center mb-6 space-y-4">
          {/* Avatar with AI Badge */}
          <div className="relative">
            <div
              className="w-24 h-24 md:w-28 md:h-28 rounded-full overflow-hidden border-4 border-white shadow-xl"
              style={{
                background: avatarUrl
                  ? "white"
                  : "linear-gradient(to bottom right, rgb(251 191 36), rgb(249 115 22))",
              }}
            >
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt={displayName}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                    const parent = e.currentTarget.parentElement;
                    if (parent) {
                      parent.style.background =
                        "linear-gradient(to bottom right, rgb(251 191 36), rgb(249 115 22))";
                      parent.innerHTML = `<span style="font-size: 2.5rem; font-weight: 600; color: white; display: flex; align-items: center; justify-content: center; height: 100%;">${fallbackInitial}</span>`;
                    }
                  }}
                />
              ) : (
                <span
                  style={{
                    fontSize: "2.5rem",
                    fontWeight: "600",
                    color: "white",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                  }}
                >
                  {fallbackInitial}
                </span>
              )}
            </div>
            {/* AI Badge */}
            <div
              className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full border-2 border-white shadow-lg flex items-center justify-center"
              style={{
                background:
                  "linear-gradient(to bottom right, rgb(251 191 36), rgb(249 115 22))",
              }}
            >
              <Sparkles className="w-4 h-4 text-white" fill="white" />
            </div>
          </div>

          {/* Name and Title */}
          <div className="text-center space-y-2">
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900">
              {displayName}
            </h1>
            {persona?.role && (
              <p className="text-gray-700 text-base md:text-lg font-medium">
                {persona.role}
                {persona.company && ` ${t("common.at")} ${persona.company}`}
              </p>
            )}

            {/* AI Badge Text */}
            <div className="flex items-center justify-center gap-2 pt-1">
              <div
                className="inline-flex items-center gap-2 text-sm font-semibold"
                style={{ color: "#B06B30" }}
              >
                <Sparkles className="w-4 h-4" />
                <span>{t("widget.aiPowered")}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Chat Interface */}
        <ExpertChatInterface
          username={expertUsername}
          personaName={personaName}
          expertName={displayName}
          avatarUrl={avatarUrl}
          widgetToken={widgetToken}
          suggestedQuestions={persona?.suggested_questions}
          emailCaptureEnabled={persona?.email_capture_enabled}
          emailCaptureThreshold={persona?.email_capture_message_threshold}
          emailCaptureRequireFullname={persona?.email_capture_require_fullname}
          emailCaptureRequirePhone={persona?.email_capture_require_phone}
          sessionTimeLimitEnabled={persona?.session_time_limit_enabled}
          sessionTimeLimitMinutes={persona?.session_time_limit_minutes}
          sessionTimeLimitWarningMinutes={
            persona?.session_time_limit_warning_minutes
          }
          enableVoice={enableVoice}
          calendarDisplayName={persona?.calendar_display_name ?? undefined}
        />
      </div>
    </div>
  );
};
