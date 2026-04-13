/**
 * Expert text chat type definitions
 */

export interface ChatSession {
  session_token: string;
  persona_id: string;
  username: string;
  is_anonymous: boolean;
}

export interface ProvideEmailRequest {
  sessionToken: string;
  email: string;
  fullname?: string;
  phone?: string;
  widgetToken?: string;
}

export interface ProvideEmailResponse {
  success: boolean;
  email: string;
  previous_conversations: boolean;
  merged_sessions: number;
}

export interface StreamChatRequest {
  sessionToken: string;
  username: string;
  message: string;
  context_window?: number;
  temperature?: number;
  widgetToken?: string;
}

export interface InitSessionRequest {
  username: string;
  personaName?: string;
  widgetToken?: string;
}

export interface ChatPDFUploadRequest {
  sessionToken: string;
  file: File;
  widgetToken?: string;
}

export interface ChatPDFUploadResponse {
  success: boolean;
  message: string;
  s3_url: string;
  filename: string;
  file_size: number;
}

export interface SpecialStreamChatRequest {
  sessionToken: string;
  username: string;
  message: string;
  pdfUrl?: string;
  temperature?: number;
  widgetToken?: string;
}

// Attachment upload types
export type AttachmentFileType =
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
export type ExtractionStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed";
export type ExtractionMethod = "marker_api" | "gpt4_vision" | null;

export interface AttachmentUploadRequest {
  sessionToken: string;
  file: File;
  widgetToken?: string;
}

export interface AttachmentUploadResponse {
  success: boolean;
  attachment_id: string;
  s3_url: string;
  filename: string;
  file_type: AttachmentFileType;
  file_size: number;
  mime_type: string;
  extracted_text: string | null;
  extraction_status: ExtractionStatus;
  extraction_method: ExtractionMethod;
  message: string;
}

export interface AttachmentInfo {
  id: string;
  filename: string;
  file_type: AttachmentFileType;
  file_size: number;
  s3_url: string;
  extraction_status: ExtractionStatus;
  uploaded_at: string;
}

export interface GetSessionAttachmentsRequest {
  sessionToken: string;
  widgetToken?: string;
}

export interface ConversationAttachment {
  id: string;
  filename: string;
  file_type: AttachmentFileType;
  file_size: number;
  mime_type: string;
  s3_url: string;
  extraction_status: ExtractionStatus;
  extraction_method: ExtractionMethod;
  message_index: number | null;
  uploaded_at: string;
  processed_at: string | null;
  metadata: Record<string, unknown>;
}

export interface ConversationAttachmentsResponse {
  conversation_id: string;
  attachments: ConversationAttachment[];
  total_count: number;
}

// Message attachment for display
export interface MessageAttachment {
  id: string;
  filename: string;
  file_type: AttachmentFileType;
  file_size: number;
  s3_url: string;
  extraction_status?: ExtractionStatus;
}

// Text limit exceeded error from 429 response
export interface TextLimitExceededError {
  error: "text_limit_exceeded";
  message: string;
  messages_used: number;
  messages_limit: number;
}

// Custom error class for text limit exceeded
export class TextLimitExceededApiError extends Error {
  public readonly messagesUsed: number;
  public readonly messagesLimit: number;

  constructor(detail: TextLimitExceededError) {
    super(detail.message);
    this.name = "TextLimitExceededApiError";
    this.messagesUsed = detail.messages_used;
    this.messagesLimit = detail.messages_limit;
  }
}

// LiveKit document upload types
export interface DocumentUploadMessage {
  type: "document_upload";
  filename: string;
  url: string; // S3 public URL from upload-attachment response
  extracted_text?: string | null; // Pre-extracted text to avoid backend re-fetching from S3
}

export interface DocumentStatusMessage {
  status: "success" | "error";
  filename: string;
  chars_extracted?: number;
  document_type?: string;
  message?: string; // Error message if status is "error"
}

// LiveKit text limit exceeded message (from chat_error topic)
export interface TextLimitExceededMessage {
  type: "text_limit_exceeded";
  message: string;
  messages_used: number;
  messages_limit: number;
}

// ============================================
// LEAD CAPTURE (Agent-driven via RPC)
// ============================================

/** Payload received from the agent via "leadCaptured" RPC */
export interface LeadCapturedRpcPayload {
  action: string;
  session_token: string;
  fullname?: string;
  email: string;
  phone?: string;
}

/** Request body for POST /sessions/{session_token}/capture-lead */
export interface LeadCaptureRequest {
  sessionToken: string;
  email: string;
  fullname?: string;
  phone?: string;
}

/** Response from POST /sessions/{session_token}/capture-lead */
export interface LeadCaptureResponse {
  success: boolean;
  email: string;
  user_id: string;
  is_new_user: boolean;
  previous_conversations: boolean;
  token: string;
}
