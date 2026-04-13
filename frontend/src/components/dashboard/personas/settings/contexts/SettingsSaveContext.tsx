import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from "react";

interface SettingsSaveContextValue {
  hasUnsavedChanges: boolean;
  isSaving: boolean;
  setHasUnsavedChanges: (value: boolean) => void;
  setIsSaving: (value: boolean) => void;
  registerSaveHandler: (handler: () => Promise<void>) => void;
  registerDiscardHandler: (handler: () => void) => void;
  handleSave: () => Promise<void>;
  handleDiscard: () => void;
}

const SettingsSaveContext = createContext<SettingsSaveContextValue | null>(
  null,
);

export function SettingsSaveProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const saveHandlerRef = useRef<(() => Promise<void>) | null>(null);
  const discardHandlerRef = useRef<(() => void) | null>(null);

  const registerSaveHandler = useCallback((handler: () => Promise<void>) => {
    saveHandlerRef.current = handler;
  }, []);

  const registerDiscardHandler = useCallback((handler: () => void) => {
    discardHandlerRef.current = handler;
  }, []);

  const handleSave = useCallback(async () => {
    if (saveHandlerRef.current) {
      await saveHandlerRef.current();
    }
  }, []);

  const handleDiscard = useCallback(() => {
    if (discardHandlerRef.current) {
      discardHandlerRef.current();
    }
  }, []);

  return (
    <SettingsSaveContext.Provider
      value={{
        hasUnsavedChanges,
        isSaving,
        setHasUnsavedChanges,
        setIsSaving,
        registerSaveHandler,
        registerDiscardHandler,
        handleSave,
        handleDiscard,
      }}
    >
      {children}
    </SettingsSaveContext.Provider>
  );
}

export function useSettingsSave() {
  const context = useContext(SettingsSaveContext);
  if (!context) {
    throw new Error("useSettingsSave must be used within SettingsSaveProvider");
  }
  return context;
}
