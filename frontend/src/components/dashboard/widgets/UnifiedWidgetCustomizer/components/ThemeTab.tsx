"use client";

import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { WidgetConfig } from "../types";

interface ThemeTabProps {
  config: WidgetConfig;
  setConfig: (config: WidgetConfig) => void;
}

export function ThemeTab({ config, setConfig }: ThemeTabProps) {
  return (
    <div className="mt-4 space-y-4">
      {/* Main Colors */}
      <Card className="p-4">
        <h4 className="mb-4 text-sm font-semibold text-slate-700">
          Main Colors
        </h4>
        <div className="space-y-4">
          {/* Primary Color */}
          <div className="space-y-2">
            <Label htmlFor="primaryColor" className="text-xs font-medium">
              Primary Color
            </Label>
            <p className="text-xs text-slate-500">Main accent color</p>
            <div className="flex gap-2">
              <Input
                id="primaryColor"
                type="color"
                value={config.primaryColor}
                onChange={(e) =>
                  setConfig({ ...config, primaryColor: e.target.value })
                }
                className="h-10 w-16"
              />
              <Input
                type="text"
                value={config.primaryColor}
                onChange={(e) =>
                  setConfig({ ...config, primaryColor: e.target.value })
                }
                placeholder="#f59e0b"
                className="flex-1 text-xs"
              />
            </div>
          </div>

          {/* Background Color */}
          <div className="space-y-2">
            <Label htmlFor="backgroundColor" className="text-xs font-medium">
              Background Color
            </Label>
            <p className="text-xs text-slate-500">Chat widget background</p>
            <div className="flex gap-2">
              <Input
                id="backgroundColor"
                type="color"
                value={config.backgroundColor}
                onChange={(e) =>
                  setConfig({ ...config, backgroundColor: e.target.value })
                }
                className="h-10 w-16"
              />
              <Input
                type="text"
                value={config.backgroundColor}
                onChange={(e) =>
                  setConfig({ ...config, backgroundColor: e.target.value })
                }
                placeholder="#fff4eb"
                className="flex-1 text-xs"
              />
            </div>
          </div>

          {/* Header Background */}
          <div className="space-y-2">
            <Label htmlFor="headerBackground" className="text-xs font-medium">
              Header Background{" "}
              <span className="font-normal text-red-500">(optional)</span>
            </Label>
            <p className="text-xs text-slate-500">Header section background</p>
            <div className="flex gap-2">
              <Input
                id="headerBackgroundColor"
                type="color"
                value={
                  config.headerBackground.startsWith("rgba")
                    ? "#ffffff"
                    : config.headerBackground
                }
                onChange={(e) =>
                  setConfig({ ...config, headerBackground: e.target.value })
                }
                className="h-10 w-16"
              />
              <Input
                type="text"
                value={config.headerBackground}
                onChange={(e) =>
                  setConfig({ ...config, headerBackground: e.target.value })
                }
                placeholder="rgba(255, 255, 255, 0.8)"
                className="flex-1 text-xs"
              />
            </div>
          </div>

          {/* Text Colors */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="textColor" className="text-xs font-medium">
                Text Color
              </Label>
              <p className="text-xs text-slate-500">Primary text</p>
              <div className="flex gap-2">
                <Input
                  id="textColor"
                  type="color"
                  value={config.textColor}
                  onChange={(e) =>
                    setConfig({ ...config, textColor: e.target.value })
                  }
                  className="h-10 w-12"
                />
                <Input
                  type="text"
                  value={config.textColor}
                  onChange={(e) =>
                    setConfig({ ...config, textColor: e.target.value })
                  }
                  className="flex-1 text-xs"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="textSecondaryColor"
                className="text-xs font-medium"
              >
                Secondary Text
              </Label>
              <p className="text-xs text-slate-500">Muted text</p>
              <div className="flex gap-2">
                <Input
                  id="textSecondaryColor"
                  type="color"
                  value={config.textSecondaryColor}
                  onChange={(e) =>
                    setConfig({ ...config, textSecondaryColor: e.target.value })
                  }
                  className="h-10 w-12"
                />
                <Input
                  type="text"
                  value={config.textSecondaryColor}
                  onChange={(e) =>
                    setConfig({ ...config, textSecondaryColor: e.target.value })
                  }
                  className="flex-1 text-xs"
                />
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Bubble Button Colors */}
      <Card className="p-4">
        <h4 className="mb-4 text-sm font-semibold text-slate-700">
          Bubble Button Colors
        </h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label
              htmlFor="bubbleBackgroundColor"
              className="text-xs font-medium"
            >
              Bubble Background
            </Label>
            <div className="flex gap-2">
              <Input
                id="bubbleBackgroundColor"
                type="color"
                value={config.bubbleBackgroundColor || config.primaryColor}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    bubbleBackgroundColor: e.target.value,
                  })
                }
                className="h-10 w-12"
              />
              <Input
                type="text"
                value={config.bubbleBackgroundColor}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    bubbleBackgroundColor: e.target.value,
                  })
                }
                placeholder="#f59e0b"
                className="flex-1 text-xs"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="bubbleTextColor" className="text-xs font-medium">
              Bubble Icon Color
            </Label>
            <div className="flex gap-2">
              <Input
                id="bubbleTextColor"
                type="color"
                value={config.bubbleTextColor}
                onChange={(e) =>
                  setConfig({ ...config, bubbleTextColor: e.target.value })
                }
                className="h-10 w-12"
              />
              <Input
                type="text"
                value={config.bubbleTextColor}
                onChange={(e) =>
                  setConfig({ ...config, bubbleTextColor: e.target.value })
                }
                placeholder="#ffffff"
                className="flex-1 text-xs"
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Message Colors */}
      <Card className="p-4">
        <h4 className="mb-4 text-sm font-semibold text-slate-700">
          Message Colors
        </h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="userMessageBg" className="text-xs font-medium">
              User Message Bg
            </Label>
            <div className="flex gap-2">
              <Input
                id="userMessageBg"
                type="color"
                value={config.userMessageBg || config.primaryColor}
                onChange={(e) =>
                  setConfig({ ...config, userMessageBg: e.target.value })
                }
                className="h-10 w-12"
              />
              <Input
                type="text"
                value={config.userMessageBg}
                onChange={(e) =>
                  setConfig({ ...config, userMessageBg: e.target.value })
                }
                placeholder="#3b82f6"
                className="flex-1 text-xs"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="botMessageBg" className="text-xs font-medium">
              Bot Message Bg
            </Label>
            <div className="flex gap-2">
              <Input
                id="botMessageBg"
                type="color"
                value={config.botMessageBg}
                onChange={(e) =>
                  setConfig({ ...config, botMessageBg: e.target.value })
                }
                className="h-10 w-12"
              />
              <Input
                type="text"
                value={config.botMessageBg}
                onChange={(e) =>
                  setConfig({ ...config, botMessageBg: e.target.value })
                }
                placeholder="#ffffff"
                className="flex-1 text-xs"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="userMessageTextColor"
              className="text-xs font-medium"
            >
              User Message Text
            </Label>
            <div className="flex gap-2">
              <Input
                id="userMessageTextColor"
                type="color"
                value={config.userMessageTextColor}
                onChange={(e) =>
                  setConfig({ ...config, userMessageTextColor: e.target.value })
                }
                className="h-10 w-12"
              />
              <Input
                type="text"
                value={config.userMessageTextColor}
                onChange={(e) =>
                  setConfig({ ...config, userMessageTextColor: e.target.value })
                }
                placeholder="#ffffff"
                className="flex-1 text-xs"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="botMessageTextColor"
              className="text-xs font-medium"
            >
              Bot Message Text
            </Label>
            <div className="flex gap-2">
              <Input
                id="botMessageTextColor"
                type="color"
                value={config.botMessageTextColor}
                onChange={(e) =>
                  setConfig({ ...config, botMessageTextColor: e.target.value })
                }
                className="h-10 w-12"
              />
              <Input
                type="text"
                value={config.botMessageTextColor}
                onChange={(e) =>
                  setConfig({ ...config, botMessageTextColor: e.target.value })
                }
                placeholder="#1f2937"
                className="flex-1 text-xs"
              />
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
