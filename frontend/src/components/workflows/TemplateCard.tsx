"use client";

import { useState } from "react";
import type { WorkflowTemplate } from "@/lib/queries/workflows";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Lock, Sparkles } from "lucide-react";
import {
  getTierDisplayName,
  getTierBadgeClass,
  hasTemplateAccess,
} from "@/lib/utils/tierMapping";
import Image from "next/image";
import { UpgradeCTA } from "@/components/tier/UpgradeCTA";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface TemplateCardProps {
  template: WorkflowTemplate;
  userTierId: number | undefined | null;
  onEnable: (template: WorkflowTemplate) => void;
}

/**
 * Card displaying a workflow template with details and enable option
 */
export function TemplateCard({
  template,
  userTierId,
  onEnable,
}: TemplateCardProps) {
  const [showUpgradeDialog, setShowUpgradeDialog] = useState(false);
  const hasAccess = hasTemplateAccess(
    userTierId,
    template.minimum_plan_tier_id,
  );

  const handleEnableClick = () => {
    if (!hasAccess) {
      setShowUpgradeDialog(true);
      return;
    }
    onEnable(template);
  };

  // Infer question count from workflow_config if possible
  const questionCount = (() => {
    const config = template.workflow_config;
    if ("steps" in config && Array.isArray(config.steps)) {
      return config.steps.length;
    }
    if ("required_fields" in config || "optional_fields" in config) {
      const required = Array.isArray(config.required_fields)
        ? config.required_fields.length
        : 0;
      const optional = Array.isArray(config.optional_fields)
        ? config.optional_fields.length
        : 0;
      return required + optional;
    }
    return 0;
  })();

  return (
    <>
      <div
        className={`group relative flex flex-col rounded-lg border bg-card overflow-hidden transition-all hover:shadow-md ${
          !hasAccess ? "opacity-75" : ""
        }`}
      >
        {/* Preview Image */}
        {template.preview_image_url ? (
          <div className="relative h-40 w-full bg-gradient-to-br from-yellow-light to-peach-light overflow-hidden">
            <Image
              src={template.preview_image_url}
              alt={template.template_name}
              fill
              className="object-cover"
            />
          </div>
        ) : (
          <div className="h-40 w-full bg-gradient-to-br from-yellow-light to-peach-light flex items-center justify-center">
            <Sparkles className="size-12 text-yellow-bright opacity-50" />
          </div>
        )}

        {/* Lock Overlay for restricted templates */}
        {!hasAccess && (
          <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px] flex items-center justify-center z-10">
            <div className="flex items-center gap-2 bg-white px-4 py-2 rounded-full shadow-lg">
              <Lock className="size-4 text-gray-700" />
              <span className="text-sm font-medium text-gray-900">
                {getTierDisplayName(template.minimum_plan_tier_id)} Required
              </span>
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex flex-1 flex-col p-4 space-y-3">
          {/* Header */}
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold text-lg line-clamp-1">
              {template.template_name}
            </h3>
            <Badge
              variant="outline"
              className={`shrink-0 ${getTierBadgeClass(template.minimum_plan_tier_id)}`}
            >
              {getTierDisplayName(template.minimum_plan_tier_id)}
            </Badge>
          </div>

          {/* Description */}
          {template.description && (
            <p className="text-sm text-muted-foreground line-clamp-2 flex-1">
              {template.description}
            </p>
          )}

          {/* Metadata */}
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {questionCount > 0 && (
              <span className="flex items-center gap-1">
                <span className="font-medium text-foreground">
                  {questionCount}
                </span>{" "}
                {questionCount === 1 ? "question" : "questions"}
              </span>
            )}
            <span className="capitalize">{template.workflow_type}</span>
            {template.usage_count !== undefined && template.usage_count > 0 && (
              <span>
                <span className="font-medium text-foreground">
                  {template.usage_count}
                </span>{" "}
                uses
              </span>
            )}
          </div>

          {/* Tags */}
          {template.tags && template.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {template.tags.slice(0, 3).map((tag) => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
            </div>
          )}

          {/* Action Button */}
          <Button
            onClick={handleEnableClick}
            className="w-full"
            variant={hasAccess ? "default" : "outline"}
          >
            {hasAccess ? "Use Template" : "Upgrade to Use"}
          </Button>
        </div>
      </div>

      {/* Upgrade Dialog */}
      <Dialog open={showUpgradeDialog} onOpenChange={setShowUpgradeDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Upgrade Required</DialogTitle>
          </DialogHeader>
          <UpgradeCTA
            title={`${getTierDisplayName(template.minimum_plan_tier_id)} Plan Required`}
            description={`This template requires a ${getTierDisplayName(template.minimum_plan_tier_id)} plan or higher. Upgrade to unlock this and other premium templates.`}
            features={[
              "Access to premium workflow templates",
              "Advanced workflow types",
              "Higher usage limits",
              "Priority support",
            ]}
            showContactOption={
              template.minimum_plan_tier_id === 3 /* TIER_ENTERPRISE */
            }
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
