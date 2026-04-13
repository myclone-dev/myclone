import type { Metadata } from "next";
import { fetchPersonaMetadata } from "@/lib/queries/persona";
import { ExpertProfilePageClient } from "./client";

interface PageProps {
  params: Promise<{ username: string }>;
}

/**
 * Generate dynamic metadata for SEO and link previews
 * Uses persona data for OpenGraph tags instead of generic ConvoxAI branding
 */
export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { username } = await params;
  const persona = await fetchPersonaMetadata(username);

  if (!persona) {
    return {
      title: "Expert Not Found",
      description: "The requested expert profile could not be found.",
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
 * Expert Profile Page (Root-level username route)
 * Server component that renders metadata and delegates to client component
 */
export default function ExpertProfilePage({ params }: PageProps) {
  return <ExpertProfilePageClient params={params} />;
}
