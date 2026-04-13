"use client";

import { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface UploadCardProps {
  title: string;
  description: string;
  icon: ReactNode;
  children: ReactNode;
  className?: string;
}

export function UploadCard({
  title,
  description,
  icon,
  children,
  className,
}: UploadCardProps) {
  return (
    <Card className={cn("p-6", className)}>
      <div className="mb-4 flex items-start gap-4">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-orange-100 text-ai-brown">
          {icon}
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
          <p className="mt-1 text-sm text-slate-600">{description}</p>
        </div>
      </div>
      {children}
    </Card>
  );
}
