"use client";

import { use } from "react";
import { PersonaPageContent } from "@/components/persona/PersonaPageContent";

interface ExpertProfilePageClientProps {
  params: Promise<{ username: string }>;
}

/**
 * Client component for Expert Profile Page
 * Renders default persona using shared PersonaPageContent component
 */
export function ExpertProfilePageClient({
  params,
}: ExpertProfilePageClientProps) {
  const { username } = use(params);

  return <PersonaPageContent username={username} personaName="default" />;
}
