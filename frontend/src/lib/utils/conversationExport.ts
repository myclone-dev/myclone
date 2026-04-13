import type {
  ConversationDetail,
  ConversationMessage,
  ConversationSummaryResult,
} from "@/lib/queries/conversations";
import { decodeHtmlEntities } from "@/lib/utils";
import { toast } from "sonner";
import * as Sentry from "@sentry/nextjs";

/**
 * Utility functions for exporting conversations to PDF and Markdown formats
 * Both formats include the AI summary and full conversation transcript
 */

/**
 * Sanitize filename by removing invalid filesystem characters
 * and limiting length to prevent issues across different operating systems
 */
function sanitizeFilename(name: string, maxLength = 50): string {
  return name
    .replace(/[/\\:*?"<>|]/g, "_") // Replace invalid chars with underscore
    .replace(/\s+/g, "_") // Replace spaces with underscore
    .replace(/_+/g, "_") // Collapse multiple underscores
    .replace(/^_|_$/g, "") // Trim leading/trailing underscores
    .slice(0, maxLength); // Limit length
}

// Helper to get message text from various possible fields
function getMessageText(message: ConversationMessage): string {
  const text = message.text || message.content || message.message || "";
  return decodeHtmlEntities(text);
}

// Helper to get speaker name
function getSpeaker(message: ConversationMessage): string {
  const speaker = message.speaker || message.role || message.type || "user";
  if (speaker === "user" || speaker === "human" || speaker === "USER") {
    return "Visitor";
  }
  return "AI Clone";
}

// Format timestamp for display
function formatTimestamp(timestamp?: string): string {
  if (!timestamp) return "";
  return new Date(timestamp).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Escape HTML special characters for safe display
 */
function escapeHtml(text: string): string {
  // First decode any existing entities, then escape for HTML
  const decoded = decodeHtmlEntities(text);
  return decoded
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Generate Markdown content from conversation data (includes summary + transcript)
 */
export function generateConversationMarkdown(
  conversation: ConversationDetail,
  summary?: ConversationSummaryResult | null,
  personaName?: string,
): string {
  const lines: string[] = [];

  // Header
  lines.push("# Conversation Export");
  lines.push("");

  // Metadata
  lines.push("## Details");
  lines.push("");
  lines.push(
    `- **Date:** ${new Date(conversation.created_at).toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}`,
  );
  lines.push(`- **Type:** ${conversation.conversation_type}`);
  lines.push(`- **Messages:** ${conversation.message_count}`);
  if (conversation.user_fullname) {
    lines.push(`- **Visitor Name:** ${conversation.user_fullname}`);
  }
  if (conversation.user_email) {
    lines.push(`- **Visitor Email:** ${conversation.user_email}`);
  }
  if (conversation.user_phone) {
    lines.push(`- **Visitor Phone:** ${conversation.user_phone}`);
  }
  if (personaName) {
    lines.push(`- **AI Clone:** ${decodeHtmlEntities(personaName)}`);
  }
  lines.push("");

  // Summary section
  if (summary) {
    lines.push("## AI Summary");
    lines.push("");
    lines.push(decodeHtmlEntities(summary.summary));
    lines.push("");

    if (summary.key_topics) {
      const topics = summary.key_topics
        .split(",")
        .map((t) => decodeHtmlEntities(t.trim()))
        .filter(Boolean);
      if (topics.length > 0) {
        lines.push("### Key Topics");
        lines.push("");
        topics.forEach((topic) => {
          lines.push(`- ${topic}`);
        });
        lines.push("");
      }
    }

    lines.push(`**Sentiment:** ${summary.sentiment}`);
    lines.push("");
  }

  // Conversation transcript
  lines.push("## Conversation Transcript");
  lines.push("");

  const messages = conversation.messages.filter((m) => !m.hidden);

  if (messages.length === 0) {
    lines.push("*No messages in this conversation.*");
  } else {
    messages.forEach((message) => {
      const speaker = getSpeaker(message);
      const isVisitor = speaker === "Visitor";
      // Use persona name for AI messages, fallback to "AI Clone"
      const displayName = isVisitor
        ? "Visitor"
        : personaName
          ? decodeHtmlEntities(personaName)
          : "AI Clone";
      const text = getMessageText(message);
      const timestamp = formatTimestamp(message.timestamp);

      lines.push(`### ${displayName}${timestamp ? ` (${timestamp})` : ""}`);
      lines.push("");
      lines.push(text);
      lines.push("");

      // Add attachment info if present
      if (message.attachments && message.attachments.length > 0) {
        lines.push("**Attachments:**");
        message.attachments.forEach((att) => {
          lines.push(`- ${att.filename} (${att.file_type.toUpperCase()})`);
        });
        lines.push("");
      }
    });
  }

  // Footer
  lines.push("---");
  lines.push("");
  lines.push(
    `*Exported on ${new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric", hour: "numeric", minute: "2-digit" })}*`,
  );

  return lines.join("\n");
}

/**
 * Download content as a file
 */
function downloadFile(
  content: string,
  filename: string,
  mimeType: string,
): void {
  try {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (error) {
    Sentry.captureException(error, {
      tags: { operation: "conversation_export_download" },
      contexts: {
        export: {
          filename,
          mimeType,
          error: error instanceof Error ? error.message : "Unknown error",
        },
      },
    });
    console.error("Failed to download file:", error);
    toast.error("Failed to download file. Please try again.");
    throw error;
  }
}

/**
 * Download conversation as Markdown file (includes summary + transcript)
 */
export function downloadConversationAsMarkdown(
  conversation: ConversationDetail,
  summary?: ConversationSummaryResult | null,
  personaName?: string,
): void {
  try {
    const markdown = generateConversationMarkdown(
      conversation,
      summary,
      personaName,
    );
    const date = new Date(conversation.created_at).toISOString().split("T")[0];
    const visitorName = sanitizeFilename(
      conversation.user_fullname || "visitor",
    );
    const filename = `conversation_${visitorName}_${date}.md`;
    downloadFile(markdown, filename, "text/markdown");
    toast.success("Markdown file downloaded successfully");
  } catch (error) {
    Sentry.captureException(error, {
      tags: { operation: "conversation_export_markdown" },
      contexts: {
        export: {
          conversationId: conversation.id,
          messageCount: conversation.message_count,
          error: error instanceof Error ? error.message : "Unknown error",
        },
      },
    });
    console.error("Failed to download markdown:", error);
    toast.error("Failed to download conversation as Markdown");
  }
}

/**
 * Generate PDF content using HTML and print-to-PDF approach
 * Includes both AI summary and full conversation transcript
 */
export function generateConversationPdfHtml(
  conversation: ConversationDetail,
  summary?: ConversationSummaryResult | null,
  personaName?: string,
): string {
  const date = new Date(conversation.created_at).toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const messages = conversation.messages.filter((m) => !m.hidden);

  const topics = summary?.key_topics
    ? summary.key_topics
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean)
    : [];

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Conversation Export - ${escapeHtml(date)}</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      line-height: 1.6;
      color: #1a1a1a;
      max-width: 800px;
      margin: 0 auto;
      padding: 40px 24px;
      background: #fff;
    }
    .header {
      text-align: center;
      margin-bottom: 32px;
      padding-bottom: 24px;
      border-bottom: 2px solid #e5e7eb;
    }
    h1 {
      font-size: 28px;
      font-weight: 700;
      margin-bottom: 8px;
      color: #111;
    }
    .subtitle {
      font-size: 14px;
      color: #6b7280;
    }
    h2 {
      font-size: 18px;
      font-weight: 600;
      margin-top: 32px;
      margin-bottom: 16px;
      color: #111;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    h2::before {
      content: '';
      display: inline-block;
      width: 4px;
      height: 20px;
      background: #3b82f6;
      border-radius: 2px;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      background: #f9fafb;
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 24px;
    }
    .meta-item {
      font-size: 13px;
    }
    .meta-label {
      color: #6b7280;
      font-weight: 500;
    }
    .meta-value {
      color: #111;
      font-weight: 600;
    }
    .summary-box {
      background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%);
      border-radius: 12px;
      padding: 20px;
      margin: 20px 0;
      border-left: 4px solid #8b5cf6;
    }
    .summary-text {
      font-size: 15px;
      color: #1f2937;
      line-height: 1.7;
    }
    .topics-section {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid rgba(139, 92, 246, 0.2);
    }
    .topics-label {
      font-size: 12px;
      font-weight: 600;
      color: #6b7280;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .topics {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .topic {
      background: white;
      color: #6d28d9;
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 500;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
      border: 1px solid #ddd6fe;
    }
    .sentiment {
      display: inline-flex;
      align-items: center;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      margin-top: 12px;
      text-transform: capitalize;
    }
    .sentiment-positive { background: #dcfce7; color: #166534; }
    .sentiment-neutral { background: #f3f4f6; color: #374151; }
    .sentiment-negative { background: #fee2e2; color: #991b1b; }
    .sentiment-mixed { background: #fef3c7; color: #92400e; }
    .messages-container {
      margin-top: 24px;
    }
    .message {
      margin: 20px 0;
      display: flex;
      flex-direction: column;
    }
    .message-visitor {
      align-items: flex-end;
    }
    .message-ai {
      align-items: flex-start;
    }
    .message-bubble {
      max-width: 85%;
      padding: 14px 18px;
      border-radius: 16px;
      position: relative;
    }
    .message-visitor .message-bubble {
      background: #fffbeb;
      color: #1f2937;
      border-bottom-right-radius: 4px;
      border: 1px solid #fbbf24;
    }
    .message-ai .message-bubble {
      background: #ffffff;
      color: #1f2937;
      border-bottom-left-radius: 4px;
      border: 1px solid #e5e7eb;
    }
    .message-header {
      font-size: 11px;
      font-weight: 600;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .message-visitor .message-header {
      color: #b45309;
    }
    .message-ai .message-header {
      color: #374151;
    }
    .message-text {
      font-size: 14px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    .message-visitor .message-text {
      color: #1f2937;
    }
    .message-ai .message-text {
      color: #1f2937;
    }
    .message-time {
      font-size: 11px;
      margin-top: 8px;
    }
    .message-visitor .message-time {
      color: #b45309;
    }
    .message-ai .message-time {
      color: #6b7280;
    }
    .attachments {
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid rgba(0,0,0,0.1);
      font-size: 12px;
    }
    .footer {
      margin-top: 48px;
      padding-top: 20px;
      border-top: 2px solid #e5e7eb;
      font-size: 12px;
      color: #9ca3af;
      text-align: center;
    }
    .no-messages {
      text-align: center;
      padding: 40px;
      color: #6b7280;
      font-style: italic;
    }
    @media print {
      body {
        padding: 16px;
        font-size: 12px;
      }
      .message {
        break-inside: avoid;
        margin: 12px 0;
      }
      .summary-box {
        break-inside: avoid;
      }
      h2 {
        break-after: avoid;
      }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>Conversation Export</h1>
    <div class="subtitle">${escapeHtml(date)}</div>
  </div>

  <div class="meta-grid">
    <div class="meta-item">
      <span class="meta-label">Type: </span>
      <span class="meta-value">${escapeHtml(conversation.conversation_type)}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Messages: </span>
      <span class="meta-value">${conversation.message_count}</span>
    </div>
    ${conversation.user_fullname ? `<div class="meta-item"><span class="meta-label">Visitor: </span><span class="meta-value">${escapeHtml(conversation.user_fullname)}</span></div>` : ""}
    ${conversation.user_email ? `<div class="meta-item"><span class="meta-label">Email: </span><span class="meta-value">${escapeHtml(conversation.user_email)}</span></div>` : ""}
    ${personaName ? `<div class="meta-item"><span class="meta-label">AI Clone: </span><span class="meta-value">${escapeHtml(personaName)}</span></div>` : ""}
  </div>

  ${
    summary
      ? `
  <h2>AI Summary</h2>
  <div class="summary-box">
    <div class="summary-text">${escapeHtml(summary.summary)}</div>
    ${
      topics.length > 0
        ? `
    <div class="topics-section">
      <div class="topics-label">Key Topics</div>
      <div class="topics">
        ${topics.map((t) => `<span class="topic">${escapeHtml(t)}</span>`).join("")}
      </div>
    </div>
    `
        : ""
    }
    <span class="sentiment sentiment-${summary.sentiment}">${summary.sentiment}</span>
  </div>
  `
      : ""
  }

  <h2>Conversation</h2>
  <div class="messages-container">
  ${
    messages.length === 0
      ? '<div class="no-messages">No messages in this conversation.</div>'
      : messages
          .map((msg) => {
            const speaker = getSpeaker(msg);
            const isVisitor = speaker === "Visitor";
            // Use persona name for AI messages, fallback to "AI Clone"
            const displayName = isVisitor
              ? "Visitor"
              : personaName
                ? escapeHtml(personaName)
                : "AI Clone";
            const text = getMessageText(msg);
            const timestamp = msg.timestamp
              ? new Date(msg.timestamp).toLocaleString("en-US", {
                  hour: "numeric",
                  minute: "2-digit",
                })
              : "";
            const attachments = msg.attachments || [];

            return `
    <div class="message ${isVisitor ? "message-visitor" : "message-ai"}">
      <div class="message-bubble">
        <div class="message-header">${displayName}</div>
        <div class="message-text">${escapeHtml(text)}</div>
        ${timestamp ? `<div class="message-time">${timestamp}</div>` : ""}
        ${
          attachments.length > 0
            ? `
        <div class="attachments">
          <strong>Attachments:</strong> ${attachments.map((a) => `${escapeHtml(a.filename)} (${a.file_type.toUpperCase()})`).join(", ")}
        </div>
        `
            : ""
        }
      </div>
    </div>
    `;
          })
          .join("")
  }
  </div>

  <div class="footer">
    Exported on ${escapeHtml(new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric", hour: "numeric", minute: "2-digit" }))}
  </div>
</body>
</html>
`;
}

/**
 * Download as PDF by opening print dialog
 */
function downloadAsPdf(html: string, title: string): void {
  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    toast.error("Please allow popups to download PDF");
    return;
  }

  printWindow.document.write(html);
  printWindow.document.close();

  // Wait for content to load, then trigger print
  printWindow.onload = () => {
    printWindow.document.title = title;
    printWindow.print();
  };
}

/**
 * Download conversation as PDF (includes summary + transcript)
 */
export function downloadConversationAsPdf(
  conversation: ConversationDetail,
  summary?: ConversationSummaryResult | null,
  personaName?: string,
): void {
  try {
    const html = generateConversationPdfHtml(
      conversation,
      summary,
      personaName,
    );
    const date = new Date(conversation.created_at).toISOString().split("T")[0];
    const visitorName = sanitizeFilename(
      conversation.user_fullname || "visitor",
    );
    const title = `Conversation - ${visitorName} - ${date}`;
    downloadAsPdf(html, title);
  } catch (error) {
    Sentry.captureException(error, {
      tags: { operation: "conversation_export_pdf" },
      contexts: {
        export: {
          conversationId: conversation.id,
          messageCount: conversation.message_count,
          error: error instanceof Error ? error.message : "Unknown error",
        },
      },
    });
    console.error("Failed to download PDF:", error);
    toast.error("Failed to download conversation as PDF");
  }
}
