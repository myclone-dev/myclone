"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Copy, Check, MessageCircle, PanelTop, Maximize } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Framework, WidgetMode } from "../types";

interface CodePanelProps {
  copied: boolean;
  selectedFramework: Framework;
  setSelectedFramework: (framework: Framework) => void;
  widgetMode: WidgetMode;
  setWidgetMode: (mode: WidgetMode) => void;
  generatedCode: string;
  handleCopy: () => void;
}

const WIDGET_MODES = [
  { value: "bubble" as const, label: "Bubble", icon: MessageCircle },
  { value: "inline" as const, label: "Inline", icon: PanelTop },
  { value: "fullpage" as const, label: "Fullpage", icon: Maximize },
] as const;

const MODE_DESCRIPTIONS: Record<WidgetMode, string> = {
  bubble:
    "Floating chat button in the corner that opens a modal. Perfect for most websites.",
  inline:
    "Embed chat directly into your page content. Ideal for contact pages.",
  fullpage: "Full-screen chat experience. Perfect for dedicated chat pages.",
};

const FRAMEWORKS = [
  { value: "html" as const, label: "HTML" },
  { value: "nextjs" as const, label: "Next.js" },
  { value: "react" as const, label: "React (TS)" },
  { value: "react-js" as const, label: "React (JS)" },
  { value: "vue" as const, label: "Vue" },
  { value: "astro" as const, label: "Astro" },
  { value: "wordpress" as const, label: "WordPress" },
  { value: "wix" as const, label: "Wix" },
  { value: "hostinger" as const, label: "Hostinger" },
];

const FRAMEWORK_INSTRUCTIONS: Record<Framework, string[]> = {
  html: [
    "1. Open your HTML file",
    "2. Find the closing </body> tag",
    "3. Paste the code right before </body>",
    "4. Save and refresh your page",
  ],
  nextjs: [
    "1. Create src/components/ConvoxAIWidget.tsx with the component code",
    "2. Import the component in your app/layout.tsx",
    "3. Add <ConvoxAIWidget /> inside the <body> tag",
    "4. Set NEXT_PUBLIC_CONVOXAI_TOKEN in .env.local",
  ],
  react: [
    "1. Create src/components/ConvoxAIWidget.tsx with the component code",
    "2. Import the component in your App.tsx",
    "3. Add <ConvoxAIWidget /> to your app",
    "4. Set VITE_CONVOXAI_TOKEN in .env file",
  ],
  "react-js": [
    "1. Create src/components/ConvoxAIWidget.jsx with the component code",
    "2. Import the component in your App.jsx",
    "3. Add <ConvoxAIWidget /> to your app",
    "4. Set VITE_CONVOXAI_TOKEN in .env file",
  ],
  vue: [
    "1. Create the ConvoxAIWidget.vue component or add to App.vue",
    "2. Import and register the component",
    "3. Add the component to your template",
    "4. Save and reload your app",
  ],
  astro: [
    "1. Create src/components/ConvoxAIWidget.astro with the code",
    "2. Import in your Layout.astro file",
    "3. Add <ConvoxAIWidget /> to your layout",
    "4. Build and deploy your site",
  ],
  wordpress: [
    "1. Copy the widget code above",
    "2. Go to WordPress admin → Tools → Theme File Editor",
    "3. Open footer.php and paste code before closing </div> tag",
    "4. Save changes and refresh your site",
  ],
  wix: [
    "1. Go to Settings (gear icon) → Custom Code → + Add Custom Code",
    "2. Paste code and set load location to 'Body - end'",
    "3. Apply to 'All pages' (or specific pages) and Save",
    "4. Or add HTML element and paste code directly",
    "5. Guide: https://support.wix.com/en/article/wix-editor-embedding-custom-code-on-your-site",
  ],
  hostinger: [
    "1. Log into your Hostinger account",
    "2. Open Horizon website builder",
    "3. Open your index.html file in the editor",
    "4. Find the closing </body> tag",
    "5. Paste the code right before </body>",
    "6. Save and publish your changes",
  ],
};

export function CodePanel({
  copied,
  selectedFramework,
  setSelectedFramework,
  widgetMode,
  setWidgetMode,
  generatedCode,
  handleCopy,
}: CodePanelProps) {
  return (
    <Card className="p-4 md:p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-900">
          Generated Code
        </h3>
        <Button
          variant="outline"
          size="sm"
          onClick={handleCopy}
          className="gap-2"
        >
          {copied ? (
            <>
              <Check className="size-4 text-green-600" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="size-4" />
              Copy
            </>
          )}
        </Button>
      </div>

      {/* Mode Selector - Segmented Control */}
      <div className="mb-4">
        <div
          role="tablist"
          aria-label="Widget embed mode"
          className="flex w-full rounded-full bg-slate-100 p-1"
        >
          {WIDGET_MODES.map(({ value, label, icon: Icon }) => (
            <Tooltip key={value} delayDuration={0}>
              <TooltipTrigger asChild>
                <button
                  role="tab"
                  aria-selected={widgetMode === value}
                  aria-controls="code-output"
                  aria-label={label}
                  onClick={() => setWidgetMode(value)}
                  className={`flex flex-1 min-w-0 items-center justify-center gap-1 rounded-full px-1.5 py-1.5 text-xs font-medium transition-all sm:gap-2 sm:px-4 sm:py-2 sm:text-sm ${
                    widgetMode === value
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  <Icon
                    className="size-3.5 shrink-0 sm:size-4"
                    aria-hidden="true"
                  />
                  <span className="truncate text-[10px] sm:text-xs">
                    {label}
                  </span>
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-sm:hidden">
                <p>{label}</p>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      </div>

      {/* Mode Description */}
      <p className="mb-4 text-xs text-slate-500">
        {MODE_DESCRIPTIONS[widgetMode]}
      </p>

      {/* Framework Tabs */}
      <div
        role="tablist"
        aria-label="Framework selection"
        className="mb-3 flex flex-wrap gap-1.5 sm:gap-2"
      >
        {FRAMEWORKS.map((fw) => (
          <button
            key={fw.value}
            role="tab"
            aria-selected={selectedFramework === fw.value}
            aria-controls="code-output"
            onClick={() => setSelectedFramework(fw.value)}
            className={`rounded-md px-2 py-1 text-xs font-medium transition-all sm:px-3 sm:py-1.5 sm:text-sm ${
              selectedFramework === fw.value
                ? "bg-ai-gold text-gray-900"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900"
            }`}
          >
            {fw.label}
          </button>
        ))}
      </div>

      <pre
        id="code-output"
        role="tabpanel"
        aria-label={`${selectedFramework} embed code for ${widgetMode} mode`}
        className="max-h-64 overflow-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100"
      >
        <code>{generatedCode}</code>
      </pre>

      {/* Framework Instructions */}
      <div className="mt-4 space-y-1.5">
        {FRAMEWORK_INSTRUCTIONS[selectedFramework].map((instruction, idx) => (
          <p key={idx} className="text-xs text-slate-600">
            {instruction}
          </p>
        ))}
      </div>
    </Card>
  );
}
