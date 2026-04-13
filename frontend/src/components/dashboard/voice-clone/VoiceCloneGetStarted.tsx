import { Mic, FileAudio, CheckCircle2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface VoiceCloneGetStartedProps {
  onRecordClick: () => void;
  onUploadClick: () => void;
}

export function VoiceCloneGetStarted({
  onRecordClick,
  onUploadClick,
}: VoiceCloneGetStartedProps) {
  return (
    <>
      <Card id="get-started-section">
        <CardHeader>
          <CardTitle>Get Started</CardTitle>
          <CardDescription>
            Choose how you want to provide your voice sample
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button size="lg" onClick={onRecordClick} className="w-full gap-2">
            <Mic className="size-5" />
            Record Your Voice
          </Button>
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-muted-foreground">Or</span>
            </div>
          </div>
          <Button
            size="lg"
            variant="outline"
            onClick={onUploadClick}
            className="w-full gap-2"
          >
            <FileAudio className="size-5" />
            Upload Audio File
          </Button>
          <p className="text-xs text-muted-foreground text-center pt-2">
            Supported formats: WAV, MP3, M4A, FLAC (Max 10MB)
          </p>
        </CardContent>
      </Card>

      {/* Requirements */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Requirements</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm text-slate-600">
            <li className="flex items-start gap-2">
              <CheckCircle2 className="size-4 text-green-600 mt-0.5 shrink-0" />
              <span>Quiet environment with minimal background noise</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle2 className="size-4 text-green-600 mt-0.5 shrink-0" />
              <span>Clear audio with good quality</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle2 className="size-4 text-green-600 mt-0.5 shrink-0" />
              <span>Minimum 30 seconds duration</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle2 className="size-4 text-green-600 mt-0.5 shrink-0" />
              <span>Natural speaking pace and tone</span>
            </li>
          </ul>
        </CardContent>
      </Card>
    </>
  );
}
