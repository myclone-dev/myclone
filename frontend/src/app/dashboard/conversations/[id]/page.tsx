"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronUp, MessageSquare, ArrowLeft } from "lucide-react";
import { ConversationDetail } from "@/components/dashboard/conversations/ConversationDetail";
import { ConversationSummaryCard } from "@/components/dashboard/conversations/ConversationSummaryCard";
import { WorkflowSessionCard } from "@/components/dashboard/conversations/WorkflowSessionCard";
import { PageLoader } from "@/components/ui/page-loader";
import { Button } from "@/components/ui/button";
import { useUserMe } from "@/lib/queries/users";
import {
  useConversation,
  useConversationSummary,
} from "@/lib/queries/conversations";
import { useWorkflowSession } from "@/lib/queries/workflows";
import { isLeadEvaluationResult } from "@/lib/queries/workflows";

interface ConversationPageProps {
  params: Promise<{
    id: string;
  }>;
}

/**
 * Individual Conversation Page
 * View a specific conversation by ID
 *
 * Layout priority:
 * 1. Workflow Session Card (expanded) - Shows lead scoring for conversational workflows
 * 2. AI Summary (collapsed) - General conversation summary
 * 3. Conversation Transcript (collapsed) - Full message history
 */
export default function ConversationPage({ params }: ConversationPageProps) {
  const router = useRouter();
  const { data: user, isLoading } = useUserMe();
  // Unwrap the params promise using React.use()
  const { id: conversationId } = use(params);

  // Track whether conversation is expanded (collapsed by default when we have workflow data)
  const [conversationExpanded, setConversationExpanded] = useState(false);

  // Fetch conversation to get workflow_session_id
  const { data: conversation } = useConversation(conversationId);

  // Fetch conversation summary at page level (auth via cookies)
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
  } = useConversationSummary(conversationId);

  // Fetch workflow session by workflow_session_id (from conversation)
  // Only fetch if conversation has a workflow_session_id
  const {
    data: workflowSession,
    isLoading: sessionLoading,
    error: sessionError,
  } = useWorkflowSession(conversation?.workflow_session_id);

  const handleBack = () => {
    router.push("/dashboard/conversations");
  };

  if (isLoading || !user) {
    return <PageLoader />;
  }

  // Check if we have lead evaluation data (conversational workflow)
  const hasLeadData =
    workflowSession && isLeadEvaluationResult(workflowSession.result_data);

  // If we have lead data, conversation should be collapsed by default
  // Otherwise, show conversation expanded
  const showConversationCollapsed = hasLeadData && !conversationExpanded;

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-4">
      {/* Back Button - Always visible at top */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={handleBack}>
          <ArrowLeft className="size-4 mr-1" />
          Back to Conversations
        </Button>
      </div>

      {/* Workflow Session Card - Lead Scoring (expanded by default if available) */}
      {/* Only show if conversation has a workflow_session_id */}
      {conversation?.workflow_session_id && (
        <WorkflowSessionCard
          session={workflowSession || null}
          isLoading={sessionLoading}
          error={sessionError}
          defaultExpanded={true}
        />
      )}

      {/* AI Summary - Collapsed by default when we have lead data */}
      <ConversationSummaryCard
        summary={summary || null}
        isLoading={summaryLoading}
        error={summaryError}
        defaultExpanded={!hasLeadData}
      />

      {/* Conversation Transcript - Collapsible section */}
      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        {/* Collapsible Header */}
        <button
          onClick={() => setConversationExpanded(!conversationExpanded)}
          className="flex w-full items-center justify-between gap-3 p-3 sm:p-4 text-left transition-colors hover:bg-gray-50"
        >
          <div className="flex items-center gap-2">
            <MessageSquare className="size-5 text-gray-600" />
            <span className="text-sm font-semibold text-foreground sm:text-base">
              Conversation Transcript
            </span>
          </div>
          <div className="flex items-center gap-2">
            {showConversationCollapsed && (
              <span className="text-xs text-muted-foreground">
                Click to view messages
              </span>
            )}
            {conversationExpanded ? (
              <ChevronUp className="size-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="size-4 text-muted-foreground" />
            )}
          </div>
        </button>

        {/* Conversation Content - Collapsible */}
        {conversationExpanded && (
          <div className="border-t border-gray-200">
            <ConversationDetail
              conversationId={conversationId}
              hideSummary={true}
            />
          </div>
        )}
      </div>
    </div>
  );
}
