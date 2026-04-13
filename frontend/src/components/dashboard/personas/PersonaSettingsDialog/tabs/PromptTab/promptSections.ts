import {
  FileText,
  Target,
  MessageSquare,
  Users,
  Zap,
  Code,
  MessagesSquare,
  Sparkles,
  ShieldCheck,
} from "lucide-react";
import type { PromptSection } from "../../types";

/**
 * Basic Prompt Sections (4 core sections)
 */
export const basicPromptSections: PromptSection[] = [
  {
    id: "introduction",
    label: "Introduction",
    icon: FileText,
    placeholder: "Introduce yourself and your expertise...",
    description: "Brief introduction about who you are",
  },
  {
    id: "area_of_expertise",
    label: "Area of Expertise",
    icon: Target,
    placeholder: "e.g., Machine Learning, Product Management, Sales...",
    description: "What topics you specialize in",
  },
  {
    id: "chat_objective",
    label: "Chat Objective",
    icon: MessageSquare,
    placeholder: "What should users achieve from conversations with you?",
    description: "Primary goal of conversations",
  },
  {
    id: "target_audience",
    label: "Target Audience",
    icon: Users,
    placeholder: "e.g., Developers, Students, Entrepreneurs...",
    description: "Who are you talking to",
  },
];

/**
 * Advanced Prompt Sections (5 advanced sections)
 */
export const advancedPromptSections: PromptSection[] = [
  {
    id: "thinking_style",
    label: "Thinking Style",
    icon: Zap,
    placeholder: "How should the AI reason and communicate?",
    description: "Reasoning and communication approach",
    infoTitle: "Thinking Style",
    infoDescription:
      "Describe how the AI should reason, approach problems, and communicate.",
  },
  {
    id: "objective_response",
    label: "Response Strategy",
    icon: Code,
    placeholder: "How should responses be structured?",
    description: "Response formatting strategy",
    infoTitle: "Response Strategy",
    infoDescription: "Define how the AI structures and formats its responses.",
  },
  {
    id: "conversation_flow",
    label: "Conversation Flow",
    icon: MessagesSquare,
    placeholder: "How should conversations progress?",
    description: "Conversation progression logic",
    infoTitle: "Conversation Flow",
    infoDescription: "Guide how conversations should naturally progress.",
  },
  {
    id: "example_responses",
    label: "Example Responses",
    icon: Sparkles,
    placeholder: "Provide example responses to guide style...",
    description: "Sample responses for reference",
    infoTitle: "Example Responses",
    infoDescription:
      "Provide sample responses to demonstrate your desired communication style.",
  },
  {
    id: "strict_guideline",
    label: "Guardrails",
    icon: ShieldCheck,
    placeholder: "Define boundaries and guidelines...",
    description: "Conversation boundaries and rules",
    infoTitle: "Guardrails",
    infoDescription:
      "Define boundaries and guidelines to keep conversations on track and appropriate.",
  },
];
