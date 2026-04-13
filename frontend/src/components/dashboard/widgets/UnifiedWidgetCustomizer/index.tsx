"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { RotateCcw } from "lucide-react";

import { CustomizeTab } from "./types";
import { useWidgetConfig, useCodeGenerator } from "./hooks";
import {
  EssentialsTab,
  ThemeTab,
  SizeTab,
  LayoutTab,
  BrandTab,
  PreviewPanel,
  CodePanel,
  CustomizeTabSelector,
} from "./components";

interface UnifiedWidgetCustomizerProps {
  username: string;
  widgetToken?: string;
}

export function UnifiedWidgetCustomizer({
  username,
  widgetToken,
}: UnifiedWidgetCustomizerProps) {
  const [activeCustomizeTab, setActiveCustomizeTab] =
    useState<CustomizeTab>("essentials");

  const { config, setConfig, resetToDefaults, effectiveColors } =
    useWidgetConfig({ username, widgetToken });

  const {
    widgetMode,
    setWidgetMode,
    selectedFramework,
    setSelectedFramework,
    copied,
    handleCopy,
    getCode,
  } = useCodeGenerator({ username, config });

  return (
    <div className="grid w-full gap-4 md:gap-6 lg:grid-cols-2">
      {/* Left Panel - Customization Form */}
      <div className="min-w-0 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">
            Customize Widget
          </h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetToDefaults}
            className="gap-2 text-slate-600"
          >
            <RotateCcw className="size-4" />
            Reset
          </Button>
        </div>

        <Tabs
          defaultValue="essentials"
          className="w-full"
          value={activeCustomizeTab}
          onValueChange={(value) =>
            setActiveCustomizeTab(value as CustomizeTab)
          }
        >
          <CustomizeTabSelector
            activeTab={activeCustomizeTab}
            setActiveTab={setActiveCustomizeTab}
          />

          <TabsList className="hidden">
            <TabsTrigger value="essentials" />
            <TabsTrigger value="theme" />
            <TabsTrigger value="size" />
            <TabsTrigger value="layout" />
            <TabsTrigger value="branding" />
          </TabsList>

          <TabsContent value="essentials" className="mt-4 space-y-4">
            <EssentialsTab config={config} setConfig={setConfig} />
          </TabsContent>

          <TabsContent value="theme" className="mt-4 space-y-4">
            <ThemeTab config={config} setConfig={setConfig} />
          </TabsContent>

          <TabsContent value="size" className="mt-4 space-y-4">
            <SizeTab config={config} setConfig={setConfig} />
          </TabsContent>

          <TabsContent value="layout" className="mt-4 space-y-4">
            <LayoutTab
              config={config}
              setConfig={setConfig}
              colors={effectiveColors}
            />
          </TabsContent>

          <TabsContent value="branding" className="mt-4 space-y-4">
            <BrandTab config={config} setConfig={setConfig} />
          </TabsContent>
        </Tabs>
      </div>

      {/* Right Panel - Preview & Code */}
      <div className="min-w-0 space-y-4">
        <PreviewPanel
          config={config}
          colors={effectiveColors}
          username={username}
        />

        <CodePanel
          widgetMode={widgetMode}
          setWidgetMode={setWidgetMode}
          selectedFramework={selectedFramework}
          setSelectedFramework={setSelectedFramework}
          copied={copied}
          handleCopy={handleCopy}
          generatedCode={getCode()}
        />
      </div>
    </div>
  );
}
