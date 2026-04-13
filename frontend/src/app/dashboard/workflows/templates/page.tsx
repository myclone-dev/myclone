"use client";

import { useState } from "react";
import Link from "next/link";
import { useUserMe } from "@/lib/queries/users";
import { useUserPersonas } from "@/lib/queries/persona";
import { useUserSubscription } from "@/lib/queries/tier";
import {
  useWorkflowTemplates,
  type TemplateCategory,
  type WorkflowTemplate,
} from "@/lib/queries/workflows";
import { TemplateCard } from "@/components/workflows/TemplateCard";
import { EnableTemplateDialog } from "@/components/workflows/EnableTemplateDialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ArrowLeft, Sparkles } from "lucide-react";

/**
 * Workflow Templates Gallery Page
 * Browse and enable workflow templates
 */
export default function WorkflowTemplatesPage() {
  const { data: user, isLoading: userLoading } = useUserMe();
  const { data: personasData } = useUserPersonas(user?.id || "");
  const { data: subscription } = useUserSubscription();
  const personas = personasData?.personas || [];

  const [selectedCategory, setSelectedCategory] = useState<
    TemplateCategory | "all"
  >("all");
  const [selectedTemplate, setSelectedTemplate] =
    useState<WorkflowTemplate | null>(null);
  const [enableDialogOpen, setEnableDialogOpen] = useState(false);

  // Fetch templates with optional category filter
  const { data: templatesData, isLoading: templatesLoading } =
    useWorkflowTemplates({
      category: selectedCategory === "all" ? undefined : selectedCategory,
      include_stats: true,
    });

  const handleEnableTemplate = (template: WorkflowTemplate) => {
    setSelectedTemplate(template);
    setEnableDialogOpen(true);
  };

  if (userLoading) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="space-y-6 animate-pulse">
          <div className="h-8 w-64 bg-muted rounded" />
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-80 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const templates = templatesData?.templates || [];

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-4">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/dashboard/workflows">
              <ArrowLeft className="size-4 mr-2" />
              Back to Workflows
            </Link>
          </Button>
          <div className="space-y-2">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2 sm:gap-3">
              <Sparkles className="size-6 sm:size-8 text-yellow-bright shrink-0" />
              <span>Workflow Templates</span>
            </h1>
            <p className="text-sm sm:text-base text-muted-foreground">
              Choose from pre-built templates designed for common use cases
            </p>
          </div>
        </div>
      </div>

      {/* Category Filter */}
      <Tabs
        value={selectedCategory}
        onValueChange={(value) =>
          setSelectedCategory(value as TemplateCategory | "all")
        }
        className="w-full"
      >
        <TabsList className="grid w-full sm:w-auto sm:inline-grid grid-cols-4 gap-1">
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="cpa">CPA</TabsTrigger>
          <TabsTrigger value="tax">Tax</TabsTrigger>
          <TabsTrigger value="insurance">Insurance</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Templates Grid */}
      {templatesLoading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-80 bg-muted rounded-lg animate-pulse" />
          ))}
        </div>
      ) : templates.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <div className="mb-4 flex size-20 items-center justify-center rounded-full bg-yellow-light">
            <Sparkles className="size-10 text-yellow-bright" />
          </div>
          <h3 className="mb-2 text-lg font-semibold">No templates found</h3>
          <p className="mb-6 text-sm text-muted-foreground max-w-md">
            {selectedCategory === "all"
              ? "There are no templates available at the moment. Check back later!"
              : `No templates found for the ${selectedCategory} category. Try browsing all templates.`}
          </p>
          {selectedCategory !== "all" && (
            <Button onClick={() => setSelectedCategory("all")}>
              View All Templates
            </Button>
          )}
        </div>
      ) : (
        <>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {templates.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                userTierId={subscription?.tier_id}
                onEnable={handleEnableTemplate}
              />
            ))}
          </div>

          {/* Template count */}
          <div className="text-center text-sm text-muted-foreground">
            Showing {templates.length} template
            {templates.length !== 1 ? "s" : ""}
            {selectedCategory !== "all" && ` in ${selectedCategory} category`}
          </div>
        </>
      )}

      {/* Enable Template Dialog */}
      <EnableTemplateDialog
        template={selectedTemplate}
        personas={personas}
        open={enableDialogOpen}
        onOpenChange={setEnableDialogOpen}
      />
    </div>
  );
}
