"use client";

import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { WidgetConfig } from "../types";
import { MessageSquare } from "lucide-react";

interface SizeTabProps {
  config: WidgetConfig;
  setConfig: (config: WidgetConfig) => void;
}

export function SizeTab({ config, setConfig }: SizeTabProps) {
  // Check if chatbot mode is enabled (modalPosition is set to a corner position)
  const isChatbotMode =
    !!config.modalPosition && config.modalPosition !== "centered";

  return (
    <div className="mt-4 space-y-4">
      {/* Chatbot Mode Size - Only show when modalPosition is set to a corner */}
      {isChatbotMode && (
        <Card className="border-amber-200 bg-amber-50/50 p-4">
          <div className="mb-4 flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-amber-600" />
            <h4 className="text-sm font-semibold text-amber-800">
              Chatbot Modal Size
            </h4>
          </div>
          <p className="mb-4 text-xs text-amber-700">
            Customize the size of the chatbot-style modal that appears in the{" "}
            {config.modalPosition} corner.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="chatbotWidth" className="text-xs font-medium">
                Width
              </Label>
              <p className="text-xs text-slate-500">Chatbot modal width</p>
              <Input
                id="chatbotWidth"
                type="text"
                value={config.chatbotWidth}
                onChange={(e) =>
                  setConfig({ ...config, chatbotWidth: e.target.value })
                }
                placeholder="380px"
                className="text-xs"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="chatbotHeight" className="text-xs font-medium">
                Height
              </Label>
              <p className="text-xs text-slate-500">Chatbot modal height</p>
              <Input
                id="chatbotHeight"
                type="text"
                value={config.chatbotHeight}
                onChange={(e) =>
                  setConfig({ ...config, chatbotHeight: e.target.value })
                }
                placeholder="550px"
                className="text-xs"
              />
            </div>
          </div>
        </Card>
      )}

      {/* Chat Modal Size (Centered Overlay) */}
      <Card className="p-4">
        <h4 className="mb-4 text-sm font-semibold text-slate-700">
          {isChatbotMode ? "Centered Overlay Size" : "Chat Modal Size"}
        </h4>
        {isChatbotMode && (
          <p className="mb-4 text-xs text-slate-500">
            These settings apply when using the centered overlay mode.
          </p>
        )}
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="width" className="text-xs font-medium">
                Width
              </Label>
              <p className="text-xs text-slate-500">Modal width</p>
              <Input
                id="width"
                type="text"
                value={config.width}
                onChange={(e) =>
                  setConfig({ ...config, width: e.target.value })
                }
                placeholder="900px"
                className="text-xs"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="height" className="text-xs font-medium">
                Height
              </Label>
              <p className="text-xs text-slate-500">Modal height</p>
              <Input
                id="height"
                type="text"
                value={config.height}
                onChange={(e) =>
                  setConfig({ ...config, height: e.target.value })
                }
                placeholder="820px"
                className="text-xs"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="borderRadius" className="text-xs font-medium">
              Border Radius
            </Label>
            <p className="text-xs text-slate-500">Corner roundness</p>
            <Input
              id="borderRadius"
              type="text"
              value={config.borderRadius}
              onChange={(e) =>
                setConfig({ ...config, borderRadius: e.target.value })
              }
              placeholder="16px"
              className="text-xs"
            />
          </div>
        </div>
      </Card>

      {/* Bubble Button Size */}
      <Card className="p-4">
        <h4 className="mb-4 text-sm font-semibold text-slate-700">
          Bubble Button Size
        </h4>
        <div className="space-y-2">
          <Label htmlFor="bubbleSize" className="text-xs font-medium">
            Bubble Size
          </Label>
          <p className="text-xs text-slate-500">Floating button size</p>
          <Input
            id="bubbleSize"
            type="text"
            value={config.bubbleSize}
            onChange={(e) =>
              setConfig({ ...config, bubbleSize: e.target.value })
            }
            placeholder="60px"
            className="text-xs"
          />
        </div>
      </Card>
    </div>
  );
}
