/**
 * Conversation API type definitions
 */

export type ConversationType = "text" | "voice";

export type RecordingStatus =
  | "disabled"
  | "starting" // Recording initiation in progress
  | "active" // Recording in progress
  | "stopping" // Recording stop in progress
  | "completed" // Recording saved to S3
  | "failed" // Recording failed
  | "stopped"; // Recording manually stopped

export interface Source {
  source: string;
  title: string;
  content: string;
  similarity?: number;
  source_url: string;
  type: "social_media" | "website" | "document" | "other";
  verification_note?: string;
}

// Attachment interface for conversation messages
export interface ConversationMessageAttachment {
  id: string;
  filename: string;
  file_type:
    | "pdf"
    | "doc"
    | "docx"
    | "xls"
    | "xlsx"
    | "ppt"
    | "pptx"
    | "png"
    | "jpg"
    | "jpeg";
  file_size?: number; // Optional for backward compatibility with older messages
  s3_url: string;
  extraction_status?: "pending" | "processing" | "completed" | "failed";
}

export interface ConversationMessage {
  // Support both frontend and backend field names
  speaker?: string; // 'user' or 'assistant'
  role?: string; // Backend uses 'role'
  type?: string;
  text?: string;
  content?: string; // Backend uses 'content'
  message?: string;
  timestamp?: string;
  isComplete?: boolean;
  sources?: Source[]; // Citations/sources for the message
  // Attachment support for PDFs and images
  attachments?: ConversationMessageAttachment[];
  // Legacy fields for special chat with attachments
  hidden?: boolean; // If true, don't render this message in UI
  content_type?: string; // "text" | "pdf"
  url?: string; // URL for attachments (e.g., S3 URL for PDFs)
}

export interface ConversationSummary {
  id: string;
  persona_id: string;
  session_id: string | null; // LiveKit/voice session token
  workflow_session_id: string | null; // Workflow session UUID (for fetching lead evaluation)
  user_email: string | null;
  user_fullname: string | null;
  user_phone: string | null;
  conversation_type: ConversationType;
  message_count: number;
  last_message_preview: string | null;
  created_at: string;
  updated_at: string;
  unread_count?: number; // Optional: may not come from backend yet
  is_new?: boolean; // Mark as new if created in last 24 hours
  voice_duration_seconds?: number; // Duration of voice conversation in seconds (only for voice type)
}

export interface ConversationDetail {
  id: string;
  persona_id: string;
  session_id: string | null; // LiveKit/voice session token
  workflow_session_id: string | null; // Workflow session UUID (for fetching lead evaluation)
  user_email: string | null;
  user_fullname: string | null;
  user_phone: string | null;
  conversation_type: ConversationType;
  messages: ConversationMessage[];
  conversation_metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  // Recording fields (voice conversations only)
  recording_url: string | null;
  recording_status: RecordingStatus | null;
  recording_duration_seconds: number | null;
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  // Aggregate counts from backend (if available)
  text_conversations?: number;
  voice_conversations?: number;
}

export interface ConversationQueryParams {
  limit?: number;
  offset?: number;
  conversation_type?: ConversationType;
}

export type ConversationSentiment =
  | "positive"
  | "neutral"
  | "negative"
  | "mixed";

export interface ConversationSummaryResult {
  conversation_id: string;
  summary: string;
  key_topics: string;
  sentiment: ConversationSentiment;
  message_count: number;
  conversation_type: ConversationType;
  generated_at: string;
}
