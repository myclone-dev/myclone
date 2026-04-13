"use client";

import {
  Globe,
  Trash2,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  ArrowRight,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { CustomDomainResponse } from "@/lib/queries/users";
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
import { DNSRecordDisplay } from "./DNSRecordDisplay";

export interface DomainCardProps {
  domain: CustomDomainResponse;
  getStatusBadge: (domain: CustomDomainResponse) => React.ReactNode;
  handleVerify: (domainId: string, domainName: string) => Promise<void>;
  handleDelete: (domainId: string, domainName: string) => Promise<void>;
  handleCopy: (text: string, fieldId: string) => Promise<void>;
  onRefresh: () => void;
  copiedField: string | null;
  verifyMutation: { isPending: boolean };
  deleteMutation: { isPending: boolean };
}

export function DomainCard({
  domain,
  getStatusBadge,
  handleVerify,
  handleDelete,
  handleCopy,
  onRefresh,
  copiedField,
  verifyMutation,
  deleteMutation,
}: DomainCardProps) {
  // Display active only when backend marks active AND verified & SSL are ready
  const isActive =
    domain.status === "active" &&
    domain.verified === true &&
    domain.ssl_ready === true;

  // Check if domain is verified but pending SSL/DNS activation
  const isPendingActivation = domain.status === "verified" && !domain.ssl_ready;

  return (
    <div
      className={`rounded-xl overflow-hidden ${
        isActive
          ? "border border-green-300 bg-green-50/50 shadow-sm"
          : isPendingActivation
            ? "border border-blue-300 bg-blue-50/50 shadow-sm"
            : "border border-yellow-bright/40 bg-yellow-light/30 shadow-sm"
      }`}
    >
      {/* Domain Header */}
      <div className="p-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div
            className={`flex size-10 shrink-0 items-center justify-center rounded-full ${
              isActive
                ? "bg-green-100 ring-2 ring-green-200"
                : isPendingActivation
                  ? "bg-blue-100 ring-2 ring-blue-200"
                  : "bg-yellow-bright ring-2 ring-yellow-bright/50"
            }`}
          >
            <Globe
              className={`size-5 ${isActive ? "text-green-600" : isPendingActivation ? "text-blue-600" : "text-gray-900"}`}
            />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h5 className="text-sm font-semibold text-slate-900 truncate">
                {domain.domain}
              </h5>
              {getStatusBadge(domain)}
            </div>
            {isActive ? (
              <a
                href={`https://${domain.domain}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-xs text-green-600 hover:text-green-700 transition-colors"
              >
                Visit your domain
                <ExternalLink className="size-3" />
              </a>
            ) : isPendingActivation ? (
              <p className="text-xs text-blue-600 mt-1 flex items-start gap-1">
                <Info className="size-3 mt-0.5 shrink-0" />
                Verifying DNS and provisioning SSL... This may take a few
                minutes.
              </p>
            ) : (
              <p className="text-xs text-slate-500 mt-1">
                Added {new Date(domain.created_at).toLocaleDateString()}
              </p>
            )}
            {domain.last_error && domain.status === "failed" && (
              <p className="text-xs text-red-600 mt-1 flex items-start gap-1">
                <AlertCircle className="size-3 mt-0.5 shrink-0" />
                {domain.last_error}
              </p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          {!isActive && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleVerify(domain.id, domain.domain)}
              disabled={verifyMutation.isPending}
              className="h-8"
            >
              <RefreshCw
                className={`size-3.5 mr-1.5 ${verifyMutation.isPending ? "animate-spin" : ""}`}
              />
              Verify
            </Button>
          )}
          {/* Refresh Status - always available */}
          <Button
            variant="ghost"
            size="sm"
            className="text-slate-500 hover:text-slate-700 h-8"
            onClick={onRefresh}
          >
            <RefreshCw className="size-3.5 mr-1.5" />
            Refresh
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="text-slate-500 hover:text-red-600 hover:bg-red-50 h-8 w-8 p-0"
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="size-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Remove {domain.domain}?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will remove the domain from your account. Your clone will
                  no longer be accessible at this domain.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => handleDelete(domain.id, domain.domain)}
                  className="bg-red-600 hover:bg-red-700"
                >
                  Yes, Remove Domain
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* DNS Records - show when not active */}
      {!isActive && (domain.verification_record || domain.routing_record) && (
        <div className="border-t border-slate-100 bg-slate-50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <ArrowRight className="size-4 text-amber-500" />
            <span className="text-xs font-medium text-slate-700">
              Add these DNS records at your domain registrar:
            </span>
          </div>

          <div className="space-y-3">
            {/* Verification Record */}
            {domain.verification_record && (
              <DNSRecordDisplay
                label="Step 1: Verification Record"
                type="TXT"
                name={domain.verification_record.name}
                value={domain.verification_record.value}
                domainId={domain.id}
                fieldPrefix="txt"
                handleCopy={handleCopy}
                copiedField={copiedField}
              />
            )}

            {/* Routing Record */}
            {domain.routing_record && (
              <DNSRecordDisplay
                label={`Step 2: Routing Record`}
                type={domain.routing_record.type}
                name={domain.routing_record.name}
                value={domain.routing_record.value}
                domainId={domain.id}
                fieldPrefix="route"
                handleCopy={handleCopy}
                copiedField={copiedField}
              />
            )}

            {/* Optional additional routing records (e.g., AAAA for apex) */}
            {Array.isArray(domain.additional_routing_records) &&
              domain.additional_routing_records?.length > 0 && (
                <div className="space-y-2">
                  {domain.additional_routing_records.map((rec, idx) => (
                    <DNSRecordDisplay
                      key={`${domain.id}-extra-${idx}`}
                      label={
                        rec.type === "AAAA"
                          ? "Optional: IPv6 Routing Record"
                          : "Optional: Additional Routing Record"
                      }
                      type={rec.type}
                      name={rec.name}
                      value={rec.value}
                      domainId={domain.id}
                      fieldPrefix={`extra-${idx}`}
                      handleCopy={handleCopy}
                      copiedField={copiedField}
                    />
                  ))}
                </div>
              )}
          </div>

          <p className="mt-3 text-[11px] text-slate-500 flex items-start gap-1.5">
            <Info className="size-3 mt-0.5 shrink-0" />
            DNS changes can take up to 48 hours to propagate. Click
            &quot;Verify&quot; once you&apos;ve added the records.
          </p>
        </div>
      )}
    </div>
  );
}
