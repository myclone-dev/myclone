"use client";

import { motion } from "motion/react";
import {
  Sparkles,
  Bot,
  Brain,
  Zap,
  Settings,
  CheckCircle2,
  Wand2,
  Loader2,
} from "lucide-react";
import { useState, useEffect } from "react";

interface PersonaCreatingOverlayProps {
  personaName?: string;
  /** Use "creating" for new persona, "loading" for loading existing persona settings */
  variant?: "creating" | "loading";
  /** Start from this step (0-indexed). Use to resume from where we left off */
  initialStep?: number;
  /** If true, show only the final step as loading (for reopening dialog) */
  showOnlyFinalStep?: boolean;
}

export function PersonaCreatingOverlay({
  personaName,
  variant = "creating",
  initialStep = 0,
  showOnlyFinalStep = false,
}: PersonaCreatingOverlayProps) {
  const [activeStep, setActiveStep] = useState(initialStep);

  const creatingSteps = [
    {
      icon: Bot,
      label: "Setting up persona",
      fullLabel: "Setting up your persona",
      completedLabel: "Persona initialized",
      duration: 1800, // 1.8 seconds - quick initial setup
    },
    {
      icon: Brain,
      label: "Configuring AI",
      fullLabel: "Configuring AI behavior",
      completedLabel: "AI configured",
      duration: 2200, // 2.2 seconds - AI config takes a bit longer
    },
    {
      icon: Zap,
      label: "Generating questions",
      fullLabel: "Generating suggested questions",
      completedLabel: "Questions ready",
      duration: 3500, // 3.5 seconds - question generation takes the longest
    },
    {
      icon: Sparkles,
      label: "Finalizing...",
      fullLabel: "Finalizing magic touches...",
      completedLabel: "All set!",
      duration: 2000, // 2 seconds - final touches
    },
  ];

  const loadingSteps = [
    {
      icon: Settings,
      label: "Loading settings",
      fullLabel: "Loading persona settings",
      completedLabel: "Settings loaded",
      duration: 1200, // 1.2 seconds
    },
    {
      icon: Brain,
      label: "Fetching config",
      fullLabel: "Fetching configuration",
      completedLabel: "Config ready",
      duration: 1500, // 1.5 seconds
    },
    {
      icon: Sparkles,
      label: "Preparing...",
      fullLabel: "Preparing editor",
      completedLabel: "Ready!",
      duration: 1000, // 1 second
    },
  ];

  const allSteps = variant === "creating" ? creatingSteps : loadingSteps;
  const isCreating = variant === "creating";

  // Auto-progress through steps with variable delays for each step
  useEffect(() => {
    if (showOnlyFinalStep) return;

    // Don't progress if we're at the last step
    if (activeStep >= allSteps.length - 1) return;

    const currentStepDuration = allSteps[activeStep].duration;

    const timeout = setTimeout(() => {
      setActiveStep((prev) => {
        if (prev < allSteps.length - 1) {
          return prev + 1;
        }
        return prev;
      });
    }, currentStepDuration);

    return () => clearTimeout(timeout);
  }, [activeStep, allSteps, showOnlyFinalStep]);

  // If showing only final step, show simplified UI
  if (showOnlyFinalStep) {
    return (
      <div className="flex flex-col items-center justify-center py-8 sm:py-12 px-4 sm:px-6 flex-1 min-h-0">
        {/* Simple spinner with message */}
        <motion.div
          className="flex items-center justify-center rounded-full bg-gradient-to-br from-primary via-primary/90 to-primary/70 shadow-xl size-16 sm:size-20 md:size-24"
          animate={{ scale: [1, 1.05, 1] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
        >
          <Loader2
            className="size-8 sm:size-10 md:size-12 text-primary-foreground animate-spin"
            strokeWidth={1.5}
          />
        </motion.div>

        <motion.p
          className="mt-6 text-sm sm:text-base text-muted-foreground text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          Loading persona data...
        </motion.p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-6 sm:py-8 md:py-10 px-3 sm:px-4 md:px-6 flex-1 min-h-0 overflow-auto">
      {/* Main Animation Container */}
      <div className="relative mb-4 sm:mb-6 md:mb-8">
        {/* Outer glow ring */}
        <motion.div
          className="absolute -inset-2 sm:-inset-3 md:-inset-4 rounded-full bg-gradient-to-r from-primary/20 via-primary/10 to-primary/20 blur-md sm:blur-lg md:blur-xl"
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.5, 0.8, 0.5],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />

        {/* Spinning outer ring with gradient */}
        <motion.div
          className="absolute inset-0 rounded-full size-[70px] sm:size-[90px] md:size-[110px] lg:size-[130px]"
          style={{
            background:
              "conic-gradient(from 0deg, transparent, hsl(var(--primary) / 0.3), transparent)",
          }}
          animate={{ rotate: 360 }}
          transition={{
            duration: isCreating ? 4 : 2,
            repeat: Infinity,
            ease: "linear",
          }}
        />

        {/* Inner ring */}
        <motion.div
          className="absolute rounded-full border-2 border-primary/20 size-[62px] sm:size-[82px] md:size-[100px] lg:size-[120px] left-[4px] top-[4px]"
          animate={{ rotate: -360 }}
          transition={{
            duration: isCreating ? 6 : 3,
            repeat: Infinity,
            ease: "linear",
          }}
        />

        {/* Center circle with gradient background */}
        <motion.div className="relative flex items-center justify-center rounded-full shadow-2xl overflow-hidden size-[70px] sm:size-[90px] md:size-[110px] lg:size-[130px]">
          {/* Animated gradient background */}
          <motion.div
            className="absolute inset-0 bg-gradient-to-br from-primary via-primary/90 to-primary/70"
            animate={{
              backgroundPosition: ["0% 0%", "100% 100%", "0% 0%"],
            }}
            transition={{
              duration: 4,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />

          {/* Icon container */}
          <motion.div
            className="relative z-10 text-primary-foreground"
            animate={
              isCreating
                ? { scale: [1, 1.1, 1], rotate: [0, 5, -5, 0] }
                : { rotate: [0, 360] }
            }
            transition={{
              duration: isCreating ? 2 : 3,
              repeat: Infinity,
              ease: isCreating ? "easeInOut" : "linear",
            }}
          >
            {isCreating ? (
              <Wand2
                className="size-7 sm:size-9 md:size-11 lg:size-12"
                strokeWidth={1.5}
              />
            ) : (
              <Settings
                className="size-7 sm:size-9 md:size-11 lg:size-12"
                strokeWidth={1.5}
              />
            )}
          </motion.div>
        </motion.div>

        {/* Floating particles - only for creating variant, fewer on mobile */}
        {isCreating &&
          [...Array(6)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute rounded-full size-1 sm:size-1.5 md:size-2"
              style={{
                left: "50%",
                top: "50%",
                marginLeft: -3,
                marginTop: -3,
                background: `hsl(var(--primary) / ${0.8 - i * 0.1})`,
              }}
              animate={{
                x: [0, Math.cos((i * Math.PI * 2) / 6) * 55],
                y: [0, Math.sin((i * Math.PI * 2) / 6) * 55],
                opacity: [1, 0],
                scale: [1, 0.3],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                delay: i * 0.25,
                ease: "easeOut",
              }}
            />
          ))}
      </div>

      {/* Title */}
      <motion.h2
        className="text-base sm:text-lg md:text-xl font-bold text-foreground mb-1.5 sm:mb-2 text-center px-2"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        {isCreating ? (
          <>
            Creating{" "}
            {personaName ? (
              <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent break-words">
                {personaName}
              </span>
            ) : (
              "your persona"
            )}
          </>
        ) : (
          <>
            Loading{" "}
            {personaName ? (
              <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent break-words">
                {personaName}
              </span>
            ) : (
              "settings"
            )}
          </>
        )}
      </motion.h2>

      <motion.p
        className="text-[11px] sm:text-xs md:text-sm text-muted-foreground mb-4 sm:mb-6 md:mb-8 text-center max-w-[280px] sm:max-w-xs md:max-w-sm px-2"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        {isCreating
          ? "Setting up your AI persona. This will only take a moment."
          : "Just a moment..."}
      </motion.p>

      {/* Progress Steps */}
      <div className="space-y-1.5 sm:space-y-2 md:space-y-2.5 w-full max-w-[300px] sm:max-w-sm md:max-w-md px-2">
        {allSteps.map((step, index) => {
          const Icon = step.icon;
          const isCompleted = index < activeStep;
          const isActive = index === activeStep;

          return (
            <motion.div
              key={index}
              className={`flex items-center gap-2 sm:gap-2.5 md:gap-3 p-2 sm:p-2.5 md:p-3 rounded-lg md:rounded-xl border transition-all duration-300 ${
                isCompleted
                  ? "bg-primary/5 border-primary/20"
                  : isActive
                    ? "bg-muted/80 border-primary/30 shadow-sm"
                    : "bg-muted/30 border-transparent"
              }`}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.15 }}
            >
              {/* Icon */}
              <motion.div
                className={`flex items-center justify-center size-7 sm:size-8 md:size-9 rounded-full transition-colors duration-300 shrink-0 ${
                  isCompleted
                    ? "bg-primary/20"
                    : isActive
                      ? "bg-primary/15"
                      : "bg-muted"
                }`}
                animate={
                  isActive
                    ? {
                        scale: [1, 1.1, 1],
                      }
                    : {}
                }
                transition={{
                  duration: 1,
                  repeat: isActive ? Infinity : 0,
                  ease: "easeInOut",
                }}
              >
                {isCompleted ? (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  >
                    <CheckCircle2 className="size-3.5 sm:size-4 md:size-4.5 text-primary" />
                  </motion.div>
                ) : (
                  <Icon
                    className={`size-3.5 sm:size-4 md:size-4.5 ${isActive ? "text-primary" : "text-muted-foreground"}`}
                  />
                )}
              </motion.div>

              {/* Label */}
              <div className="flex-1 min-w-0">
                <span
                  className={`text-[11px] sm:text-xs md:text-sm font-medium transition-colors duration-300 block truncate ${
                    isCompleted
                      ? "text-primary"
                      : isActive
                        ? "text-foreground"
                        : "text-muted-foreground"
                  }`}
                >
                  {/* Show shorter labels on mobile, full labels on md+ */}
                  <span className="md:hidden">
                    {isCompleted ? step.completedLabel : step.label}
                  </span>
                  <span className="hidden md:inline">
                    {isCompleted ? step.completedLabel : step.fullLabel}
                  </span>
                </span>
              </div>

              {/* Status indicator */}
              <div className="w-8 sm:w-10 md:w-12 flex justify-end shrink-0">
                {isActive && (
                  <motion.div
                    className="flex gap-0.5 sm:gap-1"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                  >
                    {[0, 1, 2].map((dot) => (
                      <motion.div
                        key={dot}
                        className="size-1 sm:size-1.5 md:size-2 rounded-full bg-primary"
                        animate={{
                          scale: [1, 1.3, 1],
                          opacity: [0.5, 1, 0.5],
                        }}
                        transition={{
                          duration: 0.8,
                          repeat: Infinity,
                          delay: dot * 0.15,
                          ease: "easeInOut",
                        }}
                      />
                    ))}
                  </motion.div>
                )}
                {isCompleted && (
                  <motion.span
                    className="text-[9px] sm:text-[10px] md:text-xs text-primary font-medium"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                  >
                    Done
                  </motion.span>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Progress bar at bottom */}
      <motion.div
        className="mt-4 sm:mt-5 md:mt-6 w-full max-w-[300px] sm:max-w-sm md:max-w-md h-1 md:h-1.5 bg-muted rounded-full overflow-hidden mx-2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        <motion.div
          className="h-full bg-gradient-to-r from-primary to-primary/70 rounded-full"
          initial={{ width: `${((initialStep + 1) / allSteps.length) * 100}%` }}
          animate={{
            width: `${((activeStep + 1) / allSteps.length) * 100}%`,
          }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </motion.div>
    </div>
  );
}
