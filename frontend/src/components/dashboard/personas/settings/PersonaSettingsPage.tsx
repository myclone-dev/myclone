"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { usePersonaById } from "@/lib/queries/persona";
import { useUserSubscription } from "@/lib/queries/tier";
import { isPaidTier } from "@/lib/constants/tiers";
import { useUIStore } from "@/store/ui.store";
import { SettingsHeader } from "./SettingsHeader";
import { SettingsSidebar } from "./SettingsSidebar";
import { settingsSections } from "./sections";
import { BasicInfoSection } from "./sections/BasicInfoSection";
import { AvatarSection } from "./sections/AvatarSection";
import { PromptSection } from "./sections/PromptSection";
import { VoiceSection } from "./sections/VoiceSection";
import { LanguageSection } from "./sections/LanguageSection";
import { EmailSection } from "./sections/EmailSection";
import { CalendarSection } from "./sections/CalendarSection";
import { SessionSection } from "./sections/SessionSection";
import { MonetizationSection } from "./sections/MonetizationSection";
import { KnowledgeSourcesSection } from "./sections/KnowledgeSourcesSection";
import { AccessControlSection } from "./sections/AccessControlSection";
import { ProUpgradeOverlay } from "./components/ProUpgradeOverlay";
import { Skeleton } from "@/components/ui/skeleton";
import {
  SettingsSaveProvider,
  useSettingsSave,
} from "./contexts/SettingsSaveContext";
import { NavigationGuard } from "./components/NavigationGuard";
import type { Persona } from "../PersonaSettingsDialog/types";

interface PersonaSettingsPageProps {
  personaId: string;
}

export function PersonaSettingsPage({ personaId }: PersonaSettingsPageProps) {
  // Fetch persona data by ID
  const { data: persona, isLoading: personaLoading } =
    usePersonaById(personaId);

  const { data: subscription } = useUserSubscription();

  // Loading state
  if (personaLoading || !persona) {
    return <LoadingSkeleton />;
  }

  // Convert PersonaDetails to Persona type for backward compatibility
  const personaForSettings: Persona = {
    ...persona,
    role: persona.role || "",
  } as Persona;

  return (
    <SettingsSaveProvider>
      <PersonaSettingsContent
        personaId={personaId}
        persona={personaForSettings}
        tierId={subscription?.tier_id}
      />
    </SettingsSaveProvider>
  );
}

interface PersonaSettingsContentProps {
  personaId: string;
  persona: Persona;
  tierId?: number;
}

function PersonaSettingsContent({
  personaId,
  persona,
  tierId,
}: PersonaSettingsContentProps) {
  const router = useRouter();
  const [activeSection, setActiveSection] = useState("basic-info");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [showNavigationGuard, setShowNavigationGuard] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<
    (() => void) | null
  >(null);

  const { hasUnsavedChanges, isSaving, handleSave, handleDiscard } =
    useSettingsSave();

  const setSidebarCollapsed = useUIStore((state) => state.setSidebarCollapsed);

  // Close main navigation when persona settings opens
  useEffect(() => {
    setSidebarCollapsed(true);
  }, [setSidebarCollapsed]);

  const visibleSections = settingsSections;

  // Get active section details
  const activeSectionData = visibleSections.find((s) => s.id === activeSection);

  // Handle back button click
  const handleBackClick = () => {
    if (hasUnsavedChanges) {
      setPendingNavigation(() => () => router.push("/dashboard/personas"));
      setShowNavigationGuard(true);
    } else {
      router.push("/dashboard/personas");
    }
  };

  // Handle section change
  const handleSectionChange = (sectionId: string) => {
    if (hasUnsavedChanges) {
      setPendingNavigation(() => () => setActiveSection(sectionId));
      setShowNavigationGuard(true);
    } else {
      setActiveSection(sectionId);
    }
  };

  // Handle save from navigation guard
  const handleGuardSave = async () => {
    await handleSave();
    setShowNavigationGuard(false);
    if (pendingNavigation) {
      pendingNavigation();
      setPendingNavigation(null);
    }
  };

  // Handle discard from navigation guard
  const handleGuardDiscard = () => {
    handleDiscard();
    setShowNavigationGuard(false);
    if (pendingNavigation) {
      pendingNavigation();
      setPendingNavigation(null);
    }
  };

  // Check if user has access to monetization (Pro tier and above)
  const canAccessMonetization = isPaidTier(tierId);

  // Render active section component
  const renderActiveSection = () => {
    const props = { personaId, persona };

    switch (activeSection) {
      case "basic-info":
        return <BasicInfoSection {...props} />;
      case "avatar":
        return <AvatarSection {...props} />;
      case "prompt":
        return <PromptSection {...props} />;
      case "voice":
        return <VoiceSection {...props} />;
      case "language":
        return <LanguageSection {...props} />;
      case "email":
        return <EmailSection {...props} />;
      case "calendar":
        return <CalendarSection {...props} />;
      case "session":
        return <SessionSection {...props} />;
      case "monetization":
        // Show upgrade overlay for free tier users
        if (!canAccessMonetization) {
          return <ProUpgradeOverlay />;
        }
        return <MonetizationSection {...props} />;
      case "knowledge":
        return <KnowledgeSourcesSection personaId={personaId} />;
      case "access":
        return <AccessControlSection {...props} />;
      default:
        return null;
    }
  };

  return (
    <>
      <div className="h-screen flex flex-col bg-background -m-4 sm:-m-6 lg:-m-8">
        {/* Header */}
        <SettingsHeader
          personaName={persona.name}
          onMenuClick={() => setMobileNavOpen(true)}
          activeSection={activeSectionData?.title}
          hasUnsavedChanges={hasUnsavedChanges}
          isSaving={isSaving}
          onSave={handleSave}
          onDiscard={handleDiscard}
          onBackClick={handleBackClick}
        />

        <div className="flex flex-1 overflow-hidden">
          {/* Desktop Sidebar */}
          <SettingsSidebar
            sections={visibleSections}
            activeSection={activeSection}
            onSectionChange={handleSectionChange}
            className="hidden md:block overflow-y-auto"
            userTierId={tierId}
          />

          {/* Mobile Sheet */}
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetContent side="left" className="w-72 p-0">
              <SettingsSidebar
                sections={visibleSections}
                activeSection={activeSection}
                onSectionChange={(id) => {
                  handleSectionChange(id);
                  setMobileNavOpen(false);
                }}
                userTierId={tierId}
              />
            </SheetContent>
          </Sheet>

          {/* Main Content */}
          <main className="flex-1 overflow-y-auto p-6 md:p-8">
            <div className="max-w-4xl mx-auto">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeSection}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  transition={{ duration: 0.2 }}
                >
                  {renderActiveSection()}
                </motion.div>
              </AnimatePresence>
            </div>
          </main>
        </div>
      </div>

      {/* Navigation Guard Dialog */}
      <NavigationGuard
        open={showNavigationGuard}
        onOpenChange={setShowNavigationGuard}
        onSave={handleGuardSave}
        onDiscard={handleGuardDiscard}
        isSaving={isSaving}
      />
    </>
  );
}

function LoadingSkeleton() {
  return (
    <div className="h-screen flex flex-col bg-background -m-4 sm:-m-6 lg:-m-8">
      <div className="border-b bg-background/95 sticky top-0 z-40">
        <div className="container flex h-14 items-center gap-4 px-4">
          <Skeleton className="h-6 w-64" />
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <aside className="hidden md:block w-64 border-r bg-muted/10 overflow-y-auto">
          <div className="py-6 px-4 space-y-2">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-4xl mx-auto space-y-6">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-96" />
            <Skeleton className="h-96 w-full" />
          </div>
        </main>
      </div>
    </div>
  );
}
