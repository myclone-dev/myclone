"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { cn, getInitials } from "@/lib/utils";

interface GuideVoiceAvatarProps {
  /** Avatar image URL */
  avatarUrl?: string;
  /** Expert name for alt text */
  expertName: string;
  /** Whether the assistant is speaking */
  speaking: boolean;
  /** Whether connected to voice session */
  isConnected: boolean;
  /** Whether currently connecting */
  isConnecting: boolean;
  /** Size variant */
  size?: "sm" | "md" | "lg";
  /** Primary color for rings (defaults to gold #FFC329) */
  ringColor?: string;
}

// Default gold color matching the brand
const DEFAULT_RING_COLOR = "#FFC329";

/**
 * Voice avatar with profile image and animated rings
 * Used for the ConvoxAI Guide widget with beautiful animations:
 * - Connecting: Rotating dashed ring
 * - Listening: Subtle breathing pulse
 * - Speaking: Animated sound wave rings expanding outward
 */
export const GuideVoiceAvatar = React.memo(function GuideVoiceAvatar({
  avatarUrl,
  expertName,
  speaking,
  isConnected,
  isConnecting,
  size = "md",
  ringColor = DEFAULT_RING_COLOR,
}: GuideVoiceAvatarProps) {
  // Size configurations - responsive classes for mobile
  const sizeConfig = {
    sm: {
      container: "w-16 h-16 sm:w-20 sm:h-20",
      ring: "w-20 h-20 sm:w-24 sm:h-24",
      offset: "-2",
    },
    md: {
      container: "w-20 h-20 sm:w-28 sm:h-28",
      ring: "w-24 h-24 sm:w-36 sm:h-36",
      offset: "-4",
    },
    lg: {
      container: "w-24 h-24 sm:w-36 sm:h-36",
      ring: "w-28 h-28 sm:w-44 sm:h-44",
      offset: "-4",
    },
  };

  const config = sizeConfig[size];
  const [imgError, setImgError] = useState(false);
  const showImage = avatarUrl && !imgError;

  return (
    <div className="relative flex items-center justify-center">
      {/* Outer animated rings for speaking */}
      {isConnected && speaking && (
        <>
          {/* Ring 1 - slowest, largest */}
          <motion.div
            className={cn("absolute rounded-full", config.ring)}
            style={{ border: `2px solid ${ringColor}` }}
            initial={{ scale: 1, opacity: 0.6 }}
            animate={{
              scale: [1, 1.4, 1.8],
              opacity: [0.6, 0.3, 0],
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: "easeOut",
            }}
          />
          {/* Ring 2 - medium */}
          <motion.div
            className={cn("absolute rounded-full", config.ring)}
            style={{ border: `2px solid ${ringColor}` }}
            initial={{ scale: 1, opacity: 0.5 }}
            animate={{
              scale: [1, 1.3, 1.6],
              opacity: [0.5, 0.25, 0],
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: "easeOut",
              delay: 0.3,
            }}
          />
          {/* Ring 3 - fastest, smallest expansion */}
          <motion.div
            className={cn("absolute rounded-full", config.ring)}
            style={{ border: `2px solid ${ringColor}` }}
            initial={{ scale: 1, opacity: 0.4 }}
            animate={{
              scale: [1, 1.2, 1.4],
              opacity: [0.4, 0.2, 0],
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: "easeOut",
              delay: 0.6,
            }}
          />
        </>
      )}

      {/* Listening state - subtle breathing glow */}
      {isConnected && !speaking && (
        <motion.div
          className={cn("absolute rounded-full", config.ring)}
          style={{ backgroundColor: `${ringColor}15` }}
          animate={{
            scale: [1, 1.08, 1],
            opacity: [0.3, 0.5, 0.3],
          }}
          transition={{
            duration: 2.5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      )}

      {/* Connecting state - rotating dashed ring */}
      {isConnecting && (
        <motion.div
          className={cn("absolute rounded-full", config.ring)}
          style={{
            border: `3px dashed ${ringColor}80`,
          }}
          animate={{ rotate: 360 }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "linear",
          }}
        />
      )}

      {/* Avatar container with subtle scale on speaking */}
      <motion.div
        className={cn(
          "relative rounded-full overflow-hidden shadow-xl ring-4 ring-white/50",
          config.container,
        )}
        animate={
          speaking
            ? {
                scale: [1, 1.04, 1],
              }
            : isConnected
              ? {
                  scale: [1, 1.02, 1],
                }
              : {}
        }
        transition={
          speaking
            ? {
                duration: 0.8,
                repeat: Infinity,
                ease: "easeInOut",
              }
            : isConnected
              ? {
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut",
                }
              : {}
        }
      >
        {showImage ? (
          // Profile image
          <img
            src={avatarUrl}
            alt={expertName}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          // Fallback: initials on gradient background
          <div
            className="w-full h-full relative flex items-center justify-center select-none"
            style={{
              background:
                "linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 50%, #1a1a1a 100%)",
            }}
          >
            <span
              className="font-semibold text-white"
              style={{
                fontSize:
                  size === "sm"
                    ? "0.875rem"
                    : size === "md"
                      ? "1.25rem"
                      : "1.75rem",
              }}
            >
              {getInitials(expertName)}
            </span>
          </div>
        )}

        {/* Overlay gradient for depth on images */}
        {showImage && (
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "linear-gradient(to bottom, transparent 60%, rgba(0,0,0,0.2) 100%)",
            }}
          />
        )}
      </motion.div>

      {/* Status indicator dot - responsive size */}
      <motion.div
        className={cn(
          "absolute bottom-0.5 right-0.5 sm:bottom-1 sm:right-1 w-3 h-3 sm:w-4 sm:h-4 rounded-full border-2 border-white shadow-md",
          isConnected
            ? speaking
              ? "bg-green-500"
              : "bg-emerald-400"
            : isConnecting
              ? "bg-amber-400"
              : "bg-gray-400",
        )}
        animate={
          isConnecting
            ? { scale: [1, 1.2, 1] }
            : speaking
              ? { scale: [1, 1.15, 1] }
              : {}
        }
        transition={{
          duration: isConnecting ? 1 : 0.6,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    </div>
  );
});
