"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageCircleQuestion, X, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface AssistantBubbleProps {
  onClick: () => void;
  isExpanded: boolean;
}

/**
 * Floating bubble button for the assistant widget
 * Features attention-grabbing animations and tooltip hint
 */
export function AssistantBubble({ onClick, isExpanded }: AssistantBubbleProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const [hasInteracted, setHasInteracted] = useState(false);

  // Show tooltip after a delay if user hasn't interacted
  useEffect(() => {
    if (hasInteracted || isExpanded) return;

    const timer = setTimeout(() => {
      setShowTooltip(true);
    }, 3000);

    return () => clearTimeout(timer);
  }, [hasInteracted, isExpanded]);

  // Hide tooltip after showing for a while
  useEffect(() => {
    if (!showTooltip) return;

    const timer = setTimeout(() => {
      setShowTooltip(false);
    }, 8000);

    return () => clearTimeout(timer);
  }, [showTooltip]);

  const handleClick = () => {
    setHasInteracted(true);
    setShowTooltip(false);
    onClick();
  };

  return (
    <div className="relative">
      {/* Tooltip */}
      <AnimatePresence>
        {showTooltip && !isExpanded && (
          <motion.div
            initial={{ opacity: 0, x: 10, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 10, scale: 0.9 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            className={cn(
              "absolute right-full mr-3 top-1/2 -translate-y-1/2",
              "whitespace-nowrap rounded-xl px-4 py-2.5",
              "bg-foreground text-background",
              "shadow-lg text-sm font-medium",
              "flex items-center gap-2",
            )}
          >
            <Sparkles className="h-4 w-4 text-yellow-400" />
            <span>Need help? Click me!</span>
            {/* Arrow */}
            <div
              className={cn(
                "absolute right-0 top-1/2 -translate-y-1/2 translate-x-full",
                "border-8 border-transparent border-l-foreground",
              )}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Ripple rings - only show when not expanded */}
      {!isExpanded && (
        <>
          <motion.div
            className="absolute inset-0 rounded-full bg-primary/20"
            animate={{
              scale: [1, 1.8, 2.2],
              opacity: [0.6, 0.2, 0],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeOut",
            }}
          />
          <motion.div
            className="absolute inset-0 rounded-full bg-primary/20"
            animate={{
              scale: [1, 1.6, 2],
              opacity: [0.5, 0.15, 0],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeOut",
              delay: 0.5,
            }}
          />
        </>
      )}

      {/* Main button */}
      <motion.button
        onClick={handleClick}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
        animate={
          !isExpanded
            ? {
                y: [0, -4, 0],
              }
            : {}
        }
        transition={
          !isExpanded
            ? {
                y: {
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut",
                },
              }
            : {}
        }
        aria-label={
          isExpanded ? "Close assistant" : "Get help with persona creation"
        }
        className={cn(
          // Base styles
          "relative flex h-18 w-18 items-center justify-center rounded-full",
          "shadow-xl transition-shadow duration-300",
          "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
          // Gradient background
          "bg-gradient-to-br from-primary via-primary to-primary/80",
          // Glow effect
          !isExpanded && "shadow-primary/40 shadow-lg",
        )}
      >
        {/* Inner glow */}
        <div
          className={cn(
            "absolute inset-0 rounded-full",
            "bg-gradient-to-t from-transparent via-white/10 to-white/20",
          )}
        />

        {/* Icon with animation */}
        <AnimatePresence mode="wait">
          {isExpanded ? (
            <motion.div
              key="close"
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <X
                className="h-7 w-7 text-primary-foreground"
                strokeWidth={2.5}
              />
            </motion.div>
          ) : (
            <motion.div
              key="help"
              initial={{ rotate: 90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: -90, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <MessageCircleQuestion className="h-7 w-7 text-primary-foreground" />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Shine effect */}
        {!isExpanded && (
          <motion.div
            className="absolute inset-0 rounded-full overflow-hidden"
            initial={false}
          >
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
              animate={{
                x: ["-100%", "200%"],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                repeatDelay: 3,
                ease: "easeInOut",
              }}
              style={{
                width: "50%",
              }}
            />
          </motion.div>
        )}
      </motion.button>
    </div>
  );
}
