import { PersonaSettingsPage } from "@/components/dashboard/personas/settings/PersonaSettingsPage";

export default async function PersonaSettingsRoute({
  params,
}: {
  params: Promise<{ personaId: string }>;
}) {
  const { personaId } = await params;
  return <PersonaSettingsPage personaId={personaId} />;
}

export const metadata = {
  title: "Persona Settings | Expert Clone",
  description: "Configure your persona settings",
};
