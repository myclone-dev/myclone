"use client";

import { useState } from "react";
import { Crown, Check, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ContactModal } from "./ContactModal";

export function UpgradePrompt() {
  const [isContactModalOpen, setIsContactModalOpen] = useState(false);

  return (
    <Card className="border-yellow-bright/50 bg-yellow-light/30">
      <CardHeader>
        <div className="flex items-start gap-4">
          <div className="rounded-full bg-yellow-bright p-3">
            <Crown className="size-6 text-gray-900" />
          </div>
          <div className="flex-1">
            <CardTitle>Unlock Integrations</CardTitle>
            <CardDescription className="mt-2">
              Connect your clone with Stripe, Zapier, and GoHighLevel. Automate
              workflows, sync data, and scale your business. Available on
              Business and Enterprise plans.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex-1">
            <div className="grid gap-2 text-sm sm:grid-cols-2">
              <div className="flex items-center gap-2">
                <Check className="size-4 text-green-600" />
                <span>Unlimited integrations</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="size-4 text-green-600" />
                <span>Real-time data sync</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="size-4 text-green-600" />
                <span>Custom API access</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="size-4 text-green-600" />
                <span>Priority support</span>
              </div>
            </div>
          </div>
          <ContactModal
            isOpen={isContactModalOpen}
            onOpenChange={setIsContactModalOpen}
            trigger={
              <Button size="lg" className="gap-2">
                <Sparkles className="size-4" />
                Unlock Integrations
              </Button>
            }
          />
        </div>
      </CardContent>
    </Card>
  );
}
