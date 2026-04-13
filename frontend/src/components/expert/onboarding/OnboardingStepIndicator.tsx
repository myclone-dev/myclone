"use client";

import { Check } from "lucide-react";
import { motion } from "framer-motion";

interface Step {
  number: number;
  title: string;
  description: string;
}

interface OnboardingStepIndicatorProps {
  currentStep: number;
  steps: Step[];
}

export function OnboardingStepIndicator({
  currentStep,
  steps,
}: OnboardingStepIndicatorProps) {
  return (
    <div className="mx-auto mb-6 w-full max-w-3xl sm:mb-8">
      <div className="relative">
        {/* Progress Line */}
        <div className="absolute left-0 right-0 top-5 h-0.5 bg-gray-200 sm:top-6">
          <motion.div
            className="h-full bg-primary"
            initial={{ width: "0%" }}
            animate={{
              width: `${((currentStep - 1) / (steps.length - 1)) * 100}%`,
            }}
            transition={{ duration: 0.5, ease: "easeInOut" }}
          />
        </div>

        {/* Steps */}
        <div className="relative flex justify-between">
          {steps.map((step) => {
            const isCompleted = currentStep > step.number;
            const isCurrent = currentStep === step.number;

            return (
              <div key={step.number} className="flex flex-col items-center">
                {/* Step Circle */}
                <motion.div
                  className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all duration-300 sm:h-12 sm:w-12 ${
                    isCompleted
                      ? "bg-primary border-primary"
                      : isCurrent
                        ? "border-primary bg-white"
                        : "border-gray-300 bg-white"
                  }`}
                  initial={{ scale: 0.8 }}
                  animate={{ scale: 1 }}
                  transition={{ duration: 0.3 }}
                >
                  {isCompleted ? (
                    <Check className="h-5 w-5 text-primary-foreground sm:h-6 sm:w-6" />
                  ) : (
                    <span
                      className={`text-sm font-semibold sm:text-base ${
                        isCurrent ? "text-primary" : "text-gray-400"
                      }`}
                    >
                      {step.number}
                    </span>
                  )}
                </motion.div>

                {/* Step Label */}
                <div className="mt-2 hidden text-center sm:block">
                  <p
                    className={`text-sm font-medium ${
                      isCurrent ? "text-primary" : "text-gray-600"
                    }`}
                  >
                    {step.title}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-400">
                    {step.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Mobile: Show only current step label */}
      <div className="mt-4 text-center sm:hidden">
        <p className="text-sm font-semibold text-primary">
          {steps[currentStep - 1]?.title}
        </p>
        <p className="mt-1 text-xs text-gray-500">
          {steps[currentStep - 1]?.description}
        </p>
      </div>
    </div>
  );
}
