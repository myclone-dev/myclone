"use client";

import { useState } from "react";
import { useUserMe } from "@/lib/queries/users";
import { useUserPersonas } from "@/lib/queries/persona";
import { useUserConversations } from "@/lib/queries/conversations";
import { ConversationList } from "@/components/dashboard/conversations/ConversationList";
import { PageLoader } from "@/components/ui/page-loader";
import { Badge } from "@/components/ui/badge";
import { useTour } from "@/hooks/useTour";
import { TOUR_KEYS } from "@/config/tour-keys";

/**
 * Conversations Page
 * View and manage all conversations with your AI clone
 */
export default function ConversationsPage() {
  const { data: user, isLoading } = useUserMe();
  const { data: personasData } = useUserPersonas(user?.id || "");
  const { data: conversationsData } = useUserConversations(user?.id);
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(
    null,
  );

  // Auto-start summary feature tour with cleanup on unmount
  useTour({
    tourName: "conversation-summary-feature",
    storageKey: TOUR_KEYS.SUMMARY_FEATURE_TOUR,
    shouldStart: () => {
      const conversations = conversationsData?.conversations || [];
      return conversations.length > 0;
    },
    dependencies: [user, conversationsData],
  });

  if (isLoading || !user) {
    return <PageLoader />;
  }

  const personas = personasData?.personas || [];

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
      {/* Clean Header */}
      <div className="mb-6 space-y-4">
        {/* Title Section */}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Conversations
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            View and manage all conversations with your AI clone
          </p>
        </div>

        {/* Persona Filter Chips - Horizontally scrollable on mobile */}
        {personas.length > 0 && (
          <div className="flex items-start gap-2 sm:gap-3 sm:flex-wrap sm:items-center">
            <span className="text-xs sm:text-sm text-muted-foreground shrink-0 pt-1 sm:pt-0">
              Filter:
            </span>
            <div className="flex gap-2 overflow-x-auto pb-2 sm:pb-0 sm:flex-wrap -mx-4 px-4 sm:mx-0 sm:px-0 scrollbar-hide">
              {/* All Personas Chip */}
              <Badge
                variant={!selectedPersonaId ? "default" : "outline"}
                className={`cursor-pointer px-3 py-1 text-xs transition-colors shrink-0 ${
                  !selectedPersonaId
                    ? "bg-black text-yellow-bright hover:bg-black/90"
                    : "hover:bg-muted"
                }`}
                onClick={() => setSelectedPersonaId(null)}
              >
                All Personas
              </Badge>

              {/* Individual Persona Chips */}
              {personas.map((persona) => {
                const isSelected = selectedPersonaId === persona.id;
                return (
                  <Badge
                    key={persona.id}
                    variant={isSelected ? "default" : "outline"}
                    className={`cursor-pointer px-3 py-1 text-xs transition-colors shrink-0 ${
                      isSelected
                        ? "bg-black text-yellow-bright hover:bg-black/90"
                        : "hover:bg-muted"
                    }`}
                    onClick={() => setSelectedPersonaId(persona.id)}
                  >
                    {persona.name}
                  </Badge>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Conversation List */}
      <ConversationList userId={user.id} personaId={selectedPersonaId} />
    </div>
  );
}
