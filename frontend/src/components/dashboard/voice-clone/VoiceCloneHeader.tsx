import { Mic } from "lucide-react";

export function VoiceCloneHeader() {
  return (
    <div>
      <div className="flex items-center gap-2.5 sm:gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-orange-100 sm:size-12">
          <Mic className="size-5 text-ai-brown 600 sm:size-6" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold text-slate-900 sm:text-2xl">
            Voice Clone
          </h1>
          <p className="text-xs text-slate-600 sm:text-sm">
            Create a personalized AI voice clone for natural conversations
          </p>
        </div>
      </div>
    </div>
  );
}
