"use client";

import { AvatarTab } from "../../PersonaSettingsDialog/tabs/AvatarTab";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import type { Persona } from "../../PersonaSettingsDialog/types";

interface AvatarSectionProps {
  personaId: string;
  persona: Persona;
}

/**
 * Avatar section for full-page persona settings.
 * Avatar changes are saved immediately via mutations, so no unsaved changes tracking needed.
 */
export function AvatarSection({ personaId, persona }: AvatarSectionProps) {
  const { data: user } = useUserMe();

  return (
    <AvatarTab
      personaId={personaId}
      personaName={persona.name}
      currentAvatarUrl={persona.persona_avatar_url}
      userAvatarUrl={user?.avatar ?? undefined}
    />
  );
}
