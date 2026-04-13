"use client";

import { motion } from "motion/react";
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
import { Calendar, Link, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CalendarSettings } from "../../types";
import { validateCalendarUrl, MAX_CALENDAR_URL_LENGTH } from "../../utils";

interface CalendarTabProps {
  calendar: CalendarSettings;
  onChange: (updates: Partial<CalendarSettings>) => void;
  calendarUrlError: string | null;
  setCalendarUrlError: (error: string | null) => void;
}

/**
 * Calendar Integration Tab
 * Allow users to book meetings through the chat interface
 */
export function CalendarTab({
  calendar,
  onChange,
  calendarUrlError,
  setCalendarUrlError,
}: CalendarTabProps) {
  const handleUrlBlur = () => {
    if (!calendar.url) {
      setCalendarUrlError(null);
      return;
    }

    const validation = validateCalendarUrl(calendar.url);
    if (!validation.valid) {
      setCalendarUrlError(validation.error || "Invalid URL");
    } else if (calendar.url.length > MAX_CALENDAR_URL_LENGTH) {
      setCalendarUrlError(
        `URL must be ${MAX_CALENDAR_URL_LENGTH} characters or less`,
      );
    } else {
      setCalendarUrlError(null);
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
            <Calendar className="size-4" />
            Calendar Booking Settings
          </CardTitle>
          <CardDescription>
            Enable calendar integration to let users schedule meetings with you
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Enable Toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="calendar-enabled" className="text-sm font-medium">
                Enable calendar booking
              </Label>
              <p className="text-xs text-muted-foreground">
                When enabled, users can book meetings through the chat
              </p>
            </div>
            <Switch
              id="calendar-enabled"
              checked={calendar.enabled}
              onCheckedChange={(checked) => {
                onChange({ enabled: checked });
                if (!checked) setCalendarUrlError(null);
              }}
            />
          </div>

          {calendar.enabled && (
            <>
              <div className="h-px bg-border" />

              {/* Calendar URL */}
              <div className="space-y-2">
                <Label
                  htmlFor="calendar-url"
                  className="text-sm font-medium flex items-center gap-2"
                >
                  <Link className="size-3.5" />
                  Calendar Booking URL
                </Label>
                <Input
                  id="calendar-url"
                  type="url"
                  placeholder="https://calendly.com/your-link"
                  value={calendar.url}
                  onChange={(e) => {
                    onChange({ url: e.target.value });
                    // Clear error on change
                    if (calendarUrlError) setCalendarUrlError(null);
                  }}
                  onBlur={handleUrlBlur}
                  className={cn(
                    "h-10",
                    calendarUrlError && "border-destructive",
                  )}
                />
                {calendarUrlError ? (
                  <p className="text-xs text-destructive">{calendarUrlError}</p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Enter your Calendly, Cal.com, or Google Calendar booking
                    link
                  </p>
                )}
              </div>

              {/* Calendar Display Name */}
              <div className="space-y-2">
                <Label
                  htmlFor="calendar-display-name"
                  className="text-sm font-medium"
                >
                  Display Name (optional)
                </Label>
                <Input
                  id="calendar-display-name"
                  placeholder="e.g., Book a 30-min call"
                  value={calendar.displayName}
                  onChange={(e) => onChange({ displayName: e.target.value })}
                  maxLength={100}
                  className="h-10"
                />
                <p className="text-xs text-muted-foreground">
                  Custom text to show users when offering calendar booking (max
                  100 characters)
                </p>
              </div>

              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex gap-3">
                  <ShieldCheck className="size-5 text-blue-700 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-blue-900">
                      How it works
                    </p>
                    <ul className="text-xs text-blue-800 space-y-1">
                      <li>
                        • When appropriate, your persona will offer users the
                        option to book a meeting
                      </li>
                      <li>
                        • Users will be directed to your booking page to select
                        a time
                      </li>
                      <li>
                        • The booking link opens in a new tab without
                        interrupting the conversation
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
