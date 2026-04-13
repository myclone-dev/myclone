"use client";

import React from "react";
import { motion } from "framer-motion";

interface AmbientWavesProps {
  active: boolean;
}

const WAVE1_ANIMATE = { scale: [1, 1.05, 1], opacity: [0.12, 0.18, 0.12] };
const WAVE1_TRANSITION = {
  duration: 5.2,
  repeat: Infinity,
  ease: "easeInOut" as const,
};

const WAVE2_ANIMATE = { scale: [1, 1.07, 1], opacity: [0.08, 0.14, 0.08] };
const WAVE2_TRANSITION = {
  duration: 6.4,
  repeat: Infinity,
  ease: "easeInOut" as const,
  delay: 0.6,
};

const WAVE_OFF = { opacity: 0, scale: 1 };
const WAVE_OFF_TRANSITION = { duration: 0.2 };

export const AmbientWaves = React.memo(function AmbientWaves({
  active,
}: AmbientWavesProps) {
  return (
    <>
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -inset-3 sm:-inset-4 rounded-full bg-black/15 blur-[2px] z-0"
        initial={false}
        animate={active ? WAVE1_ANIMATE : WAVE_OFF}
        transition={active ? WAVE1_TRANSITION : WAVE_OFF_TRANSITION}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -inset-5 sm:-inset-6 rounded-full bg-black/10 blur-[3px] z-0"
        initial={false}
        animate={active ? WAVE2_ANIMATE : WAVE_OFF}
        transition={active ? WAVE2_TRANSITION : WAVE_OFF_TRANSITION}
      />
    </>
  );
});
