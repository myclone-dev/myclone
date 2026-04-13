import { ArrowLeft, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { VoiceFileUpload } from "@/components/voice-clone/VoiceFileUpload";

interface VoiceCloneUploadStepProps {
  onBack: () => void;
  onComplete: (file: File, customName?: string, language?: string) => void;
  isSubmitting?: boolean;
  /** Default name to show in the name field */
  defaultName?: string;
}

export function VoiceCloneUploadStep({
  onBack,
  onComplete,
  isSubmitting,
  defaultName = "",
}: VoiceCloneUploadStepProps) {
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
          Upload a clear audio file of your voice. The file must be at least 10
          seconds long for the best voice clone quality.
        </AlertDescription>
      </Alert>

      <VoiceFileUpload
        onFileComplete={onComplete}
        isSubmitting={isSubmitting}
        defaultName={defaultName}
      />
    </div>
  );
}
