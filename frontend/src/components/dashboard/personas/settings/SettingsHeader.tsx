"use client";

import Link from "next/link";
import { ArrowLeft, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SaveButtons } from "./components/SaveButtons";

interface SettingsHeaderProps {
  personaName: string;
  onMenuClick: () => void;
  activeSection?: string;
  hasUnsavedChanges?: boolean;
  isSaving?: boolean;
  onSave?: () => void;
  onDiscard?: () => void;
  onBackClick?: () => void;
}

export function SettingsHeader({
  personaName,
  onMenuClick,
  activeSection,
  hasUnsavedChanges = false,
  isSaving = false,
  onSave,
  onDiscard,
  onBackClick,
}: SettingsHeaderProps) {
  const handleBackClick = (e: React.MouseEvent) => {
    if (onBackClick) {
      e.preventDefault();
      onBackClick();
    }
  };

  return (
    <div className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40">
      <div className="flex h-14 items-center gap-3 px-4">
        {/* Back Button (Desktop) */}
        <Button
          variant="ghost"
          size="sm"
          className="hidden md:flex gap-2"
          asChild={!onBackClick}
          onClick={onBackClick ? handleBackClick : undefined}
        >
          {onBackClick ? (
            <span className="flex items-center gap-2">
              <ArrowLeft className="size-4" />
              Back
            </span>
          ) : (
            <Link href="/dashboard/personas">
              <ArrowLeft className="size-4" />
              Back
            </Link>
          )}
        </Button>

        {/* Mobile Menu Button */}
        <Button
          variant="ghost"
          size="sm"
          className="md:hidden"
          onClick={onMenuClick}
        >
          <Menu className="size-5" />
        </Button>

        {/* Breadcrumb & Title */}
        <div className="flex-1 flex items-center gap-2 min-w-0">
          <div className="hidden md:flex items-center gap-2">
            <div>
              <p className="text-xs text-muted-foreground">Persona Settings</p>
              <h1 className="text-sm font-semibold truncate">{personaName}</h1>
            </div>
            {hasUnsavedChanges && (
              <Badge
                variant="outline"
                className="text-amber-600 border-amber-600"
              >
                Unsaved changes
              </Badge>
            )}
          </div>

          {/* Mobile Active Section Title */}
          <div className="md:hidden flex-1 text-center">
            <h1 className="font-semibold text-sm truncate">{activeSection}</h1>
          </div>
        </div>

        {/* Save Buttons (Desktop & Mobile) */}
        {onSave && onDiscard && (
          <SaveButtons
            hasChanges={hasUnsavedChanges}
            isSaving={isSaving}
            onSave={onSave}
            onDiscard={onDiscard}
          />
        )}

        {/* Mobile Back Button */}
        <Button
          variant="ghost"
          size="sm"
          className="md:hidden"
          asChild={!onBackClick}
          onClick={onBackClick ? handleBackClick : undefined}
        >
          {onBackClick ? (
            <ArrowLeft className="size-4" />
          ) : (
            <Link href="/dashboard/personas">
              <ArrowLeft className="size-4" />
            </Link>
          )}
        </Button>
      </div>
    </div>
  );
}
