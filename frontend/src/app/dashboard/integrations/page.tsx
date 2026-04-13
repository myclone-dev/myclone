"use client";

import { useState } from "react";
import { SiStripe, SiZapier, SiTwilio } from "react-icons/si";
import {
  GoHighLevelIcon,
  TaxDomeIcon,
  CanopyIcon,
  KarbonIcon,
} from "@/components/icons";
import {
  useUserSubscription,
  hasIntegrationsAccess,
  isEnterpriseTier,
} from "@/lib/queries/tier";
import { PageLoader } from "@/components/ui/page-loader";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { IntegrationConfig } from "@/lib/queries/integrations";
import {
  IntegrationCard,
  UpgradePrompt,
  ZapierWebhookDialog,
} from "@/components/dashboard/integrations";

// Mock integrations config - frontend only
const INTEGRATIONS: IntegrationConfig[] = [
  {
    type: "zapier",
    name: "Zapier",
    description:
      "Automate workflows by connecting your clone with 5,000+ apps. Create custom automation workflows without coding.",
    icon: "zapier",
    features: [
      "5,000+ app integrations",
      "Multi-step workflows",
      "Conditional logic",
      "Scheduled automations",
      "Real-time triggers",
    ],
    requiresBusinessPlan: true,
    color: "#FF4A00",
  },
  {
    type: "stripe",
    name: "Stripe Payments",
    description:
      "Process payments and subscriptions directly through your clone. Accept credit cards, handle refunds, and track revenue. Enable monetization in your persona settings to start collecting payments.",
    icon: "stripe",
    features: [
      "Enable monetization in Persona Settings first",
      "Payment processing",
      "Subscription management",
      "Refund handling",
      "Revenue analytics",
      "Webhook notifications",
    ],
    requiresBusinessPlan: true,
    color: "#635BFF",
  },
  {
    type: "gohighlevel",
    name: "GoHighLevel",
    description:
      "Sync conversations and contacts to GoHighLevel. Automate follow-ups, manage pipelines, and track customer journeys.",
    icon: "gohighlevel",
    features: [
      "Contact sync",
      "Pipeline management",
      "Automated workflows",
      "SMS & email campaigns",
      "Lead tracking",
    ],
    requiresBusinessPlan: true,
    comingSoon: true,
    color: "#00D09C",
  },
  {
    type: "canopy",
    name: "Canopy",
    description:
      "Integrate with Canopy tax practice management. Sync client data, automate communications, and streamline tax workflows.",
    icon: "canopy",
    features: [
      "Client data sync",
      "Document management",
      "Task automation",
      "Workflow integration",
      "Tax season support",
    ],
    requiresEnterprisePlan: true,
    comingSoon: true,
    color: "#4B9FD5",
  },
  {
    type: "taxdome",
    name: "TaxDome",
    description:
      "Connect with TaxDome practice management platform. Automate client onboarding, task management, and communication workflows.",
    icon: "taxdome",
    features: [
      "Client portal integration",
      "Automated workflows",
      "Document requests",
      "Task management",
      "Team collaboration",
    ],
    requiresEnterprisePlan: true,
    comingSoon: true,
    color: "#00A3E0",
  },
  {
    type: "karbon",
    name: "Karbon",
    description:
      "Sync with Karbon practice management. Streamline client work, automate communication, and manage accounting firm workflows.",
    icon: "karbon",
    features: [
      "Client work management",
      "Email integration",
      "Workflow automation",
      "Team collaboration",
      "Status tracking",
    ],
    requiresEnterprisePlan: true,
    comingSoon: true,
    color: "#6B4FBB",
  },
  {
    type: "twilio",
    name: "Twilio",
    description:
      "Integrate Twilio communications platform. Enable SMS notifications, voice calls, and multi-channel messaging for your clones.",
    icon: "twilio",
    features: [
      "SMS messaging",
      "Voice calls",
      "WhatsApp integration",
      "Programmable notifications",
      "Multi-channel support",
    ],
    requiresEnterprisePlan: true,
    comingSoon: true,
    color: "#F22F46",
  },
];

const iconMap = {
  stripe: SiStripe,
  zapier: SiZapier,
  gohighlevel: GoHighLevelIcon,
  canopy: CanopyIcon,
  taxdome: TaxDomeIcon,
  karbon: KarbonIcon,
  twilio: SiTwilio,
};

export default function IntegrationsPage() {
  const { data: subscription, isLoading } = useUserSubscription();
  const [isZapierDialogOpen, setIsZapierDialogOpen] = useState(false);

  const getIcon = (iconName: string) => {
    return iconMap[iconName as keyof typeof iconMap];
  };

  // Show loading state
  if (isLoading) {
    return <PageLoader text="Loading integrations..." />;
  }

  // Check if user has access to integrations (Business, Enterprise)
  const hasAccess = hasIntegrationsAccess(subscription?.tier_id);
  const isEnterprise = isEnterpriseTier(subscription?.tier_id);

  // Filter integrations based on tier
  const visibleIntegrations = INTEGRATIONS.filter((integration) => {
    // Show all non-enterprise integrations to everyone
    if (!integration.requiresEnterprisePlan) {
      return true;
    }
    // Only show enterprise integrations to enterprise users
    return isEnterprise;
  });

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Integrations</h1>
        <p className="mt-2 text-muted-foreground">
          Connect your clone with your favorite tools and platforms
        </p>
      </div>

      {/* Upgrade Prompt for non-qualified tiers */}
      {!hasAccess && <UpgradePrompt />}

      {/* Integrations Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {visibleIntegrations.map((integration) => {
          const isLocked =
            !hasAccess && (integration.requiresBusinessPlan ?? false);
          const Icon = getIcon(integration.icon);

          return (
            <IntegrationCard
              key={integration.type}
              integration={integration}
              isLocked={isLocked}
              Icon={Icon}
              onClick={
                integration.type === "zapier"
                  ? () => setIsZapierDialogOpen(true)
                  : undefined
              }
            />
          );
        })}
      </div>

      {/* Help Section */}
      <Card>
        <CardHeader>
          <CardTitle>Need a Custom Integration?</CardTitle>
          <CardDescription>
            Contact our team to discuss custom integrations for your enterprise
            CRM, payment processor, or other business tools.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline">Contact Sales</Button>
        </CardContent>
      </Card>

      {/* Zapier Webhook Dialog */}
      <ZapierWebhookDialog
        open={isZapierDialogOpen}
        onOpenChange={setIsZapierDialogOpen}
      />
    </div>
  );
}
