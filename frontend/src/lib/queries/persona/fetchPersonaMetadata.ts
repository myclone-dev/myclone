import { env } from "@/env";
import type { PersonaDetails } from "./interface";

/**
 * Server-side fetch function for persona metadata
 * Used in generateMetadata() for OpenGraph tags
 * This runs on the server at request time, not in the browser
 */
export async function fetchPersonaMetadata(
  username: string,
  personaName?: string,
): Promise<PersonaDetails | null> {
  try {
    const params = personaName
      ? `?persona_name=${encodeURIComponent(personaName)}`
      : "";

    const response = await fetch(
      `${env.NEXT_PUBLIC_API_URL}/expert/${username}/public${params}`,
      {
        // Cache for 60 seconds to avoid hitting API on every request
        next: { revalidate: 60 },
      },
    );

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch {
    return null;
  }
}
