"use client";

import { useState, useEffect } from "react";
import { motion } from "motion/react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Timer, Clock, AlertTriangle, Info } from "lucide-react";
import type { SessionTimeLimitSettings } from "../../types";
import {
  SESSION_LIMIT_OPTIONS,
  SESSION_WARNING_OPTIONS,
} from "../../utils/constants";

interface SessionLimitTabProps {
  sessionTimeLimit: SessionTimeLimitSettings;
  onChange: (updates: Partial<SessionTimeLimitSettings>) => void;
}

/**
 * Session Time Limit Tab
 * Configure session duration limits for visitors
 */
export function SessionLimitTab({
  sessionTimeLimit,
  onChange,
}: SessionLimitTabProps) {
  // Check if current value matches a preset option
  const isPresetValue = SESSION_LIMIT_OPTIONS.some(
    (opt) => opt.value === sessionTimeLimit.limitMinutes,
  );

  // State for custom duration mode
  const [isCustomMode, setIsCustomMode] = useState(!isPresetValue);
  const [customMinutes, setCustomMinutes] = useState(
    Math.floor(sessionTimeLimit.limitMinutes),
  );
  const [customSeconds, setCustomSeconds] = useState(
    Math.round((sessionTimeLimit.limitMinutes % 1) * 60),
  );

  // Check if warning value matches a preset option
  const isWarningPresetValue = SESSION_WARNING_OPTIONS.some(
    (opt) => opt.value === sessionTimeLimit.warningMinutes,
  );

  // State for custom warning mode
  const [isCustomWarningMode, setIsCustomWarningMode] =
    useState(!isWarningPresetValue);
  const [customWarningMinutes, setCustomWarningMinutes] = useState(
    Math.floor(sessionTimeLimit.warningMinutes),
  );
  const [customWarningSeconds, setCustomWarningSeconds] = useState(
    Math.round((sessionTimeLimit.warningMinutes % 1) * 60),
  );

  // Sync custom values when limitMinutes changes externally
  useEffect(() => {
    if (!isPresetValue && !isCustomMode) {
      setIsCustomMode(true);
    }
    setCustomMinutes(Math.floor(sessionTimeLimit.limitMinutes));
    setCustomSeconds(Math.round((sessionTimeLimit.limitMinutes % 1) * 60));
  }, [sessionTimeLimit.limitMinutes, isPresetValue, isCustomMode]);

  // Sync custom warning values when warningMinutes changes externally
  useEffect(() => {
    if (!isWarningPresetValue && !isCustomWarningMode) {
      setIsCustomWarningMode(true);
    }
    setCustomWarningMinutes(Math.floor(sessionTimeLimit.warningMinutes));
    setCustomWarningSeconds(
      Math.round((sessionTimeLimit.warningMinutes % 1) * 60),
    );
  }, [
    sessionTimeLimit.warningMinutes,
    isWarningPresetValue,
    isCustomWarningMode,
  ]);

  // Filter warning options to only show values less than the limit
  const availableWarningOptions = SESSION_WARNING_OPTIONS.filter(
    (option) => option.value < sessionTimeLimit.limitMinutes,
  );

  // Handle preset dropdown change
  const handlePresetChange = (value: string) => {
    if (value === "custom") {
      setIsCustomMode(true);
      const defaultCustom = sessionTimeLimit.limitMinutes || 5;
      setCustomMinutes(Math.floor(defaultCustom));
      setCustomSeconds(0);
    } else {
      setIsCustomMode(false);
      const newLimit = parseInt(value);
      onChange({ limitMinutes: newLimit });

      if (sessionTimeLimit.warningMinutes >= newLimit) {
        const validWarning =
          SESSION_WARNING_OPTIONS.filter((opt) => opt.value < newLimit).pop()
            ?.value || 1;
        onChange({ warningMinutes: validWarning });
      }
    }
  };

  // Update total minutes and adjust warning if needed
  const updateTotalMinutes = (mins: number, secs: number) => {
    const totalMinutes = mins + secs / 60;
    onChange({ limitMinutes: totalMinutes });

    if (sessionTimeLimit.warningMinutes >= totalMinutes) {
      const validWarning =
        SESSION_WARNING_OPTIONS.filter((opt) => opt.value < totalMinutes).pop()
          ?.value || 1;
      onChange({ warningMinutes: validWarning });
    }
  };

  // Handle custom minutes input change
  const handleCustomMinutesChange = (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const value = e.target.value;
    if (value === "") {
      setCustomMinutes(0);
      // Still update total when clearing (use 0 minutes)
      updateTotalMinutes(0, customSeconds);
      return;
    }
    const mins = parseInt(value);
    if (isNaN(mins) || mins < 0) return;
    const clampedMins = Math.min(120, mins);
    setCustomMinutes(clampedMins);
    updateTotalMinutes(clampedMins, customSeconds);
  };

  // Handle custom seconds input change
  const handleCustomSecondsChange = (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const value = e.target.value;
    if (value === "") {
      setCustomSeconds(0);
      // Still update total when clearing (use 0 seconds)
      updateTotalMinutes(customMinutes, 0);
      return;
    }
    const secs = parseInt(value);
    if (isNaN(secs) || secs < 0) return;
    const clampedSecs = Math.min(59, secs);
    setCustomSeconds(clampedSecs);
    updateTotalMinutes(customMinutes, clampedSecs);
  };

  // Handle blur - ensure valid values
  const handleMinutesBlur = () => {
    if (customMinutes < 1 && customSeconds === 0) {
      setCustomMinutes(1);
      updateTotalMinutes(1, 0);
    }
  };

  // Handle warning preset dropdown change
  const handleWarningPresetChange = (value: string) => {
    if (value === "custom") {
      setIsCustomWarningMode(true);
      const defaultCustom = sessionTimeLimit.warningMinutes || 1;
      setCustomWarningMinutes(Math.floor(defaultCustom));
      setCustomWarningSeconds(0);
    } else {
      setIsCustomWarningMode(false);
      onChange({ warningMinutes: parseInt(value) });
    }
  };

  // Update warning minutes
  const updateWarningMinutes = (mins: number, secs: number) => {
    const totalWarning = mins + secs / 60;
    // Ensure warning is less than session duration
    if (totalWarning < sessionTimeLimit.limitMinutes) {
      onChange({ warningMinutes: totalWarning });
    }
  };

  // Handle custom warning minutes input change
  const handleCustomWarningMinutesChange = (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const value = e.target.value;
    if (value === "") {
      setCustomWarningMinutes(0);
      // Still update when clearing (use 0 minutes)
      updateWarningMinutes(0, customWarningSeconds);
      return;
    }
    const mins = parseInt(value);
    if (isNaN(mins) || mins < 0) return;
    const maxMins = Math.floor(sessionTimeLimit.limitMinutes) - 1;
    const clampedMins = Math.min(Math.max(0, maxMins), mins);
    setCustomWarningMinutes(clampedMins);
    updateWarningMinutes(clampedMins, customWarningSeconds);
  };

  // Handle custom warning seconds input change
  const handleCustomWarningSecondsChange = (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const value = e.target.value;
    if (value === "") {
      setCustomWarningSeconds(0);
      // Still update when clearing (use 0 seconds)
      updateWarningMinutes(customWarningMinutes, 0);
      return;
    }
    const secs = parseInt(value);
    if (isNaN(secs) || secs < 0) return;
    const clampedSecs = Math.min(59, secs);
    setCustomWarningSeconds(clampedSecs);
    updateWarningMinutes(customWarningMinutes, clampedSecs);
  };

  // Handle warning blur - ensure valid values
  const handleWarningMinutesBlur = () => {
    if (customWarningMinutes === 0 && customWarningSeconds === 0) {
      setCustomWarningSeconds(30);
      updateWarningMinutes(0, 30);
    }
  };

  // Get current warning dropdown value
  const getWarningDropdownValue = () => {
    if (isCustomWarningMode) return "custom";
    const preset = SESSION_WARNING_OPTIONS.find(
      (opt) => opt.value === sessionTimeLimit.warningMinutes,
    );
    return preset ? preset.value.toString() : "custom";
  };

  // Format the display label for "How it works" section
  const formatDurationLabel = () => {
    if (isCustomMode) {
      if (customSeconds === 0) {
        return customMinutes === 1 ? "1 minute" : `${customMinutes} minutes`;
      }
      return `${customMinutes}m ${customSeconds}s`;
    }
    return (
      SESSION_LIMIT_OPTIONS.find(
        (opt) => opt.value === sessionTimeLimit.limitMinutes,
      )?.label || `${sessionTimeLimit.limitMinutes} minutes`
    );
  };

  // Format warning time label
  const formatWarningLabel = () => {
    if (isCustomWarningMode) {
      if (customWarningSeconds === 0) {
        return customWarningMinutes === 1
          ? "1 minute"
          : `${customWarningMinutes} minutes`;
      }
      return `${customWarningMinutes}m ${customWarningSeconds}s`;
    }
    return sessionTimeLimit.warningMinutes === 1
      ? "1 minute"
      : `${sessionTimeLimit.warningMinutes} minutes`;
  };

  // Get current dropdown value
  const getCurrentDropdownValue = () => {
    if (isCustomMode) return "custom";
    const preset = SESSION_LIMIT_OPTIONS.find(
      (opt) => opt.value === sessionTimeLimit.limitMinutes,
    );
    return preset ? preset.value.toString() : "custom";
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
            <Timer className="size-4" />
            Session Time Limit
          </CardTitle>
          <CardDescription>
            Limit how long visitors can interact with your persona per session
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Enable Toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label
                htmlFor="session-limit-enabled"
                className="text-sm font-medium"
              >
                Enable time limit
              </Label>
              <p className="text-xs text-muted-foreground">
                When enabled, sessions will automatically end after the
                specified duration
              </p>
            </div>
            <Switch
              id="session-limit-enabled"
              checked={sessionTimeLimit.enabled}
              onCheckedChange={(checked) => onChange({ enabled: checked })}
            />
          </div>

          {sessionTimeLimit.enabled && (
            <>
              {/* Session Duration */}
              <div className="space-y-2">
                <Label
                  htmlFor="session-duration"
                  className="text-sm font-medium flex items-center gap-2"
                >
                  <Clock className="size-3.5" />
                  Session Duration
                </Label>
                <p className="text-xs text-muted-foreground mb-2">
                  Maximum time visitors can interact per session
                </p>

                {/* Preset Dropdown */}
                <Select
                  value={getCurrentDropdownValue()}
                  onValueChange={handlePresetChange}
                >
                  <SelectTrigger id="session-duration" className="w-48">
                    <SelectValue placeholder="Select duration" />
                  </SelectTrigger>
                  <SelectContent>
                    {SESSION_LIMIT_OPTIONS.map((option) => (
                      <SelectItem
                        key={option.value}
                        value={option.value.toString()}
                      >
                        {option.label}
                      </SelectItem>
                    ))}
                    <SelectItem value="custom" className="border-t mt-1 pt-1">
                      <span className="font-medium">Custom...</span>
                    </SelectItem>
                  </SelectContent>
                </Select>

                {/* Custom Duration Inputs */}
                {isCustomMode && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex items-center gap-4 mt-3 p-3 bg-gray-50 rounded-lg border"
                  >
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        max={120}
                        value={customMinutes}
                        onChange={handleCustomMinutesChange}
                        onBlur={handleMinutesBlur}
                        className="w-16 text-center"
                      />
                      <span className="text-sm text-muted-foreground">min</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        max={59}
                        value={customSeconds}
                        onChange={handleCustomSecondsChange}
                        className="w-16 text-center"
                      />
                      <span className="text-sm text-muted-foreground">sec</span>
                    </div>
                  </motion.div>
                )}
              </div>

              <div className="h-px bg-border" />

              {/* Warning Time */}
              <div className="space-y-2">
                <Label
                  htmlFor="warning-time"
                  className="text-sm font-medium flex items-center gap-2"
                >
                  <AlertTriangle className="size-3.5" />
                  Warning Time
                </Label>
                <p className="text-xs text-muted-foreground mb-2">
                  Show a warning this many minutes before the session ends
                </p>
                <Select
                  value={getWarningDropdownValue()}
                  onValueChange={handleWarningPresetChange}
                >
                  <SelectTrigger id="warning-time" className="w-48">
                    <SelectValue placeholder="Select warning time" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableWarningOptions.length > 0 ? (
                      availableWarningOptions.map((option) => (
                        <SelectItem
                          key={option.value}
                          value={option.value.toString()}
                        >
                          {option.label}
                        </SelectItem>
                      ))
                    ) : (
                      <SelectItem value="1">1 minute</SelectItem>
                    )}
                    <SelectItem value="custom" className="border-t mt-1 pt-1">
                      <span className="font-medium">Custom...</span>
                    </SelectItem>
                  </SelectContent>
                </Select>

                {/* Custom Warning Inputs */}
                {isCustomWarningMode && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex items-center gap-4 mt-3 p-3 bg-gray-50 rounded-lg border"
                  >
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        max={Math.floor(sessionTimeLimit.limitMinutes) - 1}
                        value={customWarningMinutes}
                        onChange={handleCustomWarningMinutesChange}
                        onBlur={handleWarningMinutesBlur}
                        className="w-16 text-center"
                      />
                      <span className="text-sm text-muted-foreground">min</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        max={59}
                        value={customWarningSeconds}
                        onChange={handleCustomWarningSecondsChange}
                        className="w-16 text-center"
                      />
                      <span className="text-sm text-muted-foreground">sec</span>
                    </div>
                  </motion.div>
                )}
              </div>

              <div className="mt-4 p-4 bg-yellow-light border border-yellow-bright/20 rounded-lg">
                <div className="flex gap-3">
                  <Info className="size-5 text-yellow-900 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-yellow-900">
                      How it works
                    </p>
                    <p className="text-xs text-yellow-900/80">
                      When a visitor starts chatting, a timer begins. A warning
                      will appear {formatWarningLabel()} before their{" "}
                      {formatDurationLabel()} session ends. After the time
                      limit, the chat will be disconnected and they can start a
                      new session.
                    </p>
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
