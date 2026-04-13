"use client";

import { useState } from "react";
import {
  Mail,
  Plus,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  Trash2,
  Crown,
  Clock,
  Info,
  Globe,
  ExternalLink,
  HelpCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
import { toast } from "sonner";
import {
  useCustomEmailDomains,
  useAddCustomEmailDomain,
  useVerifyEmailDomain,
  useDeleteEmailDomain,
  type CustomEmailDomain,
  type EmailDNSRecord,
} from "@/lib/queries/users";

interface EmailDomainsSectionProps {
  isEnterprise: boolean;
}

export function EmailDomainsSection({
  isEnterprise,
}: EmailDomainsSectionProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [domainInput, setDomainInput] = useState("");
  const [fromEmailInput, setFromEmailInput] = useState("");
  const [fromNameInput, setFromNameInput] = useState("");
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const { data: domains, isLoading } = useCustomEmailDomains();
  const addMutation = useAddCustomEmailDomain();
  const verifyMutation = useVerifyEmailDomain();
  const deleteMutation = useDeleteEmailDomain();

  const handleCopy = async (text: string, fieldId: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleAdd = async () => {
    let domain = domainInput.trim().toLowerCase();
    const fromEmail = fromEmailInput.trim().toLowerCase();
    const fromName = fromNameInput.trim() || undefined;

    // Strip protocol prefixes if user pasted a URL
    domain = domain
      .replace(/^https?:\/\//, "")
      .replace(/\/.*$/, "")
      .trim();

    if (!domain) {
      toast.error("Please enter a domain");
      return;
    }

    if (!fromEmail) {
      toast.error("Please enter a sender email address");
      return;
    }

    // Validate email matches domain
    const emailDomain = fromEmail.split("@")[1];
    if (emailDomain !== domain) {
      toast.error(`Email must be from ${domain}`);
      return;
    }

    try {
      await addMutation.mutateAsync({
        domain,
        from_email: fromEmail,
        from_name: fromName,
      });
      setDomainInput("");
      setFromEmailInput("");
      setFromNameInput("");
      setShowAddForm(false);
    } catch {
      // Error toast handled by mutation
    }
  };

  const handleVerify = async (domainId: string) => {
    try {
      await verifyMutation.mutateAsync(domainId);
    } catch {
      // Error toast handled by mutation
    }
  };

  const handleDelete = async (domainId: string) => {
    try {
      await deleteMutation.mutateAsync(domainId);
    } catch {
      // Error toast handled by mutation
    }
  };

  // Enterprise upgrade prompt
  if (!isEnterprise) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="size-5" />
            Custom Email Domain
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-center">
            <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-yellow-bright/20">
              <Crown className="size-6 text-yellow-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900">
              Enterprise Feature
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              Send verification emails from your own domain instead of
              myclone.is. Upgrade to Enterprise to unlock custom email domains.
            </p>
            <Button className="mt-4 bg-ai-gold text-gray-900 hover:bg-ai-gold/90">
              Upgrade to Enterprise
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Mail className="size-5" />
          Custom Email Domain
        </CardTitle>
        {!showAddForm && domains && domains.length === 0 && (
          <Button
            onClick={() => setShowAddForm(true)}
            size="sm"
            className="bg-ai-gold text-gray-900 hover:bg-ai-gold/90"
          >
            <Plus className="size-4 mr-1" />
            Add Domain
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Info banner */}
        <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-4">
          <div className="flex gap-3">
            <Info className="size-5 text-yellow-600 shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-800">
              <p className="font-medium">Send emails from your brand</p>
              <p className="mt-1 text-yellow-700">
                Verification emails sent to visitors will come from your domain
                instead of myclone.is. You&apos;ll need to add DNS records to
                verify ownership.
              </p>
            </div>
          </div>
        </div>

        {/* Add Domain Form */}
        {showAddForm && (
          <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-4">
            <h4 className="font-medium text-gray-900">Add Email Domain</h4>

            <div className="space-y-3">
              <div>
                <Label htmlFor="domain">Domain</Label>
                <Input
                  id="domain"
                  placeholder="example.com"
                  value={domainInput}
                  onChange={(e) => setDomainInput(e.target.value)}
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="from_email">Sender Email</Label>
                <Input
                  id="from_email"
                  placeholder="hello@example.com"
                  value={fromEmailInput}
                  onChange={(e) => setFromEmailInput(e.target.value)}
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Must be an email on the domain above
                </p>
              </div>

              <div>
                <Label htmlFor="from_name">Sender Name (optional)</Label>
                <Input
                  id="from_name"
                  placeholder="Acme Support"
                  value={fromNameInput}
                  onChange={(e) => setFromNameInput(e.target.value)}
                  className="mt-1"
                />
              </div>
            </div>

            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                onClick={() => {
                  setShowAddForm(false);
                  setDomainInput("");
                  setFromEmailInput("");
                  setFromNameInput("");
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={handleAdd}
                disabled={addMutation.isPending}
                className="bg-ai-gold text-gray-900 hover:bg-ai-gold/90"
              >
                {addMutation.isPending ? (
                  <>
                    <RefreshCw className="size-4 mr-1 animate-spin" />
                    Adding...
                  </>
                ) : (
                  "Add Domain"
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="text-center py-8 text-gray-500">
            <RefreshCw className="size-5 animate-spin mx-auto mb-2" />
            Loading domains...
          </div>
        )}

        {/* Domain list */}
        {!isLoading && domains && domains.length > 0 && (
          <div className="space-y-4">
            {domains.map((domain) => (
              <EmailDomainCard
                key={domain.id}
                domain={domain}
                onVerify={() => handleVerify(domain.id)}
                onDelete={() => handleDelete(domain.id)}
                onCopy={handleCopy}
                copiedField={copiedField}
                isVerifying={verifyMutation.isPending}
                isDeleting={deleteMutation.isPending}
              />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && (!domains || domains.length === 0) && !showAddForm && (
          <div className="text-center py-8 text-gray-500">
            <Mail className="size-8 mx-auto mb-2 opacity-50" />
            <p>No custom email domains configured</p>
            <p className="text-sm">
              Add a domain to send emails from your brand
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Email Domain Card Component
// ============================================================================

interface EmailDomainCardProps {
  domain: CustomEmailDomain;
  onVerify: () => void;
  onDelete: () => void;
  onCopy: (text: string, fieldId: string) => void;
  copiedField: string | null;
  isVerifying: boolean;
  isDeleting: boolean;
}

function EmailDomainCard({
  domain,
  onVerify,
  onDelete,
  onCopy,
  copiedField,
  isVerifying,
  isDeleting,
}: EmailDomainCardProps) {
  const isVerified = domain.status === "verified";
  const isPending =
    domain.status === "pending" || domain.status === "verifying";
  const isFailed = domain.status === "failed";

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "numeric",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-full bg-yellow-100">
            <Globe className="size-5 text-yellow-600" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-900">
                {domain.domain}
              </span>
              {isVerified && (
                <Badge className="bg-green-100 text-green-700 border-0 hover:bg-green-100">
                  <CheckCircle2 className="size-3 mr-1" />
                  Active
                </Badge>
              )}
              {isPending && (
                <Badge className="bg-yellow-100 text-yellow-700 border-0 hover:bg-yellow-100">
                  <Clock className="size-3 mr-1" />
                  Pending DNS
                </Badge>
              )}
              {isFailed && (
                <Badge className="bg-red-100 text-red-700 border-0 hover:bg-red-100">
                  <XCircle className="size-3 mr-1" />
                  Failed
                </Badge>
              )}
            </div>
            <p className="text-sm text-gray-500">
              Added {formatDate(domain.created_at)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isPending && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onVerify}
              disabled={isVerifying}
              className="text-gray-600 hover:text-gray-900"
            >
              <RefreshCw
                className={`size-4 mr-1.5 ${isVerifying ? "animate-spin" : ""}`}
              />
              Verify
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            className="text-gray-600 hover:text-gray-900"
            onClick={onVerify}
            disabled={isVerifying}
          >
            <RefreshCw
              className={`size-4 mr-1.5 ${isVerifying ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="text-gray-400 hover:text-red-600"
              >
                <Trash2 className="size-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Email Domain</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete {domain.domain}? Emails will
                  be sent from the default ConvoxAI domain after deletion.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={onDelete}
                  disabled={isDeleting}
                  className="bg-red-600 hover:bg-red-700"
                >
                  {isDeleting ? "Deleting..." : "Delete"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* DNS Records - Resend Style Table */}
      {isPending && domain.dns_records && domain.dns_records.length > 0 && (
        <div className="border-t border-gray-200">
          {/* DNS Records Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
            <h5 className="text-sm font-medium text-gray-900">DNS Records</h5>
            <a
              href="https://resend.com/docs/knowledge-base/namecheap"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button
                variant="ghost"
                size="sm"
                className="text-gray-600 hover:text-gray-900 hover:bg-gray-100 h-8"
              >
                <HelpCircle className="size-4 mr-1.5" />
                How to add records
                <ExternalLink className="size-3 ml-1.5" />
              </Button>
            </a>
          </div>

          {/* Records Table */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-2.5 w-16">
                    Type
                  </th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-2.5">
                    Host
                  </th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-2.5">
                    Value
                  </th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-2.5 w-16">
                    TTL
                  </th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-2.5 w-20">
                    Priority
                  </th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-2.5 w-24">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white">
                {domain.dns_records.map((record, idx) => (
                  <DNSRecordTableRow
                    key={`${domain.id}-${record.type}-${idx}`}
                    record={record}
                    domainId={domain.id}
                    index={idx}
                    onCopy={onCopy}
                    copiedField={copiedField}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer note */}
          <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
            <div className="flex items-start gap-2 text-xs text-gray-500">
              <Info className="size-3.5 shrink-0 mt-0.5" />
              <span>
                DNS changes can take up to 48 hours to propagate. Click Verify
                once you&apos;ve added all the records.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Verified state - show sender email */}
      {isVerified && (
        <div className="border-t border-gray-200 p-4 bg-green-50">
          <div className="flex items-center gap-2 text-sm text-green-700">
            <CheckCircle2 className="size-4" />
            <span>
              Emails will be sent from:{" "}
              <span className="font-medium">
                {domain.from_name
                  ? `${domain.from_name} <${domain.from_email}>`
                  : domain.from_email}
              </span>
            </span>
          </div>
        </div>
      )}

      {/* Failed state */}
      {isFailed && (
        <div className="border-t border-gray-200 p-4 bg-red-50">
          <div className="flex items-center gap-2 text-sm text-red-700">
            <XCircle className="size-4" />
            <span>
              Verification failed. Please check your DNS records and try again.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// DNS Record Table Row Component
// ============================================================================

interface DNSRecordTableRowProps {
  record: EmailDNSRecord;
  domainId: string;
  index: number;
  onCopy: (text: string, fieldId: string) => void;
  copiedField: string | null;
}

function DNSRecordTableRow({
  record,
  domainId,
  index,
  onCopy,
  copiedField,
}: DNSRecordTableRowProps) {
  const nameFieldId = `${domainId}-${record.type}-${index}-name`;
  const valueFieldId = `${domainId}-${record.type}-${index}-value`;

  const isRecordVerified = record.status === "verified";

  return (
    <tr className="border-b border-gray-100 last:border-b-0 hover:bg-gray-50">
      {/* Type */}
      <td className="px-4 py-3">
        <span className="text-sm font-medium text-gray-700">{record.type}</span>
      </td>

      {/* Host */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <code className="text-sm text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
            {record.name}
          </code>
          {isRecordVerified && (
            <Check className="size-4 text-green-600 shrink-0" />
          )}
          <Button
            variant="ghost"
            size="icon"
            className="size-6 shrink-0 text-gray-400 hover:text-gray-700 hover:bg-gray-100"
            onClick={() => onCopy(record.name, nameFieldId)}
          >
            {copiedField === nameFieldId ? (
              <Check className="size-3 text-green-600" />
            ) : (
              <Copy className="size-3" />
            )}
          </Button>
        </div>
      </td>

      {/* Value */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <code className="text-sm text-gray-600 bg-gray-100 px-2 py-0.5 rounded truncate max-w-[250px]">
            {record.value}
          </code>
          <Button
            variant="ghost"
            size="icon"
            className="size-6 shrink-0 text-gray-400 hover:text-gray-700 hover:bg-gray-100"
            onClick={() => onCopy(record.value, valueFieldId)}
          >
            {copiedField === valueFieldId ? (
              <Check className="size-3 text-green-600" />
            ) : (
              <Copy className="size-3" />
            )}
          </Button>
        </div>
      </td>

      {/* TTL */}
      <td className="px-4 py-3">
        <span className="text-sm text-gray-500">{record.ttl || "Auto"}</span>
      </td>

      {/* Priority */}
      <td className="px-4 py-3">
        <span className="text-sm text-gray-500">
          {record.priority !== undefined ? record.priority : "-"}
        </span>
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <RecordStatusBadge status={record.status} />
      </td>
    </tr>
  );
}

// ============================================================================
// Record Status Badge Component
// ============================================================================

interface RecordStatusBadgeProps {
  status: "pending" | "verified" | "failed";
}

function RecordStatusBadge({ status }: RecordStatusBadgeProps) {
  switch (status) {
    case "verified":
      return (
        <Badge className="bg-green-100 text-green-700 border-0 hover:bg-green-100 text-xs">
          Verified
        </Badge>
      );
    case "failed":
      return (
        <Badge className="bg-red-100 text-red-700 border-0 hover:bg-red-100 text-xs">
          Failed
        </Badge>
      );
    default:
      return (
        <Badge className="bg-gray-100 text-gray-600 border-0 hover:bg-gray-100 text-xs">
          Not Started
        </Badge>
      );
  }
}
