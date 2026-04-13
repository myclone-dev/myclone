"use client";

import { motion } from "motion/react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  MessagesSquare,
  Hash,
  UserCircle,
  Phone,
  ShieldCheck,
  Mail,
  Loader2,
  Bot,
  Info,
  AlertTriangle,
} from "lucide-react";
import { useToggleSummaryEmail } from "@/lib/queries/persona";
import type { EmailCaptureSettings } from "../../types";

interface EmailCaptureTabProps {
  personaId: string;
  emailCapture: EmailCaptureSettings;
  onChange: (updates: Partial<EmailCaptureSettings>) => void;
  emailThresholdDisplay: string;
  setEmailThresholdDisplay: (value: string) => void;
  sendSummaryEmailEnabled: boolean;
  onSummaryEmailChange: (enabled: boolean) => void;
}

/**
 * Email Capture Tab
 * Configure when and how to collect visitor contact information
 * Also includes conversation summary email toggle
 */
export function EmailCaptureTab({
  personaId,
  emailCapture,
  onChange,
  emailThresholdDisplay,
  setEmailThresholdDisplay,
  sendSummaryEmailEnabled,
  onSummaryEmailChange,
}: EmailCaptureTabProps) {
  const toggleSummaryEmail = useToggleSummaryEmail();

  const handleSummaryEmailToggle = async (enabled: boolean) => {
    // Optimistically update UI
    onSummaryEmailChange(enabled);

    try {
      await toggleSummaryEmail.mutateAsync({ personaId, enabled });
      toast.success(
        enabled
          ? "Conversation summary emails enabled"
          : "Conversation summary emails disabled",
      );
    } catch {
      // Revert on error
      onSummaryEmailChange(!enabled);
      toast.error("Failed to update summary email setting");
    }
  };

  // Mutual exclusivity: enabling one lead capture method disables the other
  const handlePopupCaptureToggle = (checked: boolean) => {
    if (checked && emailCapture.defaultLeadCaptureEnabled) {
      // Enabling popup → disable conversational
      onChange({ enabled: true, defaultLeadCaptureEnabled: false });
      toast.info("Conversational lead capture has been disabled", {
        description:
          "Only one lead capture method can be active at a time. Popup email capture will be used instead.",
      });
    } else {
      onChange({ enabled: checked });
    }
  };

  const handleConversationalCaptureToggle = (checked: boolean) => {
    if (checked && emailCapture.enabled) {
      // Enabling conversational → disable popup
      onChange({ defaultLeadCaptureEnabled: true, enabled: false });
      toast.info("Popup email capture has been disabled", {
        description:
          "Only one lead capture method can be active at a time. Conversational lead capture will be used instead.",
      });
    } else {
      onChange({ defaultLeadCaptureEnabled: checked });
    }
  };

  const handleThresholdChange = (value: string) => {
    // Allow empty or 1-2 digit numbers
    if (value === "" || /^\d{0,2}$/.test(value)) {
      setEmailThresholdDisplay(value);
    }
  };

  const handleThresholdBlur = () => {
    const num = parseInt(emailThresholdDisplay);
    if (isNaN(num) || num < 1 || num > 20) {
      // Reset to default 5
      onChange({ threshold: 5 });
      setEmailThresholdDisplay("5");
    } else {
      onChange({ threshold: num });
      setEmailThresholdDisplay(num.toString());
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="space-y-4 sm:space-y-6"
    >
      <Card className="border-2">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <MessagesSquare className="size-4" />
            Enable Email Capture
          </CardTitle>
          <CardDescription>
            Prompt visitors to provide their contact information after a certain
            number of messages
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Enable Toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label
                htmlFor="email-capture-enabled"
                className="text-sm font-medium"
              >
                Collect visitor emails
              </Label>
              <p className="text-xs text-muted-foreground">
                When enabled, visitors will be prompted to share their email
              </p>
            </div>
            <Switch
              id="email-capture-enabled"
              checked={emailCapture.enabled}
              onCheckedChange={handlePopupCaptureToggle}
            />
          </div>

          {emailCapture.enabled && (
            <>
              {/* Message Threshold */}
              <div className="space-y-2">
                <Label
                  htmlFor="email-threshold"
                  className="text-sm font-medium flex items-center gap-2"
                >
                  <Hash className="size-3.5" />
                  Message Threshold
                </Label>
                <p className="text-xs text-muted-foreground mb-2">
                  Number of messages before prompting for email (1-20)
                </p>
                <div className="flex items-center gap-4">
                  <Input
                    id="email-threshold"
                    type="text"
                    inputMode="numeric"
                    value={emailThresholdDisplay}
                    onChange={(e) => handleThresholdChange(e.target.value)}
                    onBlur={handleThresholdBlur}
                    className="w-24"
                  />
                  <span className="text-sm text-muted-foreground">
                    messages
                  </span>
                </div>
              </div>

              <div className="h-px bg-border" />

              <div className="space-y-4">
                <h4 className="text-sm font-medium">Required Fields</h4>
                <p className="text-xs text-muted-foreground -mt-2">
                  Choose which fields visitors must provide when prompted
                </p>

                {/* Require Full Name */}
                <div className="flex items-center justify-between py-2">
                  <div className="space-y-0.5">
                    <Label
                      htmlFor="require-fullname"
                      className="text-sm font-medium flex items-center gap-2"
                    >
                      <UserCircle className="size-3.5" />
                      Full Name
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Require visitors to provide their full name
                    </p>
                  </div>
                  <Switch
                    id="require-fullname"
                    checked={emailCapture.requireFullname}
                    onCheckedChange={(checked) =>
                      onChange({ requireFullname: checked })
                    }
                  />
                </div>

                {/* Require Phone */}
                <div className="flex items-center justify-between py-2">
                  <div className="space-y-0.5">
                    <Label
                      htmlFor="require-phone"
                      className="text-sm font-medium flex items-center gap-2"
                    >
                      <Phone className="size-3.5" />
                      Phone Number
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Require visitors to provide their phone number
                    </p>
                  </div>
                  <Switch
                    id="require-phone"
                    checked={emailCapture.requirePhone}
                    onCheckedChange={(checked) =>
                      onChange({ requirePhone: checked })
                    }
                  />
                </div>
              </div>

              <div className="mt-4 p-4 bg-yellow-light border border-yellow-bright/20 rounded-lg">
                <div className="flex gap-3">
                  <ShieldCheck className="size-5 text-yellow-900 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-yellow-900">
                      Privacy Notice
                    </p>
                    <p className="text-xs text-yellow-900/80">
                      Collected information will be stored securely and
                      associated with the conversation. Email is always
                      required. Full name and phone are optional based on your
                      settings above.
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Conversational Lead Capture Card */}
      <Card className="border-2">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Bot className="size-4" />
            Conversational Lead Capture
          </CardTitle>
          <CardDescription>
            Your AI clone naturally asks visitors for their name, email, and
            phone number as part of the conversation — no popups or forms
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Enable Toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label
                htmlFor="conversational-capture-enabled"
                className="text-sm font-medium"
              >
                Enable conversational capture
              </Label>
              <p className="text-xs text-muted-foreground">
                The AI agent will find a natural moment during the conversation
                to collect contact details
              </p>
            </div>
            <Switch
              id="conversational-capture-enabled"
              checked={emailCapture.defaultLeadCaptureEnabled}
              onCheckedChange={handleConversationalCaptureToggle}
            />
          </div>

          {emailCapture.defaultLeadCaptureEnabled && (
            <>
              {/* How it works info box */}
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex gap-3">
                  <Info className="size-5 text-blue-700 shrink-0 mt-0.5" />
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-blue-900">
                      How it works
                    </p>
                    <ul className="text-xs text-blue-800 space-y-1.5 list-disc list-inside">
                      <li>
                        The AI will find a natural moment to ask for contact
                        details during the conversation
                      </li>
                      <li>
                        Email is always requested. Name and phone are asked but
                        visitors can decline
                      </li>
                      <li>
                        Collected data is automatically saved and linked to the
                        conversation
                      </li>
                      <li>
                        If the visitor provides their phone later, the record is
                        updated automatically
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Comparison note */}
              <div className="p-4 bg-yellow-light border border-yellow-bright/20 rounded-lg">
                <div className="flex gap-3">
                  <AlertTriangle className="size-5 text-yellow-900 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-yellow-900">
                      Replaces popup email capture
                    </p>
                    <p className="text-xs text-yellow-900/80">
                      This is a less disruptive alternative to the popup form
                      above. When this is enabled, the popup email capture is
                      automatically disabled. Only one method can be active at a
                      time.
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Conversation Summary Email Card */}
      <Card className="border-2">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Mail className="size-4" />
            Conversation Summary Emails
          </CardTitle>
          <CardDescription>
            Receive email summaries after conversations end with this persona
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label
                htmlFor="summary-email-enabled"
                className="text-sm font-medium"
              >
                Send conversation summaries
              </Label>
              <p className="text-xs text-muted-foreground">
                Get an email summary when a conversation with your persona ends
              </p>
            </div>
            <div className="flex items-center gap-2">
              {toggleSummaryEmail.isPending && (
                <Loader2 className="size-4 animate-spin text-muted-foreground" />
              )}
              <Switch
                id="summary-email-enabled"
                checked={sendSummaryEmailEnabled}
                onCheckedChange={handleSummaryEmailToggle}
                disabled={toggleSummaryEmail.isPending}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
