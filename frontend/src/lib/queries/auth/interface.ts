/**
 * Authentication type definitions
 */

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  fullname: string;
  username?: string;
  account_type?: string;
  license_key?: string;
}

export interface RegisterResponse {
  message: string;
  email: string;
}

export interface VerifyEmailResponse {
  message: string;
  user_id: string;
  email: string;
  fullname: string;
  token: string;
  account_type: string;
}

export interface LoginResponse {
  message: string;
  user_id: string;
  email: string;
  fullname: string;
  token: string;
  account_type: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ForgotPasswordResponse {
  message: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface ResetPasswordResponse {
  message: string;
}

export interface ResendVerificationRequest {
  email: string;
}

export interface ResendVerificationResponse {
  message: string;
}

export interface SetPasswordRequest {
  password: string;
}

export interface SetPasswordResponse {
  message: string;
}

// Legacy interfaces (keep for backward compatibility)
export interface SignupData {
  email: string;
  password: string;
  name: string;
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  username?: string;
}

export interface AuthResponse {
  user: AuthUser;
  token: string;
}
