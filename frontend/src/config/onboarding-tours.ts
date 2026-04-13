import { Tour } from "nextstepjs";
import {
  Target,
  BookOpen,
  ArrowRight,
  Mic,
  MicVocal,
  Sparkles,
  User,
  PartyPopper,
  Rocket,
  Lightbulb,
} from "lucide-react";
import { createElement } from "react";

/**
 * First-Time User Onboarding Tours
 * Progressive onboarding flow: Knowledge → Voice Clone → Persona Creation
 */

/**
 * Step 1: Knowledge Library Onboarding
 * Guides users to add their first knowledge source
 */
export const knowledgeOnboardingTour: Tour = {
  tour: "onboarding-knowledge",
  steps: [
    {
      icon: createElement(Target, { size: 20 }),
      title: "Setup Wizard: Step 1 of 3",
      content:
        "Welcome to the persona creation wizard! Let's build your first AI clone together. First step: Add knowledge sources so your AI knows what to talk about.",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(BookOpen, { size: 20 }),
      title: "Add Your Knowledge Base",
      content:
        "Your AI needs knowledge to answer questions intelligently. Import from LinkedIn, Twitter, websites, or upload PDFs, audio, and video files. You can add more sources later!",
      selector: "#knowledge-source-grid",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(ArrowRight, { size: 20 }),
      title: "Ready for Next Step?",
      content:
        "You can add a source now or skip to continue. Don't worry - you can always add knowledge sources later from this page. Click 'Finish' when ready to move to Voice Cloning!",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
  ],
};

/**
 * Step 2: Voice Clone Onboarding
 * Guides users to create their first voice clone
 */
export const voiceCloneOnboardingTour: Tour = {
  tour: "onboarding-voice-clone",
  steps: [
    {
      icon: createElement(Mic, { size: 20 }),
      title: "Setup Wizard: Step 2 of 3",
      content:
        "Great progress! Now let's make your AI sound like you. Voice cloning creates a natural, personalized experience for your visitors.",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(MicVocal, { size: 20 }),
      title: "Clone Your Voice",
      content:
        "Record your voice directly in the browser or upload an audio file. This is optional - you can skip and use a default voice, or add it later!",
      selector: "#voice-clone-section",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(ArrowRight, { size: 20 }),
      title: "Almost There!",
      content:
        "Voice cloning is optional but makes your AI feel more personal. Click 'Finish' to move to the final step: Creating your persona!",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
  ],
};

/**
 * Step 3: Persona Creation Onboarding
 * Guides users to create their first persona with knowledge and voice
 */
export const personaOnboardingTour: Tour = {
  tour: "onboarding-persona",
  steps: [
    {
      icon: createElement(Sparkles, { size: 20 }),
      title: "Setup Wizard: Step 3 of 3",
      content:
        "Final step! Now let's bring it all together by creating your AI persona. This will combine your knowledge and voice into a complete AI clone.",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(User, { size: 20 }),
      title: "What's a Persona?",
      content:
        "A persona is your AI clone with a specific purpose. For example: 'Tech Advisor' for technical Q&A or 'Career Mentor' for career advice. You can create multiple personas for different topics!",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(Target, { size: 20 }),
      title: "Create Your First Persona",
      content:
        "Click the 'New Persona' button below to open the creation wizard. We'll guide you through each field step-by-step!",
      selector: "#create-persona-button",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(BookOpen, { size: 20 }),
      title: "Follow the In-Dialog Guide",
      content:
        "Once you click 'New Persona', a detailed wizard will open with step-by-step guidance through all 3 steps: Basic Info, Chat Behavior, and Knowledge Selection. Let's do it!",
      side: "bottom",
      showControls: true,
      showSkip: false,
    },
  ],
};

/**
 * Final completion tour
 * Shows after user completes all onboarding steps
 */
export const onboardingCompleteTour: Tour = {
  tour: "onboarding-complete",
  steps: [
    {
      icon: createElement(PartyPopper, { size: 20 }),
      title: "Congratulations!",
      content:
        "You've successfully set up your AI clone! Your persona is ready to chat with visitors on your public page.",
      side: "bottom",
      showControls: true,
      showSkip: false,
    },
    {
      icon: createElement(Rocket, { size: 20 }),
      title: "What's Next?",
      content:
        "You can now:\n• Add more knowledge sources\n• Create additional personas for different topics\n• Get your embed code to add the chat widget to your website\n• Share your public profile link",
      side: "bottom",
      showControls: true,
      showSkip: false,
    },
    {
      icon: createElement(Lightbulb, { size: 20 }),
      title: "Pro Tips",
      content:
        "• Create multiple personas for different expertise areas\n• Keep adding knowledge sources to make your AI smarter\n• Check the Conversations page to see what people are asking\n• Customize your widget appearance in the Widgets section",
      side: "bottom",
      showControls: true,
      showSkip: false,
    },
  ],
};

/**
 * All onboarding tours combined
 */
export const onboardingTours: Tour[] = [
  knowledgeOnboardingTour,
  voiceCloneOnboardingTour,
  personaOnboardingTour,
  onboardingCompleteTour,
];
