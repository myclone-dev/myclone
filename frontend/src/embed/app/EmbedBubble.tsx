/**
 * ConvoxAI Embed Bubble Button
 * Floating button that opens the chat with beautiful animations
 *
 * Features:
 * - Dense pulsating waves that are clearly visible
 * - Floating animation
 * - Smooth icon transitions
 * - Periodic tooltip hint
 */

import React, { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslation } from "react-i18next";

interface EmbedBubbleProps {
  text: string;
  icon?: string;
  primaryColor: string;
  bubbleSize?: string;
  bubbleBackgroundColor?: string;
  bubbleTextColor?: string;
  onClick: () => void;
  isExpanded?: boolean;
  tooltipText?: string;
  /** Disable all animations (waves, floating, tooltips) for a simple static bubble */
  simpleBubble?: boolean;
}

export const EmbedBubble: React.FC<EmbedBubbleProps> = ({
  text,
  icon,
  primaryColor,
  bubbleSize = "80px",
  bubbleBackgroundColor,
  bubbleTextColor = "#ffffff",
  onClick,
  isExpanded = false,
  tooltipText,
  simpleBubble = false,
}) => {
  const { t } = useTranslation();
  const bgColor = bubbleBackgroundColor || primaryColor;
  const sizeNum = parseInt(bubbleSize) || 80;
  const iconSize = Math.round(sizeNum * 0.4);

  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipIndex, setTooltipIndex] = useState(0);
  const [hasInteracted, setHasInteracted] = useState(false);
  const [imageError, setImageError] = useState(false);

  // Tooltip messages that cycle through (translated)
  const tooltipMessages = useMemo(
    () => [
      t("widget.tooltips.talkToMe"),
      t("widget.tooltips.askAnything"),
      t("widget.tooltips.needHelp"),
      t("widget.tooltips.letsChat"),
    ],
    [t],
  );

  // Reset image error state when icon URL changes
  useEffect(() => {
    setImageError(false);
  }, [icon]);

  // Show tooltip after initial delay, then periodically (disabled in simple mode)
  useEffect(() => {
    if (simpleBubble || hasInteracted || isExpanded) {
      setShowTooltip(false);
      return;
    }

    // Initial delay before first tooltip
    const initialTimer = setTimeout(() => {
      setShowTooltip(true);
    }, 3000);

    return () => clearTimeout(initialTimer);
  }, [simpleBubble, hasInteracted, isExpanded]);

  // Hide tooltip after showing, then show again with next message (disabled in simple mode)
  useEffect(() => {
    if (simpleBubble || !showTooltip || hasInteracted || isExpanded) return;

    // Hide after 4 seconds
    const hideTimer = setTimeout(() => {
      setShowTooltip(false);

      // Show again after 8 seconds with next message
      const showAgainTimer = setTimeout(() => {
        if (!hasInteracted && !isExpanded) {
          setTooltipIndex((prev) => (prev + 1) % tooltipMessages.length);
          setShowTooltip(true);
        }
      }, 8000);

      return () => clearTimeout(showAgainTimer);
    }, 4000);

    return () => clearTimeout(hideTimer);
  }, [showTooltip, hasInteracted, isExpanded, tooltipMessages]);

  const handleClick = () => {
    setHasInteracted(true);
    setShowTooltip(false);
    onClick();
  };

  const currentTooltip = tooltipText || tooltipMessages[tooltipIndex];

  return (
    <div
      style={{
        position: "relative",
        width: isExpanded ? bubbleSize : "100%",
        height: isExpanded ? bubbleSize : "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: isExpanded ? "center" : "flex-end",
        // Only add padding for ripple when not expanded
        paddingRight: isExpanded ? "0" : "60px",
      }}
    >
      {/* Wrapper for bubble */}
      <div
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Pulsating waves - smooth continuous effect (disabled in simple mode) */}
        {!simpleBubble &&
          !isExpanded &&
          [0, 0.65, 1.3].map((delay) => (
            <motion.div
              key={delay}
              style={{
                position: "absolute",
                width: bubbleSize,
                height: bubbleSize,
                borderRadius: "9999px",
                backgroundColor: bgColor,
                opacity: 0,
              }}
              animate={{
                scale: [1, 1.7],
                opacity: [0.4, 0],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: [0.4, 0, 0.2, 1],
                delay,
              }}
            />
          ))}

        {/* Main button */}
        <motion.button
          onClick={handleClick}
          whileHover={{ scale: simpleBubble ? 1.05 : 1.1 }}
          whileTap={{ scale: 0.95 }}
          animate={!simpleBubble && !isExpanded ? { y: [0, -5, 0] } : {}}
          transition={
            !simpleBubble && !isExpanded
              ? { y: { duration: 2, repeat: Infinity, ease: "easeInOut" } }
              : {}
          }
          aria-label={
            isExpanded ? t("widget.closeChat") : text || t("widget.openChat")
          }
          style={{
            position: "relative",
            display: "flex",
            width: bubbleSize,
            height: bubbleSize,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "9999px",
            border: "none",
            cursor: "pointer",
            outline: "none",
            background: bgColor,
            boxShadow: `0 4px 20px ${adjustColorOpacity(bgColor, 0.5)}, 0 2px 8px rgba(0,0,0,0.15)`,
          }}
        >
          {/* Tooltip - positioned using inset to fill button, then flex center */}
          <AnimatePresence>
            {showTooltip && !isExpanded && (
              <motion.div
                initial={{ opacity: 0, x: 10, scale: 0.9 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 10, scale: 0.9 }}
                transition={{ type: "spring", stiffness: 300, damping: 25 }}
                style={{
                  position: "absolute",
                  top: 0,
                  bottom: 0,
                  right: "100%",
                  marginRight: "12px",
                  display: "flex",
                  alignItems: "center",
                  pointerEvents: "none",
                }}
              >
                <div
                  style={{
                    whiteSpace: "nowrap",
                    borderRadius: "12px",
                    padding: "10px 16px",
                    backgroundColor: "#1f2937",
                    color: "#ffffff",
                    boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                    fontSize: "14px",
                    fontWeight: 500,
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    position: "relative",
                  }}
                >
                  <SparklesIcon color="#facc15" size={16} />
                  <span>{currentTooltip}</span>
                  {/* Arrow pointing right */}
                  <div
                    style={{
                      position: "absolute",
                      right: "-8px",
                      top: "50%",
                      transform: "translateY(-50%)",
                      width: 0,
                      height: 0,
                      borderTop: "8px solid transparent",
                      borderBottom: "8px solid transparent",
                      borderLeft: "8px solid #1f2937",
                    }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          {/* Icon with smooth animation */}
          <AnimatePresence mode="wait" initial={false}>
            {isExpanded ? (
              <motion.div
                key="close"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
                transition={{
                  duration: 0.2,
                  ease: [0.4, 0, 0.2, 1],
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <CloseIcon color={bubbleTextColor} size={iconSize} />
              </motion.div>
            ) : icon && !imageError ? (
              <motion.div
                key="custom-icon"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
                transition={{
                  duration: 0.2,
                  ease: [0.4, 0, 0.2, 1],
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "100%",
                  height: "100%",
                  position: "absolute",
                  inset: 0,
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={icon}
                  alt="Chat"
                  onError={() => setImageError(true)}
                  style={{
                    width: "100%",
                    height: "100%",
                    borderRadius: "50%",
                    objectFit: "cover",
                    border: "3px solid rgba(255, 255, 255, 0.9)",
                    // Soften the image to reduce harsh resolution look
                    imageRendering: "auto",
                    filter: "blur(0.3px)",
                    // Compensate for blur with slight scale
                    transform: "scale(1.02)",
                  }}
                />
              </motion.div>
            ) : (
              <motion.div
                key="message"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
                transition={{
                  duration: 0.2,
                  ease: [0.4, 0, 0.2, 1],
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <MessageIcon color={bubbleTextColor} size={iconSize} />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.button>
      </div>
    </div>
  );
};

/**
 * Helper function to adjust color opacity
 * Works with hex colors
 */
function adjustColorOpacity(color: string, opacity: number): string {
  // If it's already rgba, just return with new opacity
  if (color.startsWith("rgba")) {
    return color.replace(/[\d.]+\)$/, `${opacity})`);
  }

  // Convert hex to rgba
  if (color.startsWith("#")) {
    const hex = color.slice(1);
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }

  // Fallback
  return color;
}

/**
 * Message bubble icon - Intercom style
 */
const MessageIcon: React.FC<{ color?: string; size?: number }> = ({
  color = "currentColor",
  size = 28,
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 28 28"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M14 2.33337C7.55672 2.33337 2.33337 7.03171 2.33337 12.8334C2.33337 15.3184 3.29837 17.5867 4.90171 19.3634V25.6667L10.7617 22.5167C11.8017 22.7517 12.8834 22.8767 14 22.8767C20.4434 22.8767 25.6667 18.1784 25.6667 12.3767C25.6667 6.57504 20.4434 2.33337 14 2.33337Z"
      fill={color}
    />
  </svg>
);

/**
 * Close icon - X shape for closing the chat
 */
const CloseIcon: React.FC<{ color?: string; size?: number }> = ({
  color = "currentColor",
  size = 28,
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M18 6L6 18M6 6L18 18"
      stroke={color}
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

/**
 * Sparkles icon for tooltip
 */
const SparklesIcon: React.FC<{ color?: string; size?: number }> = ({
  color = "currentColor",
  size = 16,
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M12 3L13.4 8.6L19 10L13.4 11.4L12 17L10.6 11.4L5 10L10.6 8.6L12 3Z"
      fill={color}
    />
    <path
      d="M19 15L19.8 17.2L22 18L19.8 18.8L19 21L18.2 18.8L16 18L18.2 17.2L19 15Z"
      fill={color}
    />
    <path
      d="M5 2L5.6 3.8L7.5 4.5L5.6 5.2L5 7L4.4 5.2L2.5 4.5L4.4 3.8L5 2Z"
      fill={color}
    />
  </svg>
);
