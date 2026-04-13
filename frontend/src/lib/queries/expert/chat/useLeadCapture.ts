import { useMutation } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";
import type { LeadCaptureRequest, LeadCaptureResponse } from "./interface";

/**
 * Capture lead data collected by the AI agent during conversation.
 *
 * POST /sessions/{session_token}/capture-lead
 *
 * This endpoint:
 * 1. Validates the session token
 * 2. Finds or creates a VISITOR user (unverified)
 * 3. Creates a free-tier subscription
 * 4. Updates UserSession and Conversation records with real email/name/phone
 * 5. Sets an HTTP-only JWT cookie (myclone_token) on the response
 *
 * CRITICAL: The Axios client has `withCredentials: true` which ensures the
 * browser accepts the Set-Cookie header from the response. Without this, the
 * visitor won't stay authenticated.
 */
const captureLead = async ({
  sessionToken,
  email,
  fullname,
  phone,
}: LeadCaptureRequest): Promise<LeadCaptureResponse> => {
  const { data } = await api.post<LeadCaptureResponse>(
    `/sessions/${sessionToken}/capture-lead`,
    { email, fullname, phone },
  );
  return data;
};

/**
 * Hook for capturing lead data from the AI agent.
 *
 * Used inside the "leadCaptured" RPC handler — when the agent finishes
 * collecting name/email/phone, it sends an RPC to the frontend which
 * calls this mutation to persist the data and receive the JWT cookie.
 */
export function useCaptureLead() {
  return useMutation({
    mutationFn: captureLead,
    onError: (error) => {
      Sentry.captureException(error, {
        tags: { operation: "lead_capture" },
        contexts: {
          lead_capture: {
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
    },
  });
}
