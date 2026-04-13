/**
 * Access Control type definitions
 * Manages private personas and authorized user access
 */

// User in the access control list (backend calls this "visitor")
export interface AccessControlUser {
  id: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  notes: string | null;
  createdAt: string;
  lastAccessedAt: string | null;
  assignedPersonaCount: number;
}

export interface AccessControlUsersResponse {
  visitors: AccessControlUser[];
  total: number;
}

// Add user to access list
export interface AddAccessControlUserRequest {
  email: string;
  firstName?: string;
  lastName?: string;
  notes?: string;
}

// Update user in access list
export interface UpdateAccessControlUserRequest {
  firstName?: string;
  lastName?: string;
  notes?: string;
}

// Toggle persona privacy
export interface AccessControlToggleRequest {
  isPrivate: boolean;
}

export interface AccessControlToggleResponse {
  success: boolean;
  message: string;
  personaId: string;
  isPrivate: boolean;
  accessControlEnabledAt: string | null;
}

// Persona's assigned users
export interface PersonaAccessControlUser {
  id: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  addedAt: string;
  lastAccessedAt: string | null;
}

export interface PersonaAccessControlUsersResponse {
  visitors: PersonaAccessControlUser[];
  total: number;
}

// Bulk assign users to persona
export interface AssignUsersRequest {
  visitorIds: string[]; // Backend uses "visitorIds" terminology
}

export interface AssignUsersResponse {
  success: boolean;
  message: string;
  assignedCount: number;
}

// Public OTP flow (visitor-facing)
export interface RequestAccessRequest {
  email: string;
  firstName?: string;
  lastName?: string;
}

export interface RequestAccessResponse {
  success: boolean;
  message: string;
  expiresIn?: number; // Seconds until OTP expires
}

export interface VerifyAccessRequest {
  email: string;
  otpCode: string;
  firstName?: string;
  lastName?: string;
}

export interface VerifyAccessResponse {
  success: boolean;
  message: string;
  visitorName?: string; // Display name for welcome message
}

// Check access with cookie or JWT
export interface CheckAccessResponse {
  hasAccess: boolean;
  isPrivate: boolean;
  visitorEmail: string | null;
  message: string;
  /** Whether user is authenticated via JWT (logged-in user) */
  isAuthenticated?: boolean;
}
