"use client";

import React from "react";
import { motion } from "framer-motion";

interface SoundWaveProps {
  isAnimating: boolean;
}

export const SoundWave = React.memo(function SoundWave({
  isAnimating,
}: SoundWaveProps) {
  const bars = [
    { height: "h-2.5", delay: 0 },
    { height: "h-5", delay: 0.1 },
    { height: "h-4", delay: 0.2 },
    { height: "h-6", delay: 0.3 },
    { height: "h-5", delay: 0.4 },
  ];

  return (
    <div className="flex items-center gap-1">
      {bars.map((bar, index) => (
        <motion.div
          key={index}
          className={`w-1 ${bar.height} bg-slate-300 rounded-sm`}
          animate={
            isAnimating
              ? {
                  scaleY: [1, 1.8, 1],
                }
              : { scaleY: 1 }
          }
          transition={
            isAnimating
              ? {
                  duration: 0.8,
                  repeat: Infinity,
                  ease: "easeInOut",
                  delay: bar.delay,
                }
              : {
                  duration: 0.3,
                  ease: "easeOut",
                }
          }
        />
      ))}
    </div>
  );
});
