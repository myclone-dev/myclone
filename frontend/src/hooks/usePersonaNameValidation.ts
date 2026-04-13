import { useState, useEffect } from "react";
import { useCheckPersonaName } from "@/lib/queries/persona";

export interface PersonaNameValidationState {
  isValid: boolean;
  isChecking: boolean;
  error?: string;
  slugifiedName?: string;
}

/**
 * Custom hook for real-time persona name validation with API check
 * Follows the same pattern as useUsernameValidation
 *
 * @param personaName - The persona name to validate
 * @param debounceMs - Debounce delay in milliseconds (default: 500ms)
 * @returns Validation state with availability info
 */
export function usePersonaNameValidation(
  personaName: string,
  debounceMs: number = 500,
): PersonaNameValidationState {
  const [debouncedName, setDebouncedName] = useState<string | null>(null);

  // Debounce the persona name for API check
  useEffect(() => {
    // Don't validate empty string or too short
    if (!personaName || personaName.trim().length < 3) {
      setDebouncedName(null);
      return;
    }

    // Set up debounce timer
    const timeoutId = setTimeout(() => {
      setDebouncedName(personaName.trim());
    }, debounceMs);

    // Cleanup timeout on unmount or name change
    return () => clearTimeout(timeoutId);
  }, [personaName, debounceMs]);

  // Check availability with backend (only if name is long enough)
  const availabilityQuery = useCheckPersonaName(debouncedName, {
    enabled: !!debouncedName && debouncedName.length >= 3,
  });

  // Return validation state based on availability
  if (!personaName || personaName.trim().length === 0) {
    return {
      isValid: false,
      isChecking: false,
    };
  }

  // Name is too short - instant feedback
  if (personaName.trim().length < 3) {
    return {
      isValid: false,
      isChecking: false,
      error: "Persona name must be at least 3 characters",
    };
  }

  // Name is valid length, but still waiting for debounce or API check
  if (availabilityQuery.isLoading || !debouncedName) {
    return {
      isValid: false,
      isChecking: true,
    };
  }

  // API check failed
  if (availabilityQuery.isError) {
    return {
      isValid: false,
      isChecking: false,
      error: "Unable to check availability. Please try again.",
    };
  }

  // API check completed
  if (availabilityQuery.data) {
    return {
      isValid: availabilityQuery.data.available,
      isChecking: false,
      error: availabilityQuery.data.available
        ? undefined
        : availabilityQuery.data.reason || undefined,
      slugifiedName: availabilityQuery.data.persona_name,
    };
  }

  // Default state (should not reach here)
  return {
    isValid: false,
    isChecking: false,
  };
}
