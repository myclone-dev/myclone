import { Tour, Step } from "nextstepjs";
import {
  Hand,
  Zap,
  Users,
  BookOpen,
  MessageSquare,
  PartyPopper,
  FolderKanban,
  Wrench,
  Sparkles,
} from "lucide-react";
import { createElement } from "react";
import { onboardingTours } from "./onboarding-tours";
import { personaCreationTours } from "./persona-creation-tours";

/**
 * Dashboard onboarding tours
 * Comprehensive tours to guide users through the dashboard
 *
 * We have two versions of the dashboard welcome tour:
 * 1. Desktop version - includes sidebar navigation steps
 * 2. Mobile version - excludes sidebar steps (sidebar is hidden in a Sheet on mobile)
 */

// Common steps used in both desktop and mobile tours
const welcomeStep: Step = {
  icon: createElement(Hand, { size: 20 }),
  title: "Welcome to ConvoxAI!",
  content:
    "Let's take a quick tour to show you how to build and deploy your AI clone in minutes.",
  side: "bottom",
  showControls: true,
  showSkip: true,
};

const quickActionsStep: Step = {
  icon: createElement(Zap, { size: 20 }),
  title: "Quick Actions",
  content:
    "These shortcuts let you quickly add knowledge, create personas, get your embed code, or view your public page.",
  selector: "#quick-actions-card",
  side: "bottom",
  showControls: true,
  showSkip: true,
};

const personasSectionStep: Step = {
  icon: createElement(Users, { size: 20 }),
  title: "Your Personas",
  content:
    "Create multiple AI versions of yourself. Each persona can have unique knowledge, tone, and personality.",
  selector: "#personas-section",
  side: "top",
  showControls: true,
  showSkip: true,
};

const knowledgeStatsStep: Step = {
  icon: createElement(BookOpen, { size: 20 }),
  title: "Knowledge Library Stats",
  content:
    "View your connected data sources. Add LinkedIn profiles, Twitter feeds, websites, PDFs, audio, and video files.",
  selector: "#knowledge-stats-card",
  side: "top",
  showControls: true,
  showSkip: true,
};

const conversationsStatsStep: Step = {
  icon: createElement(MessageSquare, { size: 20 }),
  title: "Conversations",
  content:
    "Track all interactions with your AI clone. See text chats and voice conversations from visitors.",
  selector: "#conversations-stats-card",
  side: "top",
  showControls: true,
  showSkip: true,
};

const completionStep: Step = {
  icon: createElement(PartyPopper, { size: 20 }),
  title: "You're All Set!",
  content:
    "Now you're ready! Add your knowledge sources, create your first persona, and share your AI clone with the world.",
  side: "bottom",
  showControls: true,
  showSkip: false,
};

// Desktop-only sidebar steps
const sidebarSteps: Step[] = [
  {
    icon: createElement(FolderKanban, { size: 20 }),
    title: "Sidebar Navigation",
    content:
      "Use this sidebar to navigate between different sections. Access Overview, Knowledge Library, Personas, Conversations, and Widgets.",
    selector: "#sidebar-navigation",
    side: "right",
    showControls: true,
    showSkip: true,
  },
  {
    icon: createElement(BookOpen, { size: 20 }),
    title: "Knowledge Library",
    content:
      "Add knowledge sources to train your AI. Import from LinkedIn, Twitter, websites, or upload PDFs, audio, and video files.",
    selector: "#sidebar-knowledge-library",
    side: "right",
    showControls: true,
    showSkip: true,
  },
  {
    icon: createElement(Users, { size: 20 }),
    title: "Manage Personas",
    content:
      "Create and customize your AI personas. Assign different knowledge sources, adjust tone, and configure voice settings.",
    selector: "#sidebar-personas",
    side: "right",
    showControls: true,
    showSkip: true,
  },
  {
    icon: createElement(MessageSquare, { size: 20 }),
    title: "View Conversations",
    content:
      "Review all conversations with your AI clone. Filter by persona, view transcripts, and see visitor questions.",
    selector: "#sidebar-conversations",
    side: "right",
    showControls: true,
    showSkip: true,
  },
  {
    icon: createElement(Wrench, { size: 20 }),
    title: "Get Embed Code",
    content:
      "Generate your widget embed code. Customize colors, position, and features, then copy-paste onto any website.",
    selector: "#sidebar-widgets",
    side: "right",
    showControls: true,
    showSkip: true,
  },
];

// Mobile-only step explaining how to access navigation
const mobileNavigationStep: Step = {
  icon: createElement(FolderKanban, { size: 20 }),
  title: "Navigation Menu",
  content:
    "Tap the menu icon in the top-left corner to access all sections: Knowledge Library, Personas, Conversations, Widgets, and more.",
  side: "bottom",
  showControls: true,
  showSkip: true,
};

// Desktop tour - includes sidebar navigation steps
const dashboardWelcomeTourDesktop: Tour = {
  tour: "dashboard-welcome",
  steps: [
    welcomeStep,
    quickActionsStep,
    personasSectionStep,
    knowledgeStatsStep,
    conversationsStatsStep,
    ...sidebarSteps,
    completionStep,
  ],
};

// Mobile tour - excludes sidebar steps, adds mobile-specific navigation guidance
const dashboardWelcomeTourMobile: Tour = {
  tour: "dashboard-welcome-mobile",
  steps: [
    welcomeStep,
    quickActionsStep,
    personasSectionStep,
    knowledgeStatsStep,
    conversationsStatsStep,
    mobileNavigationStep,
    completionStep,
  ],
};

/**
 * Conversation Summary Feature Tour
 * Highlights the AI-powered conversation summary feature
 */
const conversationSummaryFeatureTour: Tour = {
  tour: "conversation-summary-feature",
  steps: [
    {
      icon: createElement(Sparkles, { size: 20 }),
      title: "New: AI-Powered Summaries",
      content:
        "We've added a powerful new feature! Click the 'Summary' button on any conversation to get an instant AI-generated summary with key insights and sentiment analysis.",
      side: "bottom",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(MessageSquare, { size: 20 }),
      title: "Quick Conversation Insights",
      content:
        "Each summary includes: conversation highlights, key topics discussed, sentiment analysis, and main questions asked. Perfect for quickly understanding long conversations!",
      selector: "#conversation-summary-button",
      side: "left",
      showControls: true,
      showSkip: true,
    },
    {
      icon: createElement(PartyPopper, { size: 20 }),
      title: "Try It Now!",
      content:
        "Click the 'Summary' button below to see it in action. The AI will analyze the entire conversation and provide actionable insights in seconds.",
      selector: "#conversation-summary-button",
      side: "left",
      showControls: true,
      showSkip: false,
    },
  ],
};

/**
 * All dashboard tours including onboarding and regular tours
 * Both desktop and mobile versions are included - the dashboard page
 * will choose which one to start based on viewport width
 */
export const dashboardTours: Tour[] = [
  dashboardWelcomeTourDesktop,
  dashboardWelcomeTourMobile,
  conversationSummaryFeatureTour,
  ...onboardingTours,
  ...personaCreationTours,
];
