import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function VoiceCloneInstructions() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>How It Works</CardTitle>
        <CardDescription>
          Follow these steps to create your personalized voice clone
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3 list-decimal list-inside text-sm text-slate-600">
          <li>
            Record your voice or upload a pre-recorded audio file (minimum 30
            seconds)
          </li>
          <li>We&apos;ll process your voice using advanced AI voice cloning</li>
          <li>Your AI clone will use this voice for natural conversations</li>
          <li>The voice clone can express emotions and speak naturally</li>
        </ol>
      </CardContent>
    </Card>
  );
}
