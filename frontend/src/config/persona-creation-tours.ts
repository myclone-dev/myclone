import { Tour } from "nextstepjs";
import {
  Pencil,
  FileText,
  Link,
  Briefcase,
  Target,
  FileType,
  ArrowRight,
  MessageSquare,
  Users,
  Settings,
  Sparkles,
  BookOpen,
  Rocket,
} from "lucide-react";
import { createElement } from "react";

/**
 * Persona Creation Dialog Tours
 * Guides users through the 3-step persona creation process
 */

/**
 * Step 1: Basic Information
 * Guides through persona name, role, expertise, and description fields
 */
export const personaCreationStep1Tour: Tour = {
  tour: "persona-creation-step-1",
  steps: [
    {
      icon: createElement(Pencil, { size: 20 }),
      title: "Let's Create Your Persona!",
      content:
        "We'll guide you through filling in your persona's basic information. This includes name, username, role, expertise, and description. Fill in each field as we go.",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(FileText, { size: 20 }),
      title: "Persona Name",
      content:
        "Give your AI persona a memorable name. This is what users will see when they interact with your clone. Example: 'Tech Advisor' or 'Career Mentor'.",
      selector: "#persona-name-field",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(Link, { size: 20 }),
      title: "Username (URL Identifier)",
      content:
        "This creates your unique URL. It's auto-generated from your persona name but you can customize it. Once set, it cannot be changed. Example: 'tech-advisor' → yoursite.com/tech-advisor",
      selector: "#persona-username-field",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(Briefcase, { size: 20 }),
      title: "Professional Role",
      content:
        "What's your professional title or role? This helps users understand your expertise. Example: 'AI Consultant', 'Senior Developer', or 'Business Coach'.",
      selector: "#persona-role-field",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(Target, { size: 20 }),
      title: "Areas of Expertise",
      content:
        "List your key areas of expertise separated by commas. This helps your AI focus on relevant topics. Example: 'Deep learning, NLP, Computer Vision' or 'React, TypeScript, Node.js'.",
      selector: "#persona-expertise-field",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(FileType, { size: 20 }),
      title: "Description (Optional)",
      content:
        "Add a detailed description about yourself or your AI persona. This is optional but helps users understand what your AI clone can help them with. Maximum 500 characters.",
      selector: "#persona-description-field",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(ArrowRight, { size: 20 }),
      title: "Ready for Chat Configuration?",
      content:
        "Great job! You've completed the basic information. Click 'Next: Configure Chat' in the dialog to continue to Step 2 where you'll define how your AI interacts with users.",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
  ],
};

/**
 * Step 2: Chat Configuration
 * Guides through chat objective and target audience
 */
export const personaCreationStep2Tour: Tour = {
  tour: "persona-creation-step-2",
  steps: [
    {
      icon: createElement(MessageSquare, { size: 20 }),
      title: "Configure Chat Behavior",
      content:
        "Now define how your persona should interact with users. Fill in the chat objective, target audience, and choose response settings. You can adjust these later.",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(Target, { size: 20 }),
      title: "Chat Objective (Required)",
      content:
        "What is the main goal of conversations with your AI? Be specific about what you want your AI to help users with. Example: 'Help users understand machine learning concepts' or 'Provide career guidance for software engineers'.",
      selector: "#chat-objective-field",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(Users, { size: 20 }),
      title: "Target Audience (Optional)",
      content:
        "Who is this persona designed to help? Defining your target audience helps your AI tailor responses appropriately. Example: 'ML beginners to intermediate practitioners' or 'Early-career developers'.",
      selector: "#target-audience-field",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(Settings, { size: 20 }),
      title: "Response Settings",
      content:
        "Customize how your AI responds. Choose Response Length (intelligent/concise/explanatory/custom) and Creativity Level (strict/adaptive/creative). These settings control the style and depth of responses.",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(ArrowRight, { size: 20 }),
      title: "Ready for Final Step?",
      content:
        "Excellent! Chat configuration is complete. Click 'Next: Select Knowledge' in the dialog to move to Step 3 where you'll choose your voice and knowledge sources.",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
  ],
};

/**
 * Step 3: Knowledge & Voice Selection
 * Guides through selecting voice clone and knowledge sources
 */
export const personaCreationStep3Tour: Tour = {
  tour: "persona-creation-step-3",
  steps: [
    {
      icon: createElement(Sparkles, { size: 20 }),
      title: "Final Step: Voice & Knowledge",
      content:
        "Select knowledge sources for your persona. Toggle the switches to enable/disable sources. When ready, click 'Create Persona' to finish!",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(BookOpen, { size: 20 }),
      title: "Knowledge Sources",
      content:
        "Toggle the switches to select which knowledge sources your persona can use. You can choose from LinkedIn, Twitter, websites, documents, and YouTube. Your persona will use these sources to answer questions intelligently.",
      selector: "#knowledge-sources-list",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(Rocket, { size: 20 }),
      title: "Create Your Persona!",
      content:
        "All set! Review your selections and click the 'Create Persona' button below to bring your AI clone to life. You can always edit these settings later from the persona settings page.",
      selector: "#create-persona-submit-button",
      side: "left",
      showControls: true,
      showSkip: false,
    },
  ],
};

/**
 * All persona creation dialog tours
 */
export const personaCreationTours: Tour[] = [
  personaCreationStep1Tour,
  personaCreationStep2Tour,
  personaCreationStep3Tour,
];
