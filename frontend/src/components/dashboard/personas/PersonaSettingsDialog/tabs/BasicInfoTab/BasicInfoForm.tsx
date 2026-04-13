"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { BasicInfoFormData, Persona } from "../../types";

interface BasicInfoFormProps {
  persona: Persona;
  basicInfo: BasicInfoFormData;
  onChange: (updates: Partial<BasicInfoFormData>) => void;
}

/**
 * Basic Info form fields
 * Username (disabled), Name, Role, Expertise, Description, Greeting Message
 */
export function BasicInfoForm({
  persona,
  basicInfo,
  onChange,
}: BasicInfoFormProps) {
  return (
    <div className="space-y-4 sm:space-y-6 max-w-5xl mx-auto">
      {/* Username (disabled) */}
      <div className="space-y-2">
        <Label htmlFor="persona_name" className="text-sm font-medium">
          Username
        </Label>
        <Input
          id="persona_name"
          value={persona.persona_name}
          disabled
          className="h-10 bg-muted/50 cursor-not-allowed"
        />
        <p className="text-xs text-muted-foreground">
          This is the unique username for your persona and cannot be changed.
        </p>
      </div>

      {/* Persona Name */}
      <div className="space-y-2">
        <Label htmlFor="name" className="text-sm font-medium">
          Persona Name
        </Label>
        <Input
          id="name"
          value={basicInfo.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="e.g., Tech Advisor"
          className="h-10"
        />
      </div>

      {/* Role */}
      <div className="space-y-2">
        <Label htmlFor="role" className="text-sm font-medium">
          Role
        </Label>
        <Input
          id="role"
          value={basicInfo.role}
          onChange={(e) => onChange({ role: e.target.value })}
          placeholder="e.g., Senior Software Engineer"
          className="h-10"
        />
      </div>

      {/* Expertise */}
      <div className="space-y-2">
        <Label htmlFor="expertise" className="text-sm font-medium">
          Expertise
        </Label>
        <Input
          id="expertise"
          value={basicInfo.expertise}
          onChange={(e) => onChange({ expertise: e.target.value })}
          placeholder="e.g., Deep learning, model training, Speech synthesis"
          maxLength={200}
          className="h-10"
        />
      </div>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="description" className="text-sm font-medium">
          Description
        </Label>
        <Textarea
          id="description"
          value={basicInfo.description}
          onChange={(e) => onChange({ description: e.target.value })}
          placeholder="Describe what this persona is about..."
          rows={4}
          className="resize-none min-h-[100px] max-h-48 overflow-y-auto border-slate-300 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-slate-100 [&::-webkit-scrollbar-thumb]:bg-slate-300 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-slate-400"
        />
      </div>

      {/* Greeting Message */}
      <div className="space-y-2">
        <Label htmlFor="greetingMessage" className="text-sm font-medium">
          Chat Greeting Message
        </Label>
        <Textarea
          id="greetingMessage"
          value={basicInfo.greetingMessage}
          onChange={(e) => onChange({ greetingMessage: e.target.value })}
          placeholder="e.g., Welcome! I'm excited to help you with your questions about AI and machine learning."
          rows={3}
          className="resize-none min-h-[80px] max-h-48 overflow-y-auto border-slate-300 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-slate-100 [&::-webkit-scrollbar-thumb]:bg-slate-300 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-slate-400"
        />
        <p className="text-xs text-muted-foreground">
          Customize the first message users hear when starting a conversation.
          Leave empty to use the default greeting.
        </p>
      </div>
    </div>
  );
}
