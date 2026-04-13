"use client";

import { useState } from "react";
import { Power, MessageSquareOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface EndSessionButtonProps {
  /** Callback when user confirms ending the session */
  onEndSession: () => void;
  /** Whether the button should be disabled */
  disabled?: boolean;
  /** Optional className for custom styling */
  className?: string;
  /** Container element for the dialog portal - useful for embed widgets */
  dialogContainer?: HTMLElement | null;
}

/**
 * Small button to manually end the text chat session.
 * Includes confirmation dialog to prevent accidental disconnects.
 */
export function EndSessionButton({
  onEndSession,
  disabled = false,
  className = "",
  dialogContainer,
}: EndSessionButtonProps) {
  const { t } = useTranslation();
  const [showConfirmation, setShowConfirmation] = useState(false);

  const handleEndSession = () => {
    setShowConfirmation(false);
    onEndSession();
  };

  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowConfirmation(true)}
            disabled={disabled}
            className={`h-8 w-8 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors ${className}`}
            aria-label={t("voice.buttons.endSession")}
          >
            <Power className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="text-xs">
          {t("voice.buttons.endSession")}
        </TooltipContent>
      </Tooltip>

      <AlertDialog open={showConfirmation} onOpenChange={setShowConfirmation}>
        <AlertDialogContent
          className="max-w-[min(320px,calc(100%-2rem))] gap-0 p-5"
          container={dialogContainer}
        >
          {/* Icon and Content */}
          <div className="flex gap-3">
            <div className="shrink-0 w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
              <MessageSquareOff className="w-5 h-5 text-amber-600" />
            </div>
            <div className="flex-1 min-w-0">
              <AlertDialogHeader className="space-y-1 p-0">
                <AlertDialogTitle className="text-base font-semibold text-gray-900">
                  {t("session.endConfirm.title")}
                </AlertDialogTitle>
                <AlertDialogDescription className="text-sm text-gray-500">
                  {t("session.endConfirm.description")}
                </AlertDialogDescription>
              </AlertDialogHeader>
            </div>
          </div>

          {/* Buttons */}
          <AlertDialogFooter className="flex-row gap-2 mt-4 sm:space-x-0">
            <AlertDialogCancel className="flex-1 m-0 h-9 text-sm">
              {t("common.cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleEndSession}
              className="flex-1 m-0 h-9 text-sm bg-gray-900 hover:bg-gray-800 text-white"
            >
              {t("voice.buttons.endSession")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
