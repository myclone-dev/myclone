import { Crown, Check, Settings } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { IntegrationConfig } from "@/lib/queries/integrations";

interface IntegrationCardProps {
  integration: IntegrationConfig;
  isLocked: boolean;
  Icon: React.ComponentType<{
    className?: string;
    style?: React.CSSProperties;
  }>;
  onClick?: () => void;
}

export function IntegrationCard({
  integration,
  isLocked,
  Icon,
  onClick,
}: IntegrationCardProps) {
  const isComingSoon = integration.comingSoon;

  return (
    <Card className={isLocked ? "opacity-75" : ""}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div
              className={`flex size-16 shrink-0 items-center justify-center rounded-lg bg-slate-100 ${
                isComingSoon ? "opacity-50" : ""
              }`}
            >
              <Icon className="size-10" style={{ color: integration.color }} />
            </div>
            <div>
              <CardTitle className="flex items-center gap-2">
                <span className={isComingSoon ? "opacity-50" : ""}>
                  {integration.name}
                </span>
                {integration.comingSoon ? (
                  <Badge
                    variant="outline"
                    className="gap-1 bg-blue-50 text-blue-700 border-blue-200"
                  >
                    Coming Soon
                  </Badge>
                ) : (
                  isLocked && (
                    <Badge variant="secondary" className="gap-1">
                      <Crown className="size-3" />
                      Enterprise
                    </Badge>
                  )
                )}
              </CardTitle>
              <CardDescription
                className={`mt-1 ${isComingSoon ? "opacity-50" : ""}`}
              >
                {integration.description}
              </CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className={`space-y-4 ${isComingSoon ? "opacity-50" : ""}`}>
          {/* Features */}
          <div>
            <h4 className="mb-2 text-sm font-medium">Features:</h4>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {integration.features.map((feature) => (
                <li key={feature} className="flex items-center gap-2">
                  <Check className="size-4 text-green-600" />
                  {feature}
                </li>
              ))}
            </ul>
          </div>

          {/* Configure Button */}
          {onClick && !isLocked && !integration.comingSoon && (
            <Button
              onClick={onClick}
              className="w-full gap-2"
              variant="outline"
            >
              <Settings className="size-4" />
              Configure
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
