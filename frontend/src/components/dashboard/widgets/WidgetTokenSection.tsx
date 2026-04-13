"use client";

import { useState } from "react";
import {
  Copy,
  Check,
  Key,
  Trash2,
  AlertCircle,
  Plus,
  ShieldCheck,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import {
  useWidgetTokens,
  useCreateWidgetToken,
  useRevokeWidgetToken,
} from "@/lib/queries/users";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export function WidgetTokenSection() {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [tokenName, setTokenName] = useState("");
  const [tokenDescription, setTokenDescription] = useState("");

  const { data, isLoading, error } = useWidgetTokens();
  const createMutation = useCreateWidgetToken();
  const revokeMutation = useRevokeWidgetToken();

  const handleCopy = async (token: string, tokenId: string) => {
    await navigator.clipboard.writeText(token);
    setCopiedId(tokenId);
    toast.success("Token copied to clipboard");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleCreate = async () => {
    if (!tokenName.trim()) {
      toast.error("Token name is required");
      return;
    }

    trackDashboardOperation("widget_token_create", "started", {
      tokenName: tokenName.trim(),
    });

    try {
      await createMutation.mutateAsync({
        name: tokenName.trim(),
        description: tokenDescription.trim() || undefined,
      });

      trackDashboardOperation("widget_token_create", "success", {
        tokenName: tokenName.trim(),
      });

      toast.success("Token created successfully");
      setTokenName("");
      setTokenDescription("");
      setShowCreateForm(false);
    } catch (error) {
      trackDashboardOperation("widget_token_create", "error", {
        tokenName: tokenName.trim(),
        error: error instanceof Error ? error.message : "Unknown error",
      });
      toast.error("Failed to create token");
    }
  };

  const handleRevoke = async (tokenId: string, revokeTokenName: string) => {
    trackDashboardOperation("widget_token_revoke", "started", {
      tokenId,
      tokenName: revokeTokenName,
    });

    try {
      await revokeMutation.mutateAsync(tokenId);

      trackDashboardOperation("widget_token_revoke", "success", {
        tokenId,
        tokenName: revokeTokenName,
      });

      toast.success(`Token "${revokeTokenName}" revoked successfully`);
    } catch (error) {
      trackDashboardOperation("widget_token_revoke", "error", {
        tokenId,
        tokenName: revokeTokenName,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      toast.error("Failed to revoke token");
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-amber-100">
            <Key className="size-5 text-amber-600 animate-pulse" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Widget Tokens
            </h3>
            <p className="text-sm text-slate-600">Loading tokens...</p>
          </div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex size-10 items-center justify-center rounded-lg bg-red-100">
            <AlertCircle className="size-5 text-red-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Widget Tokens
            </h3>
            <p className="text-sm text-red-600">
              Failed to load tokens. Please try again.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  const allTokens = data?.tokens || [];
  const tokens = allTokens.filter((t) => t.is_active); // Only show active tokens
  const hasTokens = tokens.length > 0;

  return (
    <Card className="p-4 sm:p-6">
      {/* Header */}
      <div className="mb-4 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-amber-100">
            <Key className="size-5 text-amber-600" />
          </div>
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-slate-900 sm:text-lg">
              Widget Tokens
            </h3>
            <p className="text-xs text-slate-600 sm:text-sm">
              Manage authentication tokens for embedded widgets
            </p>
          </div>
        </div>
        <Button
          onClick={() => setShowCreateForm(!showCreateForm)}
          size="sm"
          variant={showCreateForm ? "outline" : "default"}
          className="w-full shrink-0 sm:w-auto"
        >
          <Plus className="size-4 mr-2" />
          New Token
        </Button>
      </div>

      {/* Create Token Form */}
      {showCreateForm && (
        <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3 sm:mb-6 sm:p-4">
          <h4 className="mb-3 text-sm font-semibold text-slate-900 sm:mb-4">
            Create New Token
          </h4>
          <div className="space-y-3 sm:space-y-4">
            <div>
              <Label htmlFor="token-name" className="text-xs sm:text-sm">
                Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="token-name"
                value={tokenName}
                onChange={(e) => setTokenName(e.target.value)}
                placeholder="e.g., Main Website, Blog Widget"
                maxLength={100}
                className="mt-1.5 text-xs sm:text-sm"
              />
              <p className="mt-1 text-[10px] text-slate-500 sm:text-xs">
                A descriptive name to identify this token
              </p>
            </div>
            <div>
              <Label htmlFor="token-description" className="text-xs sm:text-sm">
                Description (Optional)
              </Label>
              <Textarea
                id="token-description"
                value={tokenDescription}
                onChange={(e) => setTokenDescription(e.target.value)}
                placeholder="e.g., Token for example.com chat widget"
                maxLength={500}
                rows={2}
                className="mt-1.5 text-xs sm:text-sm"
              />
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                onClick={handleCreate}
                disabled={createMutation.isPending || !tokenName.trim()}
                size="sm"
                className="w-full sm:w-auto"
              >
                {createMutation.isPending ? "Creating..." : "Create Token"}
              </Button>
              <Button
                onClick={() => {
                  setShowCreateForm(false);
                  setTokenName("");
                  setTokenDescription("");
                }}
                variant="outline"
                size="sm"
                className="w-full sm:w-auto"
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Tokens List */}
      {!hasTokens ? (
        <div className="text-center py-12">
          <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-slate-100">
            <Key className="size-8 text-slate-400" />
          </div>
          <h4 className="text-sm font-semibold text-slate-900 mb-1">
            No tokens yet
          </h4>
          <p className="text-sm text-slate-600 mb-4">
            Create your first token to start embedding widgets
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-slate-700">
              Active Tokens ({tokens.length})
            </p>
          </div>

          {tokens.map((token) => (
            <div
              key={token.id}
              className="rounded-lg border border-slate-200 bg-white p-4"
            >
              {/* Token Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="size-5 text-green-600" />
                  <div>
                    <h5 className="text-sm font-semibold text-slate-900">
                      {token.name}
                    </h5>
                    {token.description && (
                      <p className="text-xs text-slate-600">
                        {token.description}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Token Value */}
              <div className="flex items-stretch gap-2 mb-3">
                <div className="flex-1 min-w-0 rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <code className="text-sm text-slate-900 block truncate">
                    {token.token}
                  </code>
                </div>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handleCopy(token.token, token.id)}
                  className="shrink-0 h-auto w-14"
                >
                  {copiedId === token.id ? (
                    <Check className="size-4 text-green-600" />
                  ) : (
                    <Copy className="size-4" />
                  )}
                </Button>
              </div>

              {/* Token Metadata */}
              <div className="flex items-center justify-between text-xs text-slate-500">
                <div className="flex items-center gap-4">
                  <span>Created: {formatDate(token.created_at)}</span>
                  {token.last_used_at ? (
                    <span>Last used: {formatDate(token.last_used_at)}</span>
                  ) : (
                    <span className="text-slate-400">Never used</span>
                  )}
                </div>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600 hover:text-red-700 hover:bg-red-50 h-7"
                      disabled={revokeMutation.isPending}
                    >
                      <Trash2 className="size-3 mr-1" />
                      Revoke
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>
                        Revoke &ldquo;{token.name}&rdquo;?
                      </AlertDialogTitle>
                      <AlertDialogDescription>
                        This will permanently disable this token. All widgets
                        using this token will stop working immediately. This
                        action cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => handleRevoke(token.id, token.name)}
                        className="bg-red-600 hover:bg-red-700"
                      >
                        Yes, Revoke Token
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
