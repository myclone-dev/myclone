"use client";

import React, { useEffect, useRef } from "react";
import { motion, useAnimation } from "framer-motion";
import { SoundWave } from "./SoundWave";

interface VoiceAvatarProps {
  speaking: boolean;
  isConnected: boolean;
}

export const VoiceAvatar = React.memo(function VoiceAvatar({
  speaking,
  isConnected,
}: VoiceAvatarProps) {
  const controls = useAnimation();
  const hasMountedRef = useRef(false);

  useEffect(() => {
    if (!hasMountedRef.current) return;
    controls.start(
      {
        scale: speaking ? 1.06 : 1,
      },
      {
        type: "spring",
        stiffness: 120,
        damping: 18,
      },
    );
  }, [speaking, controls]);

  useEffect(() => {
    controls.set({ scale: 1 });
    hasMountedRef.current = true;
  }, [controls]);

  return (
    <div className="relative">
      <motion.div
        className="w-24 h-24 sm:w-32 sm:h-32 rounded-full overflow-hidden shadow-2xl ring-2 sm:ring-4 ring-black/5 will-change-transform relative"
        style={{ borderRadius: 9999 }}
        animate={controls}
      >
        {/* 3D Sphere Effect - dark slate/charcoal */}
        <div className="w-full h-full relative">
          {/* Base gradient - deep charcoal to slate */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(circle at 40% 40%, #475569 0%, #334155 50%, #1e293b 100%)",
            }}
          />

          {/* Strong top highlight for glossy sphere effect */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 65% 45% at 40% 25%, rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.15) 40%, transparent 65%)",
            }}
          />

          {/* Bottom shadow for depth */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 80% 50% at 50% 90%, rgba(0, 0, 0, 0.6), transparent 60%)",
            }}
          />

          {/* Rim light on left edge */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 25% 60% at 10% 50%, rgba(148, 163, 184, 0.4), transparent 50%)",
            }}
          />

          {/* Right edge darkening for roundness */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 30% 70% at 90% 50%, rgba(15, 23, 42, 0.7), transparent 50%)",
            }}
          />

          {/* Sharp glossy reflection */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 40% 25% at 35% 20%, rgba(255, 255, 255, 0.4), transparent 50%)",
            }}
          />

          {/* Sound wave overlay */}
          <div className="absolute inset-0 flex items-center justify-center">
            <SoundWave isAnimating={isConnected} />
          </div>
        </div>
      </motion.div>
    </div>
  );
});
