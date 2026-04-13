import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

interface MonetizationToggleProps {
  isEnabled: boolean;
  onToggle: (checked: boolean) => void;
  disabled?: boolean;
}

/**
 * Toggle switch card for enabling/disabling monetization
 * Only updates local state - parent save handler calls API
 */
export function MonetizationToggle({
  isEnabled,
  onToggle,
  disabled = false,
}: MonetizationToggleProps) {
  return (
    <Card className="border-2">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="monetization-toggle" className="text-base">
              Enable Monetization
            </Label>
            <p className="text-sm text-muted-foreground">
              Charge visitors to access this persona
            </p>
          </div>
          <Switch
            id="monetization-toggle"
            checked={isEnabled}
            onCheckedChange={onToggle}
            disabled={disabled}
          />
        </div>
      </CardContent>
    </Card>
  );
}
