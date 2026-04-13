"use client";

import { useState, useEffect } from "react";
import { SiZapier } from "react-icons/si";
import { Loader2, Link2, Trash2, ExternalLink } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  useGetWebhook,
  useCreateWebhook,
  useDeleteWebhook,
} from "@/lib/queries/webhooks";

interface ZapierWebhookDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ZapierWebhookDialog({
  open,
  onOpenChange,
}: ZapierWebhookDialogProps) {
  const [webhookUrl, setWebhookUrl] = useState("");

  // Fetch webhook config (account-level)
  const { data: webhook, isLoading: isLoadingWebhook } = useGetWebhook();

  // Mutations
  const createWebhook = useCreateWebhook();
  const deleteWebhook = useDeleteWebhook();

  // Update local state when webhook data loads
  useEffect(() => {
    if (webhook?.url) {
      setWebhookUrl(webhook.url);
    }
  }, [webhook?.url]);

  const handleConnect = () => {
    if (!webhookUrl.trim()) return;

    createWebhook.mutate(
      {
        url: webhookUrl.trim(),
        events: ["conversation.finished"],
      },
      {
        onSuccess: () => {
          // Keep dialog open to show success state
        },
      },
    );
  };

  const handleDisconnect = () => {
    deleteWebhook.mutate(undefined, {
      onSuccess: () => {
        setWebhookUrl("");
      },
    });
  };

  const isConnected = webhook?.enabled && webhook?.url;
  const isLoading =
    createWebhook.isPending || deleteWebhook.isPending || isLoadingWebhook;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded-lg bg-slate-100">
              <SiZapier className="size-8" style={{ color: "#FF4A00" }} />
            </div>
            <div>
              <DialogTitle>Connect Zapier</DialogTitle>
              <DialogDescription>
                Automatically send conversation transcripts to Zapier
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Info Alert */}
          <Alert>
            <AlertDescription className="text-sm">
              When conversations end, transcripts will be automatically sent to
              Zapier. Applies to all personas.
            </AlertDescription>
          </Alert>

          {/* Connection Status */}
          {isConnected && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge className="bg-green-600">Connected</Badge>
                  <span className="text-sm text-green-900">
                    Zapier is receiving your conversations
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleDisconnect}
                  disabled={isLoading}
                  className="text-red-600 hover:text-red-700"
                >
                  {isLoading ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <>
                      <Trash2 className="size-4 mr-2" />
                      Disconnect
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}

          {/* Webhook URL Input */}
          <div className="space-y-2">
            <Label htmlFor="webhook-url">Zapier URL</Label>
            <div className="flex gap-2">
              <Input
                id="webhook-url"
                type="url"
                placeholder="https://hooks.zapier.com/hooks/catch/..."
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                disabled={isLoading}
              />
              <Button
                onClick={handleConnect}
                disabled={!webhookUrl.trim() || isLoading}
                className="shrink-0"
              >
                {isLoading ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <>
                    <Link2 className="size-4 mr-2" />
                    {isConnected ? "Update" : "Connect"}
                  </>
                )}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Get this URL from your Zapier Zap setup
            </p>
          </div>

          {/* Current Webhook Info */}
          {isConnected && webhook?.url && (
            <div className="rounded-lg border bg-slate-50 p-3">
              <h4 className="text-sm font-medium mb-2">Connected URL</h4>
              <div className="flex items-start gap-2">
                <code className="flex-1 rounded bg-white px-2 py-1 text-xs break-all">
                  {webhook.url}
                </code>
              </div>
            </div>
          )}

          {/* Setup Instructions */}
          <div className="rounded-lg border bg-blue-50 p-4">
            <h4 className="text-sm font-semibold text-blue-900 mb-2">
              How to set up
            </h4>
            <ol className="space-y-1 text-sm text-blue-900 list-decimal list-inside">
              <li>Create a new Zap in Zapier with a webhook trigger</li>
              <li>Copy the webhook URL from Zapier</li>
              <li>Paste it above and click Connect</li>
              <li>Test with any conversation to see it in Zapier</li>
            </ol>
            <Button
              variant="link"
              size="sm"
              className="mt-2 p-0 h-auto text-blue-700"
              asChild
            >
              <a
                href="https://zapier.com/apps/webhook/integrations"
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="size-3 mr-1" />
                Learn more
              </a>
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
