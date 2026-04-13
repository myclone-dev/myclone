"use client";

import { useEffect } from "react";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AlertCircle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { useUserPersonas } from "@/lib/queries/persona";
import { useWidgetTokens } from "@/lib/queries/users";
import { WidgetConfig } from "../types";

interface EssentialsTabProps {
  config: WidgetConfig;
  setConfig: (config: WidgetConfig) => void;
}

export function EssentialsTab({ config, setConfig }: EssentialsTabProps) {
  const { data: user } = useUserMe();
  const { data: personasData, isLoading: personasLoading } = useUserPersonas(
    user?.id || "",
  );
  const { data: tokensData, isLoading: tokensLoading } = useWidgetTokens();

  const personas = personasData?.personas || [];
  const tokens = (tokensData?.tokens || []).filter((t) => t.is_active);

  const selectedPersona = personas.find(
    (p) => p.persona_name === config.personaName,
  );

  // Auto-select first persona if none selected
  useEffect(() => {
    if (!personasLoading && personas.length > 0 && !config.personaName) {
      const firstPersona = personas[0];
      setConfig({
        ...config,
        personaName: firstPersona.persona_name,
        welcomeMessage: firstPersona.greeting_message || config.welcomeMessage,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personas, personasLoading]);

  // Auto-select first token if none selected
  useEffect(() => {
    if (!tokensLoading && tokens.length > 0 && !config.widgetToken) {
      setConfig({
        ...config,
        widgetToken: tokens[0].token,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokens, tokensLoading]);

  const handlePersonaChange = (personaName: string) => {
    const persona = personas.find((p) => p.persona_name === personaName);
    if (persona) {
      setConfig({
        ...config,
        personaName: persona.persona_name,
        welcomeMessage: persona.greeting_message || config.welcomeMessage,
      });
    }
  };

  const handleTokenChange = (token: string) => {
    setConfig({
      ...config,
      widgetToken: token,
    });
  };

  return (
    <>
      {/* Persona Selector */}
      <Card className="p-4">
        <h4 className="mb-3 text-sm font-semibold text-slate-700">
          Select Persona
        </h4>
        <p className="mb-3 text-xs text-slate-500">
          Choose which AI persona users will interact with
        </p>

        {personasLoading ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="text-sm text-slate-600">Loading personas...</p>
          </div>
        ) : personas.length > 0 ? (
          <>
            <Select
              value={config.personaName || ""}
              onValueChange={handlePersonaChange}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a persona" />
              </SelectTrigger>
              <SelectContent>
                {personas.map((persona) => (
                  <SelectItem key={persona.id} value={persona.persona_name}>
                    {persona.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {selectedPersona?.greeting_message && (
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs text-slate-600">
                  <span className="font-medium">Welcome message:</span>{" "}
                  {selectedPersona.greeting_message}
                </p>
              </div>
            )}
          </>
        ) : (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <div className="mb-3 flex items-start gap-3">
              <AlertCircle className="mt-0.5 size-5 shrink-0 text-amber-600" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-amber-900">
                  No personas available
                </p>
                <p className="mt-1 text-xs text-amber-700">
                  Create your first persona to get started. Personas define how
                  your AI clone responds to users.
                </p>
              </div>
            </div>
            <Button size="sm" variant="outline" asChild className="w-full">
              <Link href="/dashboard/personas">
                <ExternalLink className="mr-2 size-4" />
                Go to Personas Page
              </Link>
            </Button>
          </div>
        )}
      </Card>

      {/* Token Selector */}
      <Card className="p-4">
        <h4 className="mb-3 text-sm font-semibold text-slate-700">
          Select API Token
        </h4>
        <p className="mb-3 text-xs text-slate-500">
          Choose the token to authenticate your widget
        </p>

        {tokensLoading ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="text-sm text-slate-600">Loading tokens...</p>
          </div>
        ) : tokens.length > 0 ? (
          <Select
            value={config.widgetToken || ""}
            onValueChange={handleTokenChange}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select a token" />
            </SelectTrigger>
            <SelectContent>
              {tokens.map((token) => (
                <SelectItem key={token.id} value={token.token}>
                  {token.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <div className="mb-3 flex items-start gap-3">
              <AlertCircle className="mt-0.5 size-5 shrink-0 text-amber-600" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-amber-900">
                  No tokens available
                </p>
                <p className="mt-1 text-xs text-amber-700">
                  Create a token to authenticate your widget. Tokens are
                  required for all widget API calls.
                </p>
              </div>
            </div>
            <p className="text-xs text-amber-700">
              Switch to the &quot;API Tokens&quot; tab above to create your
              first token.
            </p>
          </div>
        )}
      </Card>
    </>
  );
}
