import { useMutation, useQuery } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { env } from "@/env";
import { api } from "@/lib/api/client";
import type { Room } from "livekit-client";
import type {
  ChatSession,
  ProvideEmailRequest,
  ProvideEmailResponse,
  StreamChatRequest,
  ChatPDFUploadRequest,
  ChatPDFUploadResponse,
  SpecialStreamChatRequest,
  AttachmentUploadRequest,
  AttachmentUploadResponse,
  AttachmentInfo,
  GetSessionAttachmentsRequest,
  TextLimitExceededError,
  DocumentUploadMessage,
} from "./interface";
import { TextLimitExceededApiError } from "./interface";

/**
 * Initialize anonymous chat session
 */
const initializeSession = async (
  username: string,
  personaName?: string,
  widgetToken?: string,
): Promise<ChatSession> => {
  const params = personaName ? `?persona_name=${personaName}` : "";
  const url = `${env.NEXT_PUBLIC_API_URL}/personas/username/${username}/init-session${params}`;

  const authToken = widgetToken || env.NEXT_PUBLIC_API_KEY;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${authToken}`,
  };

  const response = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to initialize session" }));
    throw new Error(error.detail || "Failed to initialize session");
  }

  return response.json();
};

/**
 * Provide email to associate with session
 * Now uses api client - interceptor handles authentication automatically
 */
const provideEmail = async ({
  sessionToken,
  email,
  fullname,
  phone,
  widgetToken: _widgetToken, // Kept for backward compatibility but not used (interceptor handles auth)
}: ProvideEmailRequest): Promise<ProvideEmailResponse> => {
  const { data } = await api.post<ProvideEmailResponse>(
    `/sessions/${sessionToken}/provide-email`,
    { email, fullname, phone },
  );
  return data;
};

/**
 * Send streaming chat message
 */
const sendStreamMessage = async ({
  sessionToken,
  username,
  message,
  context_window,
  temperature,
  widgetToken,
}: StreamChatRequest): Promise<ReadableStream<Uint8Array>> => {
  const authToken = widgetToken || env.NEXT_PUBLIC_API_KEY;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
    Authorization: `Bearer ${authToken}`,
  };

  const response = await fetch(
    `${env.NEXT_PUBLIC_API_URL}/personas/username/${username}/stream-chat`,
    {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify({
        message,
        session_token: sessionToken,
        context_window,
        temperature,
      }),
    },
  );

  if (!response.ok) {
    const errorData = await response
      .json()
      .catch(() => ({ detail: "Failed to send message" }));

    // Handle 429 Too Many Requests (text limit exceeded)
    // FastAPI wraps the error in a "detail" field
    const detailData = errorData?.detail;
    if (
      response.status === 429 &&
      typeof detailData === "object" &&
      detailData?.error === "text_limit_exceeded"
    ) {
      throw new TextLimitExceededApiError(detailData as TextLimitExceededError);
    }

    throw new Error(
      typeof detailData === "string"
        ? detailData
        : detailData?.message || errorData.message || "Failed to send message",
    );
  }

  if (!response.body) {
    throw new Error("No response body available");
  }

  return response.body;
};

/**
 * Hook to initialize expert chat session
 */
export function useInitSession() {
  return useMutation({
    mutationFn: ({
      username,
      personaName,
      widgetToken,
    }: {
      username: string;
      personaName?: string;
      widgetToken?: string;
    }) => initializeSession(username, personaName, widgetToken),
    onError: (error) => {
      Sentry.captureException(error, {
        tags: { operation: "chat_init_session" },
        contexts: {
          chat: {
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
    },
  });
}

/**
 * Hook to provide email for session
 */
export function useProvideEmail() {
  return useMutation({
    mutationFn: provideEmail,
    onError: (error) => {
      Sentry.captureException(error, {
        tags: { operation: "chat_provide_email" },
        contexts: {
          chat: {
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
    },
  });
}

/**
 * Hook to send streaming chat messages
 */
export function useSessionStreamChat() {
  return useMutation({
    mutationFn: sendStreamMessage,
    onError: (error) => {
      Sentry.captureException(error, {
        tags: { operation: "chat_stream_message" },
        contexts: {
          chat: {
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
    },
  });
}

/**
 * Upload PDF file as chat attachment
 * Now uses api client - interceptor handles authentication automatically
 */
const uploadChatPDF = async ({
  sessionToken,
  file,
  widgetToken: _widgetToken, // Kept for backward compatibility but not used (interceptor handles auth)
}: ChatPDFUploadRequest): Promise<ChatPDFUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await api.post<ChatPDFUploadResponse>(
    `/sessions/${sessionToken}/upload-pdf`,
    formData,
  );
  return data;
};

/**
 * Hook to upload PDF as chat attachment
 */
export function useChatPDFUpload() {
  return useMutation({
    mutationFn: uploadChatPDF,
    onError: (error) => {
      Sentry.captureException(error, {
        tags: { operation: "chat_pdf_upload" },
        contexts: {
          chat: {
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
    },
  });
}

/**
 * Send special streaming chat message with PDF for evaluation
 * Used for resume review and document analysis by specific experts
 */
const sendSpecialStreamMessage = async ({
  sessionToken,
  username,
  message,
  pdfUrl,
  temperature,
  widgetToken,
}: SpecialStreamChatRequest): Promise<ReadableStream<Uint8Array>> => {
  const authToken = widgetToken || env.NEXT_PUBLIC_API_KEY;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
    Authorization: `Bearer ${authToken}`,
  };

  const response = await fetch(
    `${env.NEXT_PUBLIC_API_URL}/personas/username/${username}/special-stream-chat`,
    {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify({
        message,
        session_token: sessionToken,
        ...(pdfUrl && { pdf_url: pdfUrl }),
        temperature,
      }),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Failed to send special chat message" }));
    throw new Error(error.detail || "Failed to send special chat message");
  }

  if (!response.body) {
    throw new Error("No response body available");
  }

  return response.body;
};

/**
 * Hook to send special streaming chat messages with PDF attachment
 */
export function useSpecialStreamChat() {
  return useMutation({
    mutationFn: sendSpecialStreamMessage,
    onError: (error) => {
      Sentry.captureException(error, {
        tags: { operation: "chat_special_stream" },
        contexts: {
          chat: {
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
    },
  });
}

// ============================================
// ATTACHMENT UPLOAD API (New endpoint)
// ============================================

/**
 * Supported file types configuration
 * Includes PDFs, Office documents (Word, Excel, PowerPoint), and images
 */
export const SUPPORTED_ATTACHMENT_TYPES = {
  // PDFs
  "application/pdf": { ext: "pdf", maxSize: 50 * 1024 * 1024 }, // 50MB
  // Microsoft Word
  "application/msword": { ext: "doc", maxSize: 50 * 1024 * 1024 }, // 50MB
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
    ext: "docx",
    maxSize: 50 * 1024 * 1024,
  }, // 50MB
  // Microsoft Excel
  "application/vnd.ms-excel": { ext: "xls", maxSize: 50 * 1024 * 1024 }, // 50MB
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
    ext: "xlsx",
    maxSize: 50 * 1024 * 1024,
  }, // 50MB
  // Microsoft PowerPoint
  "application/vnd.ms-powerpoint": { ext: "ppt", maxSize: 50 * 1024 * 1024 }, // 50MB
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
    ext: "pptx",
    maxSize: 50 * 1024 * 1024,
  }, // 50MB
  // Images
  "image/png": { ext: "png", maxSize: 20 * 1024 * 1024 }, // 20MB
  "image/jpeg": { ext: "jpg", maxSize: 20 * 1024 * 1024 }, // 20MB (covers .jpg and .jpeg)
} as const;

export type SupportedMimeType = keyof typeof SUPPORTED_ATTACHMENT_TYPES;

/**
 * Upload attachment to chat session
 * Supports PDF, Office documents (DOC, DOCX, XLS, XLSX, PPT, PPTX), and images (PNG, JPG/JPEG)
 * Now uses api client - interceptor handles authentication automatically
 */
const uploadAttachment = async ({
  sessionToken,
  file,
  widgetToken: _widgetToken, // Kept for backward compatibility but not used (interceptor handles auth)
}: AttachmentUploadRequest): Promise<AttachmentUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await api.post<AttachmentUploadResponse>(
    `/sessions/${sessionToken}/upload-attachment`,
    formData,
  );
  return data;
};

/**
 * Hook to upload attachment to chat session
 */
export function useAttachmentUpload() {
  return useMutation({
    mutationFn: uploadAttachment,
    onError: (error) => {
      Sentry.captureException(error, {
        tags: { operation: "chat_attachment_upload" },
        contexts: {
          chat: {
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
    },
  });
}

/**
 * Get session attachments
 * Now uses api client - interceptor handles authentication automatically
 */
const getSessionAttachments = async ({
  sessionToken,
  widgetToken: _widgetToken, // Kept for backward compatibility but not used (interceptor handles auth)
}: GetSessionAttachmentsRequest): Promise<AttachmentInfo[]> => {
  const { data } = await api.get<AttachmentInfo[]>(
    `/sessions/${sessionToken}/attachments`,
  );
  return data;
};

/**
 * Hook to get session attachments
 */
export function useSessionAttachments(
  sessionToken: string | null,
  widgetToken?: string,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ["session-attachments", sessionToken],
    queryFn: () => {
      if (!sessionToken) throw new Error("Session token required");
      return getSessionAttachments({ sessionToken, widgetToken });
    },
    enabled: options?.enabled !== false && !!sessionToken,
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Validate file before upload
 * Returns error message if invalid, null if valid
 */
export function validateAttachmentFile(file: File): string | null {
  // Check file type
  const mimeType = file.type as SupportedMimeType;
  const config = SUPPORTED_ATTACHMENT_TYPES[mimeType];

  if (!config) {
    const extension = file.name.split(".").pop()?.toLowerCase() || "unknown";
    return `Unsupported file type '.${extension}'. Supported: .pdf, .doc, .docx, .xls, .xlsx, .ppt, .pptx, .png, .jpg, .jpeg`;
  }

  // Check file size
  if (file.size > config.maxSize) {
    const maxSizeMB = config.maxSize / (1024 * 1024);
    return `File too large. Maximum size for .${config.ext} is ${maxSizeMB}MB`;
  }

  return null;
}

/** File category type for icon display */
export type AttachmentCategory =
  | "pdf"
  | "document"
  | "spreadsheet"
  | "presentation"
  | "image";

/**
 * Get file category based on file type
 */
export function getAttachmentCategory(fileType: string): AttachmentCategory {
  const documentTypes = ["doc", "docx"];
  const spreadsheetTypes = ["xls", "xlsx"];
  const presentationTypes = ["ppt", "pptx"];
  const imageTypes = ["png", "jpg", "jpeg"];

  if (fileType === "pdf") return "pdf";
  if (documentTypes.includes(fileType)) return "document";
  if (spreadsheetTypes.includes(fileType)) return "spreadsheet";
  if (presentationTypes.includes(fileType)) return "presentation";
  if (imageTypes.includes(fileType)) return "image";
  return "document"; // Default fallback
}

/**
 * Get file icon based on file type
 * @deprecated Use getAttachmentCategory instead for more granular icon selection
 */
export function getAttachmentIcon(fileType: string): "pdf" | "image" {
  const imageTypes = ["png", "jpg", "jpeg"];
  return imageTypes.includes(fileType) ? "image" : "pdf";
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// ============================================
// LIVEKIT DOCUMENT UPLOAD NOTIFICATION
// ============================================

/**
 * Send document upload notification to LiveKit agent via data channel.
 * This notifies the agent that a document has been uploaded to S3
 * so it can process and add to session context for LLM.
 *
 * @param room - LiveKit room instance
 * @param filename - Name of the uploaded file
 * @param s3Url - S3 public URL of the uploaded file
 * @param extractedText - Pre-extracted text content (optional, avoids backend S3 re-fetch)
 * @returns Promise that resolves when the message is published
 */
export async function notifyLiveKitDocumentUpload(
  room: Room,
  filename: string,
  s3Url: string,
  extractedText?: string | null,
): Promise<void> {
  const payload: DocumentUploadMessage = {
    type: "document_upload",
    filename,
    url: s3Url,
    extracted_text: extractedText,
  };

  const sendTopic = "lk.chat";
  if (process.env.NODE_ENV === "development") {
    console.log(
      `📤 [SEND Topic: ${sendTopic}] Document upload notification:`,
      payload,
    );
  }

  try {
    // Use sendText() with proper options object for text-only agents
    // Architecture: Client sends on "lk.chat" → Agent receives and processes document
    await room.localParticipant.sendText(JSON.stringify(payload), {
      topic: sendTopic,
    });

    if (process.env.NODE_ENV === "development") {
      console.log(
        `✅ [SEND Topic: ${sendTopic}] Document upload notification sent via sendText successfully`,
      );
    }
  } catch (error) {
    console.error(
      "❌ [LiveKit] Failed to send document upload notification:",
      error,
    );
    Sentry.captureException(error, {
      tags: { operation: "livekit_document_upload_notify" },
      contexts: {
        document: {
          filename,
          s3Url: s3Url.substring(0, 100),
          error: error instanceof Error ? error.message : "Unknown error",
        },
      },
    });
    throw error;
  }
}
