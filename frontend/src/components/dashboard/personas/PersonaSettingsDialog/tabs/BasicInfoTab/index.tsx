"use client";

import { motion } from "motion/react";
import type { BasicInfoFormData, Persona } from "../../types";
import { BasicInfoForm } from "./BasicInfoForm";
import { SuggestedQuestions } from "./SuggestedQuestions";

interface BasicInfoTabProps {
  persona: Persona;
  basicInfo: BasicInfoFormData;
  onChange: (updates: Partial<BasicInfoFormData>) => void;
}

/**
 * Basic Info Tab
 * Contains basic persona information and suggested questions
 */
export function BasicInfoTab({
  persona,
  basicInfo,
  onChange,
}: BasicInfoTabProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="space-y-4 sm:space-y-6 max-w-5xl mx-auto"
    >
      <BasicInfoForm
        persona={persona}
        basicInfo={basicInfo}
        onChange={onChange}
      />
      <SuggestedQuestions personaId={persona.id} />
    </motion.div>
  );
}
