"use client";

import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { WidgetConfig, EffectiveColors, ChatbotStyle } from "../types";
import { Sparkles, Layout } from "lucide-react";

interface LayoutTabProps {
  config: WidgetConfig;
  setConfig: (config: WidgetConfig) => void;
  colors: EffectiveColors;
}

export function LayoutTab({ config, setConfig, colors }: LayoutTabProps) {
  // Check if chatbot mode is enabled (modalPosition is set to a corner position)
  const isChatbotMode =
    !!config.modalPosition && config.modalPosition !== "centered";

  return (
    <div className="mt-4 space-y-4">
      {/* Position */}
      <Card className="p-4">
        <h4 className="mb-4 text-sm font-semibold text-slate-700">Position</h4>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="position" className="text-xs font-medium">
              Bubble Button Position
            </Label>
            <p className="text-xs text-slate-500">Corner of the screen</p>
            <Select
              value={config.position}
              onValueChange={(value) =>
                setConfig({ ...config, position: value })
              }
            >
              <SelectTrigger id="position" className="text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="bottom-right">Bottom Right</SelectItem>
                <SelectItem value="bottom-left">Bottom Left</SelectItem>
                <SelectItem value="top-right">Top Right</SelectItem>
                <SelectItem value="top-left">Top Left</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="modalPosition" className="text-xs font-medium">
              Chat Modal Position
            </Label>
            <p className="text-xs text-slate-500">
              Where the chat opens (leave as centered for default behavior)
            </p>
            <Select
              value={config.modalPosition || "centered"}
              onValueChange={(value) =>
                setConfig({
                  ...config,
                  modalPosition: value === "centered" ? "" : value,
                })
              }
            >
              <SelectTrigger id="modalPosition" className="text-xs">
                <SelectValue placeholder="Centered (default)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="centered">Centered (Default)</SelectItem>
                <SelectItem value="bottom-right">
                  Bottom Right (Chatbot-style)
                </SelectItem>
                <SelectItem value="bottom-left">Bottom Left</SelectItem>
                <SelectItem value="top-right">Top Right</SelectItem>
                <SelectItem value="top-left">Top Left</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Chatbot Mode Options - Only show when modalPosition is set to a corner */}
          {isChatbotMode && (
            <div className="space-y-3">
              {/* Chatbot Style Selector */}
              <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
                <div className="mb-3 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-amber-600" />
                  <span className="text-xs font-semibold text-amber-800">
                    Chatbot Style
                  </span>
                </div>
                <div className="space-y-2">
                  <p className="text-xs text-amber-700">
                    Choose the layout style for your chatbot modal
                  </p>
                  <Select
                    value={config.chatbotStyle || "guide"}
                    onValueChange={(value: ChatbotStyle) =>
                      setConfig({ ...config, chatbotStyle: value })
                    }
                  >
                    <SelectTrigger className="text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="guide">
                        <div className="flex flex-col">
                          <span className="font-medium">
                            Guide Style (Recommended)
                          </span>
                          <span className="text-[10px] text-slate-500">
                            Centered avatar, mode toggle, inline transcript
                          </span>
                        </div>
                      </SelectItem>
                      <SelectItem value="classic">
                        <div className="flex flex-col">
                          <span className="font-medium">Classic Style</span>
                          <span className="text-[10px] text-slate-500">
                            Header with avatar/name, full chat interface
                          </span>
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Chatbot Modal Size */}
              <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
                <div className="mb-3 flex items-center gap-2">
                  <Layout className="h-4 w-4 text-amber-600" />
                  <span className="text-xs font-semibold text-amber-800">
                    Chatbot Modal Size
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label
                      htmlFor="chatbotWidth"
                      className="text-xs font-medium text-amber-900"
                    >
                      Width
                    </Label>
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
                  <div className="space-y-1">
                    <Label
                      htmlFor="chatbotHeight"
                      className="text-xs font-medium text-amber-900"
                    >
                      Height
                    </Label>
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
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="offsetX" className="text-xs font-medium">
                Horizontal Offset
              </Label>
              <Input
                id="offsetX"
                type="text"
                value={config.offsetX}
                onChange={(e) =>
                  setConfig({ ...config, offsetX: e.target.value })
                }
                placeholder="20px"
                className="text-xs"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="offsetY" className="text-xs font-medium">
                Vertical Offset
              </Label>
              <Input
                id="offsetY"
                type="text"
                value={config.offsetY}
                onChange={(e) =>
                  setConfig({ ...config, offsetY: e.target.value })
                }
                placeholder="20px"
                className="text-xs"
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Position Preview */}
      <Card className="p-4">
        <h4 className="mb-3 text-sm font-semibold text-slate-700">
          Position Preview
        </h4>
        <div className="relative h-40 rounded-lg border-2 border-dashed border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100">
          <div className="absolute left-3 top-3 text-[10px] text-slate-400">
            yourwebsite.com
          </div>
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
            <div className="text-xs font-medium text-slate-400">
              Your Website
            </div>
            <div className="text-[10px] text-slate-300">
              Bubble: {config.position.replace("-", " ")}
            </div>
          </div>

          {/* Bubble preview */}
          <div
            className="absolute flex items-center justify-center rounded-full shadow-lg transition-all duration-300"
            style={{
              width: "32px",
              height: "32px",
              background: colors.bubbleBg,
              ...(config.position === "bottom-right" && {
                bottom: "8px",
                right: "8px",
              }),
              ...(config.position === "bottom-left" && {
                bottom: "8px",
                left: "8px",
              }),
              ...(config.position === "top-right" && {
                top: "8px",
                right: "8px",
              }),
              ...(config.position === "top-left" && {
                top: "8px",
                left: "8px",
              }),
            }}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 28 28"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M14 2.33337C7.55672 2.33337 2.33337 7.03171 2.33337 12.8334C2.33337 15.3184 3.29837 17.5867 4.90171 19.3634V25.6667L10.7617 22.5167C11.8017 22.7517 12.8834 22.8767 14 22.8767C20.4434 22.8767 25.6667 18.1784 25.6667 12.3767C25.6667 6.57504 20.4434 2.33337 14 2.33337Z"
                fill={colors.bubbleText}
              />
            </svg>
          </div>
        </div>
      </Card>
    </div>
  );
}
