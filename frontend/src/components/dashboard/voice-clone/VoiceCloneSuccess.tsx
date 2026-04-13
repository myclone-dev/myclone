import { useRouter } from "next/navigation";
import { CheckCircle2, Sparkles, ArrowRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

interface VoiceCloneSuccessProps {
  voiceName: string;
}

export function VoiceCloneSuccess({ voiceName }: VoiceCloneSuccessProps) {
  const router = useRouter();

  return (
    <Card className="border-yellow-bright bg-yellow-light">
      <CardHeader>
        <div className="flex items-center gap-3">
          <CheckCircle2 className="size-8 text-primary" />
          <div>
            <CardTitle className="text-foreground">
              Voice Clone Created Successfully!
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              {voiceName} is being processed and will be ready soon
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <Alert className="border-yellow-bright bg-peach-cream">
            <Sparkles className="size-4 text-primary" />
            <AlertDescription className="text-foreground">
              <strong className="font-semibold">{voiceName}</strong> is being
              processed. This usually takes a few minutes. Your voice has been
              automatically applied to all your personas.
            </AlertDescription>
          </Alert>

          {/* Primary CTA */}
          <div className="rounded-lg border-2 border-yellow-bright bg-white p-4">
            <div className="mb-3">
              <h3 className="font-semibold text-foreground">
                Voice Applied to All Personas
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Your voice clone has been automatically assigned to all your
                personas for natural conversations with your audience.
              </p>
            </div>
            <Button
              onClick={() => router.push("/dashboard/personas")}
              className="w-full gap-2"
              size="lg"
            >
              Go to Personas
              <ArrowRight className="size-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
