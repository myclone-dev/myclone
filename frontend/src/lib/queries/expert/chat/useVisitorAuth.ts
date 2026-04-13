import { useMutation } from "@tanstack/react-query";
import { env } from "@/env";

// ============================================================================
// TYPES
// ============================================================================

export interface RequestOtpRequest {
  email: string;
  fullname?: string;
  personaUsername?: string; // For whitelabel email - OTP sent from persona owner's custom domain
  source?: "email_capture"; // For conversation email capture (uses neutral email template)
}

export interface RequestOtpResponse {
  success: boolean;
  message: string;
  is_new_user: boolean;
  account_type?: string; // "visitor" | "creator"
}

export interface VerifyOtpRequest {
  email: string;
  otpCode: string; // Backend uses camelCase
}

export interface VerifyOtpResponse {
  success: boolean;
  message: string;
  user_id: string;
  email: string;
  fullname: string;
  account_type: string; // "visitor" | "creator"
  token: string; // JWT token for visitor authentication
}

// ============================================================================
// REQUEST OTP
// ============================================================================

const requestOtp = async (
  data: RequestOtpRequest,
): Promise<RequestOtpResponse> => {
  const response = await fetch(`${env.NEXT_PUBLIC_API_URL}/auth/request-otp`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to request OTP");
  }

  return response.json();
};

export const useRequestOtp = () => {
  return useMutation({
    mutationFn: requestOtp,
  });
};

// ============================================================================
// VERIFY OTP
// ============================================================================

const verifyOtp = async (
  data: VerifyOtpRequest,
): Promise<VerifyOtpResponse> => {
  const response = await fetch(`${env.NEXT_PUBLIC_API_URL}/auth/verify-otp`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Invalid or expired verification code");
  }

  return response.json();
};

export const useVerifyOtp = () => {
  return useMutation({
    mutationFn: verifyOtp,
  });
};
