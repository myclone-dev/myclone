"use client";

import { useUserMe } from "@/lib/queries/users/useUserMe";
import { useScrapingJobs } from "@/lib/queries/knowledge/useScrapingJobs";
import { useUserConversations } from "@/lib/queries/conversations/useConversations";
import { useUserPersonas } from "@/lib/queries/persona";
import { useVoiceClones } from "@/lib/queries/voice-clone";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SetupGuide } from "@/components/dashboard/SetupGuide";
import {
  MessageSquare,
  Database,
  ExternalLink,
  CheckCircle2,
  Clock,
  XCircle,
  Linkedin,
  Twitter,
  Globe,
  FileText,
  UserPlus,
  Music,
  Video,
  Mic,
  HelpCircle,
} from "lucide-react";
import Link from "next/link";
import { useNextStep } from "nextstepjs";
import { useEffect, useState } from "react";
import {
  hasCompletedKnowledgeLibrary,
  hasCompletedVoiceClone,
  markKnowledgeLibraryComplete,
  markVoiceCloneComplete,
  setCurrentUsername,
} from "@/lib/utils/setupProgress";
import {
  shouldShowOnboarding,
  startOnboarding,
} from "@/lib/utils/onboardingProgress";
import { useTour } from "@/hooks/useTour";
import { TOUR_KEYS } from "@/config/tour-keys";

const SETUP_GUIDE_DISMISSED_KEY = "hasSetupGuideDismissed";

// Mobile breakpoint - matches Tailwind's md breakpoint (768px)
const MOBILE_BREAKPOINT = 768;

/**
 * Get the appropriate tour name based on viewport width
 * Mobile tour excludes sidebar steps since sidebar is hidden in a Sheet
 */
function getTourName(): string {
  if (typeof window === "undefined") return "dashboard-welcome";
  return window.innerWidth < MOBILE_BREAKPOINT
    ? "dashboard-welcome-mobile"
    : "dashboard-welcome";
}

/**
 * Dashboard Overview - Shows profile summary and key statistics
 * Auto-starts tour for first-time users
 */
export default function DashboardPage() {
  const { data: user, isLoading: userLoading } = useUserMe();
  const { data: scrapingResponse } = useScrapingJobs(user?.id);
  const scrapingData = scrapingResponse?.jobs || [];
  const { data: conversationsData } = useUserConversations(user?.id);
  const { data: personasData } = useUserPersonas(user?.id || "");
  const { data: voiceClones } = useVoiceClones(user?.id);
  const { startNextStep } = useNextStep();
  const [hasCheckedGuidance, setHasCheckedGuidance] = useState(false);

  // Cleanup tours on unmount to prevent persistence across navigation
  // Note: Dashboard uses manual tour initialization due to viewport-dependent tour names
  useTour();

  // Initialize setup guide state from localStorage to prevent flickering
  const [showSetupGuide, setShowSetupGuide] = useState(() => {
    if (typeof window === "undefined") return true;
    const dismissed = localStorage.getItem(SETUP_GUIDE_DISMISSED_KEY);
    // Don't show if dismissed OR if both steps are already completed
    return (
      dismissed !== "true" &&
      !(hasCompletedKnowledgeLibrary() && hasCompletedVoiceClone())
    );
  });

  // Use localStorage cache for immediate render, update from API when data arrives
  const [hasKnowledge, setHasKnowledge] = useState(() =>
    hasCompletedKnowledgeLibrary(),
  );
  const [hasVoice, setHasVoice] = useState(() => hasCompletedVoiceClone());

  // Store username for navigation purposes
  useEffect(() => {
    if (user?.username) {
      setCurrentUsername(user.username);
    }
  }, [user?.username]);

  // Update localStorage when API data confirms completion
  useEffect(() => {
    const apiHasKnowledge = (scrapingData?.length || 0) > 0;
    const apiHasVoice = (voiceClones?.length || 0) > 0;

    // Update localStorage if API shows completion but cache doesn't
    if (apiHasKnowledge && !hasKnowledge) {
      markKnowledgeLibraryComplete();
      setHasKnowledge(true);
    }

    if (apiHasVoice && !hasVoice) {
      markVoiceCloneComplete();
      setHasVoice(true);
    }

    // Hide setup guide if both are complete
    if (apiHasKnowledge && apiHasVoice && showSetupGuide) {
      setShowSetupGuide(false);
    }
  }, [scrapingData, voiceClones, hasKnowledge, hasVoice, showSetupGuide]);

  // Auto-start dashboard welcome tour for first-time users
  useEffect(() => {
    if (!user || hasCheckedGuidance) return;

    const hasSeenGuidance = localStorage.getItem(TOUR_KEYS.DASHBOARD_GUIDANCE);

    // For first-time users, show the dashboard tour FIRST
    if (!hasSeenGuidance) {
      // Check if this is truly a first-time onboarding user
      if (shouldShowOnboarding()) {
        startOnboarding();
      }

      // Start the appropriate tour based on viewport size
      // Mobile tour excludes sidebar steps since sidebar is in a Sheet
      if (typeof startNextStep === "function") {
        const tourName = getTourName();

        // Use RAF to ensure DOM is ready and NextStepJS is initialized
        requestAnimationFrame(() => {
          startNextStep(tourName);
          localStorage.setItem(TOUR_KEYS.DASHBOARD_GUIDANCE, "true");
          setHasCheckedGuidance(true);
        });
      }
    } else {
      setHasCheckedGuidance(true);
    }
  }, [user, hasCheckedGuidance, startNextStep]);

  if (userLoading) {
    return (
      <div className="container max-w-6xl py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="h-4 w-96 bg-muted rounded" />
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Calculate knowledge library stats
  const totalJobs = scrapingData?.length || 0;
  const completedJobs =
    scrapingData?.filter((job) => job.status === "completed").length || 0;
  const processingJobs =
    scrapingData?.filter((job) => job.status === "processing").length || 0;
  const failedJobs =
    scrapingData?.filter((job) => job.status === "failed").length || 0;

  // Get connected sources
  const connectedSources = new Set(
    scrapingData
      ?.filter((job) => job.status === "completed")
      .map((job) => job.source_type) || [],
  );

  // Conversation stats from API
  const totalConversations = conversationsData?.total || 0;

  // Get conversation type breakdown - prefer backend aggregates if available
  const textConversations =
    conversationsData?.text_conversations ??
    conversationsData?.conversations?.filter(
      (c) => c.conversation_type === "text",
    ).length ??
    0;
  const voiceConversations =
    conversationsData?.voice_conversations ??
    conversationsData?.conversations?.filter(
      (c) => c.conversation_type === "voice",
    ).length ??
    0;

  const sourceIcons = {
    linkedin: Linkedin,
    twitter: Twitter,
    website: Globe,
    pdf: FileText,
    audio: Music,
    video: Video,
  };

  // Get personas from API
  const personas = personasData?.personas || [];

  return (
    <div className="max-w-7xl mx-auto py-8 space-y-8 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div
        id="dashboard-header"
        className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"
      >
        <div className="space-y-1 sm:space-y-2">
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Dashboard Overview
          </h1>
          <p className="text-sm text-muted-foreground sm:text-base">
            Welcome back! Here&apos;s a summary of your AI clone profile
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => startNextStep(getTourName())}
          className="w-full gap-2 sm:w-auto"
        >
          <HelpCircle className="size-4" />
          Take a Tour
        </Button>
      </div>

      {/* Setup Guide - Show when knowledge library or voice clone is missing */}
      {showSetupGuide && (
        <SetupGuide
          hasKnowledgeLibrary={hasKnowledge}
          hasVoiceClone={hasVoice}
          onDismiss={() => {
            setShowSetupGuide(false);
            localStorage.setItem(SETUP_GUIDE_DISMISSED_KEY, "true");
          }}
        />
      )}

      {/* Quick Actions */}
      <Card id="quick-actions-card">
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Link href="/dashboard/knowledge" className="group">
              <div className="h-auto rounded-md border bg-card px-3 py-4 shadow-xs transition-all hover:border-primary/30 hover:bg-primary/10 flex flex-col items-center justify-center gap-2 min-h-[100px]">
                <Database className="size-5 transition-colors group-hover:text-primary sm:size-6" />
                <span className="text-center text-xs font-medium sm:text-sm">
                  Add Knowledge
                </span>
              </div>
            </Link>
            <Link href="/dashboard/widgets" className="group">
              <div className="h-auto rounded-md border bg-card px-3 py-4 shadow-xs transition-all hover:border-primary/30 hover:bg-primary/10 flex flex-col items-center justify-center gap-2 min-h-[100px]">
                <Globe className="size-5 transition-colors group-hover:text-primary sm:size-6" />
                <span className="text-center text-xs font-medium sm:text-sm">
                  Get Embed Code
                </span>
              </div>
            </Link>
            <Link href="/dashboard/personas" className="group">
              <div className="h-auto rounded-md border bg-card px-3 py-4 shadow-xs transition-all hover:border-primary/30 hover:bg-primary/10 flex flex-col items-center justify-center gap-2 min-h-[100px]">
                <UserPlus className="size-5 transition-colors group-hover:text-primary sm:size-6" />
                <span className="text-center text-xs font-medium sm:text-sm">
                  Create Persona
                </span>
              </div>
            </Link>
            <Link href={`/${user.username}`} target="_blank" className="group">
              <div className="h-auto rounded-md border bg-card px-3 py-4 shadow-xs transition-all hover:border-primary/30 hover:bg-primary/10 flex flex-col items-center justify-center gap-2 min-h-[100px]">
                <ExternalLink className="size-5 transition-colors group-hover:text-primary sm:size-6" />
                <span className="text-center text-xs font-medium sm:text-sm">
                  View Public Page
                </span>
              </div>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Personas Overview */}
      <div id="personas-section" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Your Personas</h2>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/dashboard/personas">Manage Personas →</Link>
          </Button>
        </div>
        {personas.length === 0 ? (
          <Card>
            <CardContent className="py-12">
              <div className="text-center space-y-3">
                <UserPlus className="size-12 mx-auto text-muted-foreground" />
                <div>
                  <h3 className="font-semibold mb-1">No personas yet</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Create personas to focus on different aspects of your
                    expertise
                  </p>
                  <Button asChild>
                    <Link href="/dashboard/personas">Create First Persona</Link>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {personas.map((persona) => {
              return (
                <Link
                  key={persona.id}
                  href={`/${user.username}/${persona.persona_name}`}
                  target="_blank"
                  className="block"
                >
                  <Card className="h-full cursor-pointer transition-all hover:border-primary/30 hover:shadow-md">
                    <CardContent className="py-3">
                      <div className="flex items-start gap-3">
                        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary">
                          <UserPlus className="size-5 text-foreground" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <h3 className="truncate font-semibold">
                            {persona.name}
                          </h3>
                          <p className="truncate text-xs text-muted-foreground">
                            /{user.username}/{persona.persona_name}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Stats Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Knowledge Library Stats */}
        <Card id="knowledge-stats-card">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Database className="size-5" />
                Knowledge Library
              </span>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/dashboard/knowledge">View All →</Link>
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Overall Stats */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Total Sources</p>
                <p className="text-2xl font-bold">{totalJobs}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Connected</p>
                <p className="text-2xl font-bold text-green-600">
                  {connectedSources.size}
                </p>
              </div>
            </div>

            {/* Status Breakdown */}
            <div className="space-y-2">
              <p className="text-sm font-medium">Status Breakdown</p>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-green-600" />
                    Completed
                  </span>
                  <span className="font-semibold">{completedJobs}</span>
                </div>
                {processingJobs > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <Clock className="size-4 text-blue-600" />
                      Processing
                    </span>
                    <span className="font-semibold">{processingJobs}</span>
                  </div>
                )}
                {failedJobs > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <XCircle className="size-4 text-red-600" />
                      Failed
                    </span>
                    <span className="font-semibold">{failedJobs}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Connected Sources */}
            {connectedSources.size > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Connected Sources</p>
                <div className="flex flex-wrap gap-2">
                  {Array.from(connectedSources).map((source) => {
                    const Icon =
                      sourceIcons[source as keyof typeof sourceIcons] ||
                      Database;
                    return (
                      <Badge key={source} variant="secondary" className="gap-1">
                        <Icon className="size-3" />
                        {source.charAt(0).toUpperCase() + source.slice(1)}
                      </Badge>
                    );
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Conversations Stats */}
        <Card id="conversations-stats-card">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <MessageSquare className="size-5" />
                Conversations
              </span>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/dashboard/conversations">View All →</Link>
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">
                Total Conversations
              </p>
              <p className="text-3xl font-bold">{totalConversations}</p>
            </div>

            {totalConversations === 0 ? (
              <div className="rounded-lg border border-dashed p-6 text-center">
                <MessageSquare className="mx-auto size-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  No conversations yet
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Share your profile link to start receiving conversations
                </p>
              </div>
            ) : (
              <>
                {/* Conversation Type Breakdown */}
                <div className="space-y-2">
                  <p className="text-sm font-medium">Conversation Types</p>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <MessageSquare className="size-4 text-blue-600" />
                        Text Chat
                      </span>
                      <span className="font-semibold">{textConversations}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <Mic className="size-4 text-ai-brown 600" />
                        Voice Chat
                      </span>
                      <span className="font-semibold">
                        {voiceConversations}
                      </span>
                    </div>
                  </div>
                </div>

                <Button asChild className="w-full">
                  <Link href="/dashboard/conversations">
                    View All Conversations →
                  </Link>
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
