/**
 * Claim Account API Interfaces
 * Handles account claim flow for auto-onboarded users
 */

// ========================================
// Verify Claim Code
// ========================================

export interface VerifyClaimCodeRequest {
  code: string;
}

export interface VerifyClaimCodeResponse {
  message: string;
  username: string;
  email: string;
  fullname: string;
  is_generated_email: boolean;
}

// ========================================
// Check Username Availability
// ========================================

export interface CheckUsernameRequest {
  username: string;
}

export interface CheckUsernameResponse {
  available: boolean;
  username: string; // Normalized (lowercase)
}

// ========================================
// Submit Claim
// ========================================

export interface SubmitClaimRequest {
  code: string;
  username: string;
  email: string;
  password: string;
}

export interface SubmitClaimResponse {
  message: string;
  user_id: string;
  email: string;
  fullname: string;
  token: string;
}
