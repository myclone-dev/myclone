"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  UserCircle2,
  MessageSquare,
  BookOpen,
  Settings,
  Trash2,
  ExternalLink,
  Copy,
  Check,
  Mic,
  Shield,
  Globe,
  AlertTriangle,
  DollarSign,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { env } from "@/env";
import { useVoiceClones } from "@/lib/queries/voice-clone";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { usePersonaConversationCount } from "@/lib/queries/conversations";
import { useGetPersonaMonetization, formatPrice } from "@/lib/queries/stripe";

interface PersonaCardProps {
  persona: {
    id: string;
    persona_name: string;
    name: string;
    role: string;
    expertise?: string;
    description?: string;
    slug: string;
    icon?: LucideIcon;
    voice_id?: string;
    greeting_message?: string;
    knowledge_sources_count: number;
    conversations_count: number;
    created_at: string;
    is_private?: boolean;
    suggested_questions?: string[];
    // Email Capture Settings
    email_capture_enabled?: boolean;
    email_capture_message_threshold?: number;
    email_capture_require_fullname?: boolean;
    email_capture_require_phone?: boolean;
    // Calendar Integration Settings
    calendar_enabled?: boolean;
    calendar_url?: string;
    calendar_display_name?: string;
  };
  username: string;
  onManageKnowledge: (personaId: string) => void;
  onManageAccessControl?: (personaId: string) => void;
  onDelete: (personaId: string) => void;
  /** If true, show loading animation in PersonaSettingsDialog (persona is still being created) */
  isCreating?: boolean;
}

export function PersonaCard({
  persona,
  username,
  onManageKnowledge: _onManageKnowledge,
  onManageAccessControl: _onManageAccessControl,
  onDelete,
  isCreating: _isCreating = false,
}: PersonaCardProps) {
  const [isCopied, setIsCopied] = useState(false);
  const baseUrl = env.NEXT_PUBLIC_APP_URL.endsWith("/")
    ? env.NEXT_PUBLIC_APP_URL.slice(0, -1)
    : env.NEXT_PUBLIC_APP_URL;
  const personaUrl = `${baseUrl}/${username}/${persona.slug}`;

  // Fetch voice clones to get the voice name
  const { data: user } = useUserMe();
  const { data: voiceClones } = useVoiceClones(user?.id);
  const currentVoice = voiceClones?.find(
    (v) => v.voice_id === persona.voice_id,
  );

  // Fetch actual conversation count from API
  const { data: conversationCount } = usePersonaConversationCount(persona.id);

  // Fetch monetization settings
  const { data: monetization } = useGetPersonaMonetization(persona.id);

  const handleCopyUrl = () => {
    navigator.clipboard.writeText(personaUrl);
    toast.success("Persona URL copied to clipboard!");
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const PersonaIcon = persona.icon || UserCircle2;

  return (
    <Card className="p-6 gap-3 hover:shadow-lg transition-all duration-300 border-border bg-card w-full overflow-hidden">
      {/* Header */}
      <div className="space-y-3">
        <div className="flex items-center gap-3 min-w-0">
          <PersonaIcon className="w-10 h-10 text-foreground shrink-0" />
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-lg text-foreground truncate">
              {persona.name}
            </h3>
            <p className="text-sm text-muted-foreground truncate">
              {persona.role}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="default" className="font-medium whitespace-nowrap">
            Active
          </Badge>
          {persona.is_private ? (
            <Badge
              variant="outline"
              className="bg-violet-50 text-violet-700 border-violet-200 whitespace-nowrap"
            >
              <Shield className="w-3 h-3 mr-1" />
              Private
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="bg-emerald-50 text-emerald-700 border-emerald-200 whitespace-nowrap"
            >
              <Globe className="w-3 h-3 mr-1" />
              Public
            </Badge>
          )}
          {monetization?.is_active ? (
            <Badge
              variant="outline"
              className="bg-amber-50 text-amber-700 border-amber-200 whitespace-nowrap"
            >
              <DollarSign className="w-3 h-3 mr-1" />
              {formatPrice(monetization.price_cents, monetization.currency)}
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="bg-blue-50 text-blue-700 border-blue-200 whitespace-nowrap"
            >
              Free
            </Badge>
          )}
        </div>
      </div>

      {/* Description */}
      {persona.description && (
        <p className="text-sm text-muted-foreground line-clamp-2">
          {persona.description}
        </p>
      )}

      {/* Stats */}
      <div className="flex flex-wrap items-center gap-3 py-1.5 border-y border-border">
        <div className="flex items-center gap-2 text-sm whitespace-nowrap">
          <BookOpen className="w-4 h-4 text-muted-foreground shrink-0" />
          <span className="font-medium text-foreground">
            {persona.knowledge_sources_count}
          </span>
          <span className="text-muted-foreground">sources</span>
        </div>
        <div className="flex items-center gap-2 text-sm whitespace-nowrap">
          <MessageSquare className="w-4 h-4 text-muted-foreground shrink-0" />
          <span className="font-medium text-foreground">
            {conversationCount ?? 0}
          </span>
          <span className="text-muted-foreground">conversations</span>
        </div>
      </div>

      {/* Voice Info */}
      <div className="bg-secondary/50 rounded-lg p-2">
        <div className="flex items-center gap-2 text-sm min-w-0">
          <Mic className="w-4 h-4 text-amber-700 shrink-0" />
          <span className="text-foreground font-medium truncate">
            {currentVoice ? currentVoice.name : "Default voice"}
          </span>
        </div>
      </div>

      {/* Primary Actions */}
      <div className="space-y-2 pt-2">
        {/* Warning Chip - No Knowledge Sources */}
        {persona.knowledge_sources_count === 0 && (
          <div className="rounded-md bg-amber-50 border border-amber-200 p-2 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800 leading-relaxed">
              This persona won&apos;t work properly until you add at least one
              knowledge source.
            </p>
          </div>
        )}

        {/* View Live - Primary CTA */}
        <div className="flex items-center gap-2">
          {persona.knowledge_sources_count > 0 ? (
            <Button
              variant="default"
              className="flex-1 cursor-pointer"
              size="sm"
              asChild
            >
              <Link href={`/${username}/${persona.slug}`} target="_blank">
                <ExternalLink className="w-4 h-4 mr-2 shrink-0" />
                <span className="truncate">View Live</span>
              </Link>
            </Button>
          ) : (
            <Button
              variant="default"
              className="flex-1 cursor-pointer"
              size="sm"
              asChild
            >
              <Link href="/dashboard/knowledge">
                <BookOpen className="w-4 h-4 mr-2 shrink-0" />
                <span className="truncate">Add Knowledge First</span>
              </Link>
            </Button>
          )}

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopyUrl}
                className="cursor-pointer shrink-0"
              >
                {isCopied ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="text-xs">
              <p>{isCopied ? "Link copied!" : "Copy persona link"}</p>
            </TooltipContent>
          </Tooltip>
        </div>

        {/* Management Actions */}
        <TooltipProvider delayDuration={200}>
          <div className="flex items-center gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  className="flex-1 cursor-pointer"
                  size="sm"
                  asChild
                >
                  <Link href={`/dashboard/personas/${persona.id}/settings`}>
                    <Settings className="w-4 h-4 mr-2" />
                    Settings
                  </Link>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                <p>Manage all persona settings</p>
              </TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="cursor-pointer text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  onClick={() => onDelete(persona.id)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                <p>Delete Persona</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </TooltipProvider>
      </div>
    </Card>
  );
}
