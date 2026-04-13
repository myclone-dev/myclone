"use client";

import { use } from "react";
import { PersonaPageContent } from "@/components/persona/PersonaPageContent";

interface PersonaPageClientProps {
  params: Promise<{ username: string; persona_name: string }>;
}

/**
 * Client component for Specific Persona Page
 * Renders persona using shared PersonaPageContent component
 */
export function PersonaPageClient({ params }: PersonaPageClientProps) {
  const { username, persona_name } = use(params);

  return <PersonaPageContent username={username} personaName={persona_name} />;
}
