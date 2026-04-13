/**
 * Email Prompt Component
 * Appears after user sends N messages to capture their email
 */

import React, { useState } from "react";
import { useTranslation } from "../../i18n";

interface EmbedEmailPromptProps {
  onSubmit: (email: string) => void;
  onDismiss: () => void;
  isLoading?: boolean;
}

export const EmbedEmailPrompt: React.FC<EmbedEmailPromptProps> = ({
  onSubmit,
  onDismiss,
  isLoading = false,
}) => {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");

  const validateEmail = (email: string): boolean => {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!email.trim()) {
      setError(t("email.prompt.errors.required"));
      return;
    }

    if (!validateEmail(email)) {
      setError(t("email.prompt.errors.invalid"));
      return;
    }

    onSubmit(email);
  };

  return (
    <div className="embed-email-overlay">
      <div className="embed-email-prompt">
        <button
          className="embed-email-close"
          onClick={onDismiss}
          aria-label={t("common.close")}
        >
          ✕
        </button>

        <div className="embed-email-icon">📧</div>

        <h3 className="embed-email-title">{t("email.prompt.title")}</h3>
        <p className="embed-email-description">
          {t("email.prompt.description")}
        </p>

        <form onSubmit={handleSubmit} className="embed-email-form">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("email.prompt.placeholder")}
            className="embed-email-input"
            disabled={isLoading}
            autoFocus
          />

          {error && <div className="embed-email-error">{error}</div>}

          <button
            type="submit"
            className="embed-email-submit"
            disabled={isLoading}
          >
            {isLoading
              ? t("email.prompt.submitting")
              : t("email.prompt.submit")}
          </button>
        </form>

        <button className="embed-email-skip" onClick={onDismiss}>
          {t("email.prompt.skip")}
        </button>
      </div>
    </div>
  );
};
