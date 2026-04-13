import { Sparkles } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

export function VoiceCloneProcessing() {
  return (
    <Card className="border-blue-200 bg-blue-50">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="flex size-8 items-center justify-center">
            <div className="size-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          </div>
          <div>
            <CardTitle className="text-blue-900">
              Creating Voice Clone...
            </CardTitle>
            <CardDescription className="text-blue-700">
              Please wait while we process your voice
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Alert className="border-blue-300 bg-blue-100">
          <Sparkles className="size-4 text-blue-600" />
          <AlertDescription className="text-blue-900">
            Processing your audio file. This may take a few moments...
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
