import { useEffect, useRef, useState, useCallback } from "react";

/**
 * Hook to detect unsaved changes by comparing current state with original state
 * @param currentValue - Current form/state value
 * @param options - Configuration options
 * @returns hasChanges flag and utility functions
 */
export function useUnsavedChanges<T>(
  currentValue: T,
  options: {
    enabled?: boolean;
  } = {},
) {
  const { enabled = true } = options;
  const [originalValue, setOriginalValue] = useState<T>(currentValue);
  const isFirstRender = useRef(true);
  // Store the value that was saved - used to detect when refetch brings matching data
  const savedValueRef = useRef<string | null>(null);

  // Initialize original value on first render
  useEffect(() => {
    if (isFirstRender.current) {
      setOriginalValue(currentValue);
      isFirstRender.current = false;
    }
  }, [currentValue]);

  // Deep comparison to detect changes
  const currentValueStr = JSON.stringify(currentValue);
  const originalValueStr = JSON.stringify(originalValue);
  const hasChanges = enabled ? currentValueStr !== originalValueStr : false;

  // Reset current value to original (discard changes)
  const reset = useCallback(() => {
    return originalValue;
  }, [originalValue]);

  // Update original value (after successful save)
  // Takes an optional value to use instead of currentValue - useful when state
  // is about to be reset by a refetch
  const markAsSaved = useCallback(
    (savedValue?: T) => {
      const valueToSave = savedValue !== undefined ? savedValue : currentValue;
      const valueStr = JSON.stringify(valueToSave);
      setOriginalValue(valueToSave);
      // Store the saved value string so we can detect when refetch brings it back
      savedValueRef.current = valueStr;
    },
    [currentValue],
  );

  // Mark that we're about to save - clears any previous saved value
  const markSaveStarted = useCallback(() => {
    savedValueRef.current = null;
  }, []);

  // Sync original value when currentValue changes to match what was saved
  // This handles the case where refetch updates the state after save
  useEffect(() => {
    if (savedValueRef.current !== null) {
      // If currentValue now matches what we saved, sync originalValue
      // This handles the refetch bringing back the saved data
      if (currentValueStr === savedValueRef.current) {
        setOriginalValue(currentValue);
        savedValueRef.current = null;
      }
    }
  }, [currentValue, currentValueStr]);

  return {
    hasChanges,
    reset,
    markAsSaved,
    markSaveStarted,
    originalValue,
  };
}
