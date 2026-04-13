"use client";

import { Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

export interface DNSRecordDisplayProps {
  label: string;
  type: string;
  name: string;
  value: string;
  domainId: string;
  fieldPrefix: string;
  handleCopy: (text: string, fieldId: string) => Promise<void>;
  copiedField: string | null;
}

export function DNSRecordDisplay({
  label,
  type,
  name,
  value,
  domainId,
  fieldPrefix,
  handleCopy,
  copiedField,
}: DNSRecordDisplayProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-center gap-2 mb-2">
        <Badge variant="outline" className="text-[10px] font-mono">
          {type}
        </Badge>
        <span className="text-xs font-medium text-slate-700">{label}</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {/* Name field */}
        <div>
          <Label className="text-[10px] text-slate-500 uppercase tracking-wider">
            Name / Host
          </Label>
          <div className="mt-1 flex items-center gap-1.5">
            <code className="flex-1 bg-slate-100 px-2 py-1.5 rounded text-xs font-mono truncate">
              {name}
            </code>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 shrink-0"
              onClick={() =>
                handleCopy(name, `${domainId}-${fieldPrefix}-name`)
              }
            >
              {copiedField === `${domainId}-${fieldPrefix}-name` ? (
                <Check className="size-3.5 text-green-600" />
              ) : (
                <Copy className="size-3.5" />
              )}
            </Button>
          </div>
        </div>

        {/* Value field */}
        <div>
          <Label className="text-[10px] text-slate-500 uppercase tracking-wider">
            Value / Points to
          </Label>
          <div className="mt-1 flex items-center gap-1.5">
            <code className="flex-1 bg-slate-100 px-2 py-1.5 rounded text-xs font-mono truncate">
              {value}
            </code>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 shrink-0"
              onClick={() =>
                handleCopy(value, `${domainId}-${fieldPrefix}-value`)
              }
            >
              {copiedField === `${domainId}-${fieldPrefix}-value` ? (
                <Check className="size-3.5 text-green-600" />
              ) : (
                <Copy className="size-3.5" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
