import type { Metadata } from "next";
import { fetchPersonaMetadata } from "@/lib/queries/persona";
import { PersonaPageClient } from "./client";

interface PageProps {
  params: Promise<{ username: string; persona_name: string }>;
}

/**
 * Generate dynamic metadata for SEO and link previews
 * Uses persona data for OpenGraph tags instead of generic ConvoxAI branding
 */
export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { username, persona_name } = await params;
  const persona = await fetchPersonaMetadata(username, persona_name);

  if (!persona) {
    return {
      title: "Persona Not Found",
      description: "The requested persona could not be found.",
    };
  }

  const title = persona.name;
  const description = persona.role
    ? `${persona.role}${persona.company ? ` at ${persona.company}` : ""}`
    : `AI-powered digital clone of ${persona.name}`;

  // Use persona-specific avatar if available, otherwise fall back to user profile avatar
  const avatarUrl = persona.persona_avatar_url || persona.avatar;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "profile",
      images: avatarUrl ? [{ url: avatarUrl }] : [],
    },
    twitter: {
      card: "summary",
      title,
      description,
      images: avatarUrl ? [avatarUrl] : [],
    },
  };
}

/**
 * Specific Persona Page
 * Server component that renders metadata and delegates to client component
 */
export default function PersonaPage({ params }: PageProps) {
  return <PersonaPageClient params={params} />;
}
