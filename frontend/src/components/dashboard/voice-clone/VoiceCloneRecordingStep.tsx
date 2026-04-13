import { ArrowLeft, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { VoiceRecordingScript } from "@/components/voice-clone/VoiceRecordingScript";

interface VoiceCloneRecordingStepProps {
  userName: string;
  userExpertise?: string;
  onBack: () => void;
  onComplete: (files: File[]) => void;
  isSubmitting?: boolean;
}

export function VoiceCloneRecordingStep({
  userName,
  userExpertise,
  onBack,
  onComplete,
  isSubmitting,
}: VoiceCloneRecordingStepProps) {
  return (
    <div className="space-y-6">
      <Button
        variant="ghost"
        onClick={onBack}
        className="gap-2 text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="size-4" />
        Back to options
      </Button>

      <Alert>
        <AlertCircle className="size-4" />
        <AlertDescription>
          Read the script naturally and clearly. Your recording must be at least
          10 seconds long for the best voice clone quality.
        </AlertDescription>
      </Alert>

      <VoiceRecordingScript
        onRecordingsComplete={onComplete}
        userName={userName}
        userExpertise={userExpertise || "helping others achieve their goals"}
        isSubmitting={isSubmitting}
      />
    </div>
  );
}
