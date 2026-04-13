"use client";

import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { WidgetConfig } from "../types";

interface BrandTabProps {
  config: WidgetConfig;
  setConfig: (config: WidgetConfig) => void;
}

export function BrandTab({ config, setConfig }: BrandTabProps) {
  return (
    <div className="mt-4 space-y-4">
      {/* Header Customization */}
      <Card className="p-4">
        <h4 className="mb-4 text-sm font-semibold text-slate-700">
          Header Customization
        </h4>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="headerTitle" className="text-xs font-medium">
              Custom Title
            </Label>
            <Input
              id="headerTitle"
              type="text"
              value={config.headerTitle}
              onChange={(e) =>
                setConfig({ ...config, headerTitle: e.target.value })
              }
              placeholder="Leave empty to use username"
              className="text-xs"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="headerSubtitle" className="text-xs font-medium">
              Custom Subtitle
            </Label>
            <Input
              id="headerSubtitle"
              type="text"
              value={config.headerSubtitle}
              onChange={(e) =>
                setConfig({ ...config, headerSubtitle: e.target.value })
              }
              placeholder="e.g., AI Assistant"
              className="text-xs"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="avatarUrl" className="text-xs font-medium">
              Custom Avatar URL
            </Label>
            <Input
              id="avatarUrl"
              type="text"
              value={config.avatarUrl}
              onChange={(e) =>
                setConfig({ ...config, avatarUrl: e.target.value })
              }
              placeholder="https://example.com/avatar.png"
              className="text-xs"
            />
          </div>
        </div>
      </Card>

      {/* Widget Text */}
      <Card className="p-4">
        <h4 className="mb-4 text-sm font-semibold text-slate-700">
          Widget Text
        </h4>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="bubbleText" className="text-xs font-medium">
              Bubble Button Text
            </Label>
            <p className="text-xs text-slate-500">
              Text shown on the chat bubble button
            </p>
            <Input
              id="bubbleText"
              type="text"
              value={config.bubbleText}
              onChange={(e) =>
                setConfig({ ...config, bubbleText: e.target.value })
              }
              placeholder="Chat with me"
              className="text-xs"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="bubbleIcon" className="text-xs font-medium">
              Custom Bubble Icon URL{" "}
              <span className="text-slate-400">(Optional)</span>
            </Label>
            <p className="text-xs text-slate-500">
              Override the bubble icon with a different image. If empty, uses
              the avatar URL above.
            </p>
            <Input
              id="bubbleIcon"
              type="text"
              value={config.bubbleIcon}
              onChange={(e) =>
                setConfig({ ...config, bubbleIcon: e.target.value })
              }
              placeholder="https://example.com/bubble-icon.png"
              className="text-xs"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="welcomeMessage" className="text-xs font-medium">
              Welcome Message
            </Label>
            <p className="text-xs text-slate-500">
              Initial greeting message when chat opens
            </p>
            <Input
              id="welcomeMessage"
              type="text"
              value={config.welcomeMessage}
              onChange={(e) =>
                setConfig({ ...config, welcomeMessage: e.target.value })
              }
              placeholder="Hello! How can I help you?"
              className="text-xs"
            />
          </div>
        </div>
      </Card>

      {/* Visibility & Behavior */}
      <Card className="p-4">
        <h4 className="mb-4 text-sm font-semibold text-slate-700">
          Visibility & Behavior
        </h4>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="showAvatar" className="text-xs font-medium">
                Show Avatar
              </Label>
              <p className="text-xs text-slate-500">Display avatar in header</p>
            </div>
            <Switch
              id="showAvatar"
              checked={config.showAvatar}
              onCheckedChange={(checked) =>
                setConfig({ ...config, showAvatar: checked })
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="showBranding" className="text-xs font-medium">
                Show AI Branding
              </Label>
              <p className="text-xs text-slate-500">
                &quot;AI powered digital clone&quot; badge
              </p>
            </div>
            <Switch
              id="showBranding"
              checked={config.showBranding}
              onCheckedChange={(checked) =>
                setConfig({ ...config, showBranding: checked })
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="enableVoice" className="text-xs font-medium">
                Enable Voice Chat
              </Label>
              <p className="text-xs text-slate-500">
                Allow voice conversations
              </p>
            </div>
            <Switch
              id="enableVoice"
              checked={config.enableVoice}
              onCheckedChange={(checked) =>
                setConfig({ ...config, enableVoice: checked })
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="simpleBubble" className="text-xs font-medium">
                Simple Bubble
              </Label>
              <p className="text-xs text-slate-500">
                Disable animations (waves, floating, tooltips)
              </p>
            </div>
            <Switch
              id="simpleBubble"
              checked={config.simpleBubble}
              onCheckedChange={(checked) =>
                setConfig({ ...config, simpleBubble: checked })
              }
            />
          </div>
        </div>
      </Card>
    </div>
  );
}
