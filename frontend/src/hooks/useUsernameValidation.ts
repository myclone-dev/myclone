import { useState, useEffect } from "react";
import { validateUsername } from "@/lib/utils/usernameValidation";
import { useUsernameAvailability } from "@/lib/queries/users";

export interface UsernameValidationState {
  isValid: boolean;
  isChecking: boolean;
  error?: string;
  processedUsername?: string;
}

/**
 * Custom hook for real-time username validation with API check
 *
 * @param username - The username to validate
 * @param debounceMs - Debounce delay in milliseconds (default: 500ms)
 * @returns Validation state with availability info
 */
export function useUsernameValidation(
  username: string,
  debounceMs: number = 500,
): UsernameValidationState {
  const [debouncedUsername, setDebouncedUsername] = useState<string | null>(
    null,
  );

  // First, validate format locally (instant feedback)
  const formatValidation = validateUsername(username);

  // Debounce the username for API check
  useEffect(() => {
    // Don't validate empty string or invalid format
    if (
      !username ||
      username.trim().length === 0 ||
      !formatValidation.isValid
    ) {
      setDebouncedUsername(null);
      return;
    }

    // Set up debounce timer
    const timeoutId = setTimeout(() => {
      setDebouncedUsername(username.trim().toLowerCase());
    }, debounceMs);

    // Cleanup timeout on unmount or username change
    return () => clearTimeout(timeoutId);
  }, [username, debounceMs, formatValidation.isValid]);

  // Check availability with backend (only if format is valid)
  const availabilityQuery = useUsernameAvailability(debouncedUsername, {
    enabled: !!debouncedUsername && formatValidation.isValid,
  });

  // Return validation state based on format + availability
  if (!username || username.trim().length === 0) {
    return {
      isValid: false,
      isChecking: false,
    };
  }

  // Format is invalid - return format error immediately
  if (!formatValidation.isValid) {
    return {
      isValid: false,
      isChecking: false,
      error: formatValidation.error,
    };
  }

  // Format is valid, but still waiting for debounce or API check
  if (availabilityQuery.isLoading || !debouncedUsername) {
    return {
      isValid: false,
      isChecking: true,
      processedUsername: formatValidation.processedUsername,
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
      error: availabilityQuery.data.reason || undefined,
      processedUsername: formatValidation.processedUsername,
    };
  }

  // Default state (should not reach here)
  return {
    isValid: false,
    isChecking: false,
  };
}
