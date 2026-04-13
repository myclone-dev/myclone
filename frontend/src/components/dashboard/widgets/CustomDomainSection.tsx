"use client";

import { useState, useEffect } from "react";
import {
  Globe,
  Plus,
  AlertCircle,
  ShieldCheck,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  Sparkles,
  Lock,
  Zap,
  Info,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  useCustomDomains,
  useAddCustomDomain,
  useVerifyCustomDomain,
  useDeleteCustomDomain,
  type CustomDomainResponse,
} from "@/lib/queries/users";
import { useUserUsage } from "@/lib/queries/tier";
import { DomainCard } from "./DomainCard";

export function CustomDomainSection() {
  const [showAddForm, setShowAddForm] = useState(false);
  const [domainInput, setDomainInput] = useState("");
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useCustomDomains();
  const { data: usageData } = useUserUsage();
  const addMutation = useAddCustomDomain();
  const verifyMutation = useVerifyCustomDomain();
  const deleteMutation = useDeleteCustomDomain();

  // Get domain limit from usage data
  const maxDomains = usageData?.custom_domains?.limit ?? 0;
  const isUnlimited = maxDomains === -1;

  // Auto-poll for domains in "verified" status (pending activation)
  // Check every 30 seconds if there are any verified domains waiting for activation
  useEffect(() => {
    if (!data?.domains) return;

    const hasVerifiedDomains = data.domains.some(
      (domain) => domain.status === "verified" && !domain.ssl_ready,
    );

    if (!hasVerifiedDomains) return;

    // Poll every 30 seconds
    const interval = setInterval(() => {
      refetch();
    }, 30000);

    return () => clearInterval(interval);
  }, [data?.domains, refetch]);

  const handleCopy = async (text: string, fieldId: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleAdd = async () => {
    let domain = domainInput.trim().toLowerCase();

    // Strip protocol prefixes if user pasted a URL
    domain = domain
      .replace(/^https?:\/\//, "")
      .replace(/\/.*$/, "")
      .trim();

    if (!domain) {
      toast.error("Please enter a domain");
      return;
    }

    // Basic validation
    if (!domain.includes(".") || domain.length < 4) {
      toast.error("Please enter a valid domain (e.g., chat.example.com)");
      return;
    }

    try {
      await addMutation.mutateAsync({ domain });
      toast.success("Domain added successfully", {
        description: "Configure DNS records to complete setup",
        duration: 5000,
      });
      setDomainInput("");
      setShowAddForm(false);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to add domain";

      // Check if it's a conflict error (domain already exists)
      const isConflict = message.toLowerCase().includes("already");

      toast.error(
        isConflict ? "Domain Already Exists" : "Failed to add domain",
        {
          description: message,
          duration: isConflict ? 8000 : 5000,
        },
      );
    }
  };

  const handleVerify = async (domainId: string, domainName: string) => {
    try {
      const result = await verifyMutation.mutateAsync(domainId);

      if (result.success && result.verified) {
        toast.success(`${domainName} verified!`, {
          description: "Your domain is now active",
          duration: 5000,
        });
        return;
      }

      if (result.success && !result.verified) {
        toast.info(`${domainName} ownership verified`, {
          description:
            result.message || "SSL provisioning and activation pending.",
          duration: 7000,
        });
        return;
      }

      toast.error(`Verification failed for ${domainName}`, {
        description:
          result.message ||
          "DNS records not found. Please check your configuration.",
        duration: 7000,
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : undefined;
      toast.error("Failed to verify domain", {
        description: message,
      });
    }
  };

  const handleDelete = async (domainId: string, domainName: string) => {
    try {
      await deleteMutation.mutateAsync(domainId);
      toast.success(`${domainName} removed`);
    } catch {
      toast.error("Failed to remove domain");
    }
  };

  const getStatusBadge = (domain: CustomDomainResponse) => {
    switch (domain.status) {
      case "active":
        return (
          <Badge className="bg-green-100 text-green-700 hover:bg-green-100 border-green-200">
            <CheckCircle2 className="mr-1 size-3" />
            Active
          </Badge>
        );
      case "verified":
        return (
          <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100 border-blue-200">
            <ShieldCheck className="mr-1 size-3" />
            Pending Activation
          </Badge>
        );
      case "verifying":
        return (
          <Badge className="bg-yellow-100 text-yellow-700 hover:bg-yellow-100 border-yellow-200">
            <RefreshCw className="mr-1 size-3 animate-spin" />
            Verifying
          </Badge>
        );
      case "pending":
        return (
          <Badge className="bg-slate-100 text-slate-600 hover:bg-slate-100 border-slate-200">
            <Clock className="mr-1 size-3" />
            Pending DNS
          </Badge>
        );
      case "failed":
        return (
          <Badge className="bg-red-100 text-red-700 hover:bg-red-100 border-red-200">
            <XCircle className="mr-1 size-3" />
            Failed
          </Badge>
        );
      case "expired":
        return (
          <Badge className="bg-gray-100 text-gray-600 hover:bg-gray-100 border-gray-200">
            <Clock className="mr-1 size-3" />
            Expired
          </Badge>
        );
      default:
        return <Badge variant="secondary">{domain.status}</Badge>;
    }
  };

  if (isLoading) {
    return (
      <Card className="p-6 sm:p-8">
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded-full bg-yellow-light">
              <Globe className="size-6 text-yellow-600 animate-pulse" />
            </div>
            <p className="text-sm text-slate-500">Loading domain...</p>
          </div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 sm:p-8">
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded-full bg-red-100">
              <AlertCircle className="size-6 text-red-600" />
            </div>
            <p className="text-sm text-red-600">
              Failed to load domain. Please try again.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  const domains = data?.domains || [];
  const domainCount = domains.length;
  // Check if user can add more domains
  const canAddMore = isUnlimited || domainCount < maxDomains;
  const hasDomains = domains.length > 0;

  return (
    <div className="rounded-xl overflow-hidden border border-yellow-bright/30 bg-white shadow-sm">
      {/* Header with gradient accent */}
      <div className="bg-linear-to-r from-yellow-light/80 to-yellow-bright/30 p-4 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-base sm:text-lg font-semibold text-slate-900">
                Custom Domain
              </h3>
              {hasDomains && (
                <Badge className="text-xs bg-yellow-bright text-gray-800 hover:bg-yellow-bright border-0">
                  {domainCount} {domainCount === 1 ? "Domain" : "Domains"}
                </Badge>
              )}
            </div>
            <p className="text-xs sm:text-sm text-slate-600">
              Connect your own domain for a fully branded experience
              {!isUnlimited && (
                <span className="ml-1 text-slate-500">
                  ({domainCount}/{maxDomains} domains used)
                </span>
              )}
            </p>
          </div>
          {canAddMore && (
            <Button
              onClick={() => setShowAddForm(!showAddForm)}
              size="sm"
              variant={showAddForm ? "outline" : "default"}
              className="w-full sm:w-auto"
              disabled={!canAddMore}
            >
              <Plus className="size-4 mr-2" />
              Add Domain
            </Button>
          )}
          {!canAddMore && !isUnlimited && (
            <div className="text-xs text-slate-500 text-right">
              Limit reached ({maxDomains} max)
            </div>
          )}
        </div>
      </div>

      <div className="p-4 sm:p-6">
        {/* Add Domain Form */}
        {showAddForm && canAddMore && (
          <div className="mb-6 rounded-xl border-2 border-dashed border-yellow-bright/50 bg-yellow-light/30 p-4 sm:p-5">
            <div className="flex items-start gap-3 mb-4">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-yellow-bright">
                <Globe className="size-4 text-gray-900" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-slate-900">
                  Add Your Custom Domain
                </h4>
                <p className="text-xs text-slate-600 mt-0.5">
                  Enter your domain without https:// prefix
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <Label htmlFor="domain-input" className="text-xs sm:text-sm">
                  Domain Name <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="domain-input"
                  value={domainInput}
                  onChange={(e) => setDomainInput(e.target.value)}
                  placeholder="e.g., chat.yourcompany.com or yourcompany.com"
                  className="mt-1.5 bg-white"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleAdd();
                  }}
                />
                <div className="mt-2 flex items-start gap-1.5 text-[11px] text-slate-500">
                  <Info className="size-3 mt-0.5 shrink-0" />
                  <span>
                    You can use a subdomain (chat.example.com) or apex domain
                    (example.com)
                  </span>
                </div>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  onClick={handleAdd}
                  disabled={addMutation.isPending || !domainInput.trim()}
                  size="sm"
                  className="w-full sm:w-auto"
                >
                  {addMutation.isPending ? (
                    <>
                      <RefreshCw className="size-4 mr-2 animate-spin" />
                      Adding...
                    </>
                  ) : (
                    <>
                      <Plus className="size-4 mr-2" />
                      Add Domain
                    </>
                  )}
                </Button>
                <Button
                  onClick={() => {
                    setShowAddForm(false);
                    setDomainInput("");
                  }}
                  variant="ghost"
                  size="sm"
                  className="w-full sm:w-auto"
                >
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Limit Reached Message */}
        {!canAddMore && !isUnlimited && domainCount > 0 && (
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="size-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-semibold text-amber-900 mb-1">
                  Domain Limit Reached
                </h4>
                <p className="text-xs text-amber-700">
                  You've reached your plan's limit of {maxDomains} custom{" "}
                  {maxDomains === 1 ? "domain" : "domains"}. Upgrade your plan
                  to add more domains.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!hasDomains && !showAddForm && canAddMore && (
          <div className="text-center py-12 sm:py-16">
            <div className="mx-auto mb-4 flex size-16 sm:size-20 items-center justify-center rounded-full bg-linear-to-br from-yellow-light to-yellow-bright/50">
              <Globe className="size-8 sm:size-10 text-gray-800" />
            </div>
            <h4 className="text-base sm:text-lg font-semibold text-slate-900 mb-2">
              Launch on Your Own Domain
            </h4>
            <p className="text-sm text-slate-600 mb-6 max-w-md mx-auto">
              Connect a custom domain to host your AI clone with your own
              branding. Perfect for businesses and personal brands.
            </p>

            {/* Benefits */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl mx-auto mb-6">
              <div className="flex items-center gap-2 justify-center text-xs sm:text-sm text-slate-600 bg-slate-50 rounded-lg py-2 px-3">
                <Sparkles className="size-4 text-amber-500" />
                <span>White-label branding</span>
              </div>
              <div className="flex items-center gap-2 justify-center text-xs sm:text-sm text-slate-600 bg-slate-50 rounded-lg py-2 px-3">
                <Lock className="size-4 text-green-500" />
                <span>Free SSL certificate</span>
              </div>
              <div className="flex items-center gap-2 justify-center text-xs sm:text-sm text-slate-600 bg-slate-50 rounded-lg py-2 px-3">
                <Zap className="size-4 text-amber-500" />
                <span>Instant setup</span>
              </div>
            </div>

            <Button onClick={() => setShowAddForm(true)}>
              <Plus className="size-4 mr-2" />
              Add Your Domain
            </Button>
          </div>
        )}

        {/* Domain List */}
        {hasDomains && (
          <div className="space-y-4">
            {domains.map((domain) => (
              <DomainCard
                key={domain.id}
                domain={domain}
                getStatusBadge={getStatusBadge}
                handleVerify={handleVerify}
                handleDelete={handleDelete}
                handleCopy={handleCopy}
                onRefresh={() => {
                  refetch();
                  toast.info("Refreshing domain status...");
                }}
                copiedField={copiedField}
                verifyMutation={verifyMutation}
                deleteMutation={deleteMutation}
              />
            ))}
          </div>
        )}

        {/* How it works - only show when there is a domain or form is shown */}
        {(hasDomains || showAddForm) && (
          <div className="mt-6 rounded-xl border border-yellow-bright/20 bg-yellow-light/20 p-4">
            <h4 className="text-sm font-semibold text-slate-800 mb-3 flex items-center gap-2">
              <Info className="size-4 text-slate-500" />
              How to Set Up Your Domain
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 text-xs">
              <div className="flex items-start gap-2">
                <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-yellow-bright text-gray-800 font-semibold text-[10px]">
                  1
                </div>
                <span className="text-slate-600">Add your domain above</span>
              </div>
              <div className="flex items-start gap-2">
                <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-yellow-bright text-gray-800 font-semibold text-[10px]">
                  2
                </div>
                <span className="text-slate-600">Copy DNS records shown</span>
              </div>
              <div className="flex items-start gap-2">
                <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-yellow-bright text-gray-800 font-semibold text-[10px]">
                  3
                </div>
                <span className="text-slate-600">Add to your registrar</span>
              </div>
              <div className="flex items-start gap-2">
                <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-yellow-bright text-gray-800 font-semibold text-[10px]">
                  4
                </div>
                <span className="text-slate-600">Wait for propagation</span>
              </div>
              <div className="flex items-start gap-2">
                <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-green-100 text-green-700 font-semibold text-[10px]">
                  5
                </div>
                <span className="text-slate-600">Click Verify to go live</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
