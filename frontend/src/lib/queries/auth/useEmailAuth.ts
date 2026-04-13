import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  RegisterData,
  RegisterResponse,
  VerifyEmailResponse,
  LoginCredentials,
  LoginResponse,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
  ResetPasswordRequest,
  ResetPasswordResponse,
  ResendVerificationRequest,
  ResendVerificationResponse,
  SetPasswordRequest,
  SetPasswordResponse,
} from "./interface";

/**
 * Register new user with email/password
 * POST /auth/register
 */
const register = async (data: RegisterData): Promise<RegisterResponse> => {
  const response = await api.post<RegisterResponse>("/auth/register", data);
  return response.data;
};

export function useRegister() {
  return useMutation({
    mutationFn: register,
  });
}

/**
 * Verify email with token
 * GET /auth/verify-email?token={token}
 */
const verifyEmail = async (token: string): Promise<VerifyEmailResponse> => {
  const response = await api.get<VerifyEmailResponse>(
    `/auth/verify-email?token=${token}`,
  );
  return response.data;
};

export function useVerifyEmail(token: string | null) {
  return useQuery<VerifyEmailResponse, Error>({
    queryKey: ["verify-email", token],
    queryFn: () => {
      if (!token) throw new Error("Token is required");
      return verifyEmail(token);
    },
    enabled: !!token,
    retry: false,
  });
}

/**
 * Login with email/password
 * POST /auth/login
 */
const login = async (credentials: LoginCredentials): Promise<LoginResponse> => {
  const response = await api.post<LoginResponse>("/auth/login", credentials);
  return response.data;
};

export function useEmailLogin() {
  return useMutation({
    mutationFn: login,
  });
}

/**
 * Request password reset
 * POST /auth/forgot-password
 */
const forgotPassword = async (
  data: ForgotPasswordRequest,
): Promise<ForgotPasswordResponse> => {
  const response = await api.post<ForgotPasswordResponse>(
    "/auth/forgot-password",
    data,
  );
  return response.data;
};

export function useForgotPassword() {
  return useMutation({
    mutationFn: forgotPassword,
  });
}

/**
 * Reset password with token
 * POST /auth/reset-password
 */
const resetPassword = async (
  data: ResetPasswordRequest,
): Promise<ResetPasswordResponse> => {
  const response = await api.post<ResetPasswordResponse>(
    "/auth/reset-password",
    data,
  );
  return response.data;
};

export function useResetPassword() {
  return useMutation({
    mutationFn: resetPassword,
  });
}

/**
 * Resend verification email
 * POST /auth/resend-verification
 */
const resendVerification = async (
  data: ResendVerificationRequest,
): Promise<ResendVerificationResponse> => {
  const response = await api.post<ResendVerificationResponse>(
    "/auth/resend-verification",
    data,
  );
  return response.data;
};

export function useResendVerification() {
  return useMutation({
    mutationFn: resendVerification,
  });
}

/**
 * Set password for OAuth users
 * POST /auth/set-password
 * Requires authentication
 */
const setPassword = async (
  data: SetPasswordRequest,
): Promise<SetPasswordResponse> => {
  const response = await api.post<SetPasswordResponse>(
    "/auth/set-password",
    data,
  );
  return response.data;
};

export function useSetPassword() {
  return useMutation({
    mutationFn: setPassword,
  });
}
