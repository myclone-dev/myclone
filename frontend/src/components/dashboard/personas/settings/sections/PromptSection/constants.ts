import {
  FileText,
  Target,
  MessageSquare,
  Users,
  Code,
  Zap,
  MessagesSquare,
  Sparkles,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export interface PromptFieldConfig {
  id: string;
  label: string;
  tooltip: string;
  placeholder: string;
  icon: LucideIcon;
  minHeight: string;
  isOptional?: boolean;
  docAnchor: string;
}

export const ESSENTIAL_FIELDS: PromptFieldConfig[] = [
  {
    id: "introduction",
    label: "What is your professional background?",
    tooltip:
      "Describe your professional background, experience, and credentials. This helps establish your persona's authority and expertise.",
    placeholder:
      "e.g., I'm a licensed real estate agent with 10+ years in luxury properties. Former architect with expertise in valuation and market analysis...",
    icon: FileText,
    minHeight: "100px",
    docAnchor: "field-introduction",
  },
  {
    id: "area_of_expertise",
    label: "What topics can your persona help with?",
    tooltip:
      "List your main areas of expertise. This helps your persona stay focused and provide better answers.",
    placeholder: "List your areas of expertise...",
    icon: Target,
    minHeight: "120px",
    docAnchor: "field-expertise",
  },
  {
    id: "chat_objective",
    label: "What should conversations achieve?",
    tooltip:
      "Define the main goal or outcome you want from conversations with your persona.",
    placeholder: "Describe the goal of conversations...",
    icon: MessageSquare,
    minHeight: "100px",
    docAnchor: "field-chat-objective",
  },
];

export const ADVANCED_FIELDS: PromptFieldConfig[] = [
  {
    id: "target_audience",
    label: "Who will chat with your persona?",
    tooltip:
      "Describe your target audience to help your persona adjust its communication style.",
    placeholder:
      "e.g., First-time entrepreneurs, enterprise executives, developers, students",
    icon: Users,
    minHeight: "80px",
    isOptional: true,
    docAnchor: "field-target-audience",
  },
  {
    id: "objective_response",
    label: "What example conversations demonstrate your approach?",
    tooltip:
      "Write 2-3 complete multi-turn dialogues showing different scenarios. Include realistic user questions and show how your persona should respond with follow-up questions.",
    placeholder: `Example Conversation 1: First-time buyer

User: I want to buy a home but don't know where to start.

Persona: Great! Let me ask a few questions first. What's your budget range?

User: Around $500k.

Persona: Perfect. And what neighborhoods are you considering?

---

Example Conversation 2: Investment inquiry...`,
    icon: Code,
    minHeight: "120px",
    isOptional: true,
    docAnchor: "field-example-conversations",
  },
  {
    id: "thinking_style",
    label: "How should your persona approach problems?",
    tooltip: "Describe the reasoning style and problem-solving approach.",
    placeholder:
      "e.g., Analytical and data-driven, creative and innovative, practical and solution-focused...",
    icon: Zap,
    minHeight: "80px",
    isOptional: true,
    docAnchor: "field-thinking-style",
  },
  {
    id: "conversation_flow",
    label: "How should conversations progress?",
    tooltip: "Define how your persona should guide the conversation flow.",
    placeholder:
      "e.g., Start with questions to understand context, then provide tailored advice...",
    icon: MessagesSquare,
    minHeight: "80px",
    isOptional: true,
    docAnchor: "field-conversation-flow",
  },
  {
    id: "example_responses",
    label: "What response patterns define your style?",
    tooltip:
      "Define 3-5 specific techniques your persona uses. Give each pattern a name and show 2-3 short example quotes.",
    placeholder: `Pattern 1: Always cite data
- 'Market average is $1,200/sq ft, up 8% YoY'
- 'Your budget gets you 2-bed in this area'

Pattern 2: Present trade-offs
- 'Option A = lower price but needs work'
- 'Option B = move-in ready but higher cost'

Pattern 3: End with action items...`,
    icon: Sparkles,
    minHeight: "100px",
    isOptional: true,
    docAnchor: "field-example-responses",
  },
  {
    id: "strict_guideline",
    label: "What should your persona avoid or always do?",
    tooltip:
      "Set boundaries and rules for what the persona should never do or always follow.",
    placeholder:
      "e.g., Never provide medical or legal advice, Always ask clarifying questions before giving recommendations...",
    icon: ShieldCheck,
    minHeight: "100px",
    isOptional: true,
    docAnchor: "field-guardrails",
  },
];

// Documentation URL mapping
export const FIELD_URL_MAP: Record<string, string> = {
  "field-introduction":
    "/docs/user-guide/prompt-configuration/about-your-persona#field-introduction",
  "field-expertise":
    "/docs/user-guide/prompt-configuration/about-your-persona#field-expertise",
  "field-chat-objective":
    "/docs/user-guide/prompt-configuration/goals-and-audience#field-chat-objective",
  "field-target-audience":
    "/docs/user-guide/prompt-configuration/goals-and-audience#field-target-audience",
  "field-example-conversations":
    "/docs/user-guide/prompt-configuration/goals-and-audience#field-example-conversations",
  "field-thinking-style":
    "/docs/user-guide/prompt-configuration/communication-style#field-thinking-style",
  "field-conversation-flow":
    "/docs/user-guide/prompt-configuration/communication-style#field-conversation-flow",
  "field-example-responses":
    "/docs/user-guide/prompt-configuration/examples-and-guardrails#field-example-responses",
  "field-guardrails":
    "/docs/user-guide/prompt-configuration/examples-and-guardrails#field-guardrails",
  "professional-examples":
    "/docs/user-guide/prompt-configuration/professional-examples",
};
