import type { AxiosError } from "axios";

/**
 * API Error Parsing Utilities
 * Handles different error response formats from backend
 */

/**
 * Standard API error response format from backend
 */
export interface ApiErrorResponse {
  detail: string | Array<{ msg: string; loc?: string[] }>;
  message?: string;
}

/**
 * Status code to user-friendly message mapping
 */
const STATUS_CODE_MESSAGES: Record<number, string> = {
  400: "Invalid request. Please check your input and try again.",
  401: "Authentication required. Please log in and try again.",
  403: "Access denied. You don't have permission to perform this action.",
  404: "The requested resource was not found.",
  409: "This action conflicts with existing data.",
  413: "The file you're trying to upload is too large.",
  422: "The data provided is invalid or incomplete.",
  429: "Too many requests. Please slow down and try again later.",
  500: "Server error. Please try again later.",
  502: "Service temporarily unavailable. Please try again later.",
  503: "Service temporarily unavailable. Please try again later.",
  504: "Request timeout. Please try again.",
};

/**
 * Parse API error and extract user-friendly message
 *
 * Handles:
 * - Network errors (no response)
 * - Status-code-specific messages
 * - FastAPI validation errors (detail array)
 * - Simple error messages (detail string)
 * - Axios errors
 * - Generic Error instances
 *
 * @param error - The error object from API call
 * @param fallbackMessage - Custom fallback message (optional)
 * @returns User-friendly error message
 */
export function parseApiError(
  error: unknown,
  fallbackMessage?: string,
): string {
  // Handle Axios error
  if (error && typeof error === "object" && "isAxiosError" in error) {
    const axiosError = error as AxiosError<ApiErrorResponse>;

    // Network error (no response from server)
    if (!axiosError.response) {
      if (axiosError.code === "ECONNABORTED") {
        return "Request timeout. Please check your connection and try again.";
      }
      if (axiosError.code === "ERR_NETWORK") {
        return "Network error. Please check your internet connection.";
      }
      return "Unable to connect to server. Please check your internet connection.";
    }

    const { response } = axiosError;
    const statusCode = response.status;
    const data = response.data;

    // Handle FastAPI validation error (detail is array)
    if (data?.detail && Array.isArray(data.detail)) {
      const firstError = data.detail[0];
      if (firstError?.msg) {
        // Include field location if available
        const location = firstError.loc
          ?.filter((l) => l !== "body")
          .join(" → ");
        return location ? `${location}: ${firstError.msg}` : firstError.msg;
      }
      return STATUS_CODE_MESSAGES[422] || "Validation error";
    }

    // Handle simple error detail (detail is string)
    if (typeof data?.detail === "string") {
      return data.detail;
    }

    // Handle message field
    if (data?.message) {
      return data.message;
    }

    // Status-code-specific fallback messages
    if (STATUS_CODE_MESSAGES[statusCode]) {
      return STATUS_CODE_MESSAGES[statusCode];
    }

    // Generic HTTP error fallback
    if (statusCode >= 500) {
      return "Server error. Please try again later.";
    }
    if (statusCode >= 400) {
      return "Request failed. Please check your input and try again.";
    }
  }

  // Handle Error instance
  if (error instanceof Error) {
    return error.message;
  }

  // Fallback for unknown error types
  return fallbackMessage || "An unexpected error occurred";
}

/**
 * Parse API error and extract all validation errors
 *
 * @param error - The error object from API call
 * @returns Array of error messages with field locations
 */
export function parseApiValidationErrors(error: unknown): string[] {
  if (error && typeof error === "object" && "isAxiosError" in error) {
    const axiosError = error as AxiosError<ApiErrorResponse>;

    const data = axiosError.response?.data;

    // Handle FastAPI validation errors (detail array)
    if (data?.detail && Array.isArray(data.detail)) {
      return data.detail.map((err) => {
        // Include field location if available
        const location = err.loc?.filter((l) => l !== "body").join(" → ");
        return location ? `${location}: ${err.msg}` : err.msg;
      });
    }
  }

  // Fallback to single error message
  return [parseApiError(error)];
}

/**
 * Extract HTTP status code from error
 *
 * @param error - The error object from API call
 * @returns HTTP status code or undefined
 */
export function getErrorStatusCode(error: unknown): number | undefined {
  if (error && typeof error === "object" && "isAxiosError" in error) {
    const axiosError = error as AxiosError;
    return axiosError.response?.status;
  }
  return undefined;
}

/**
 * Check if error is a network error (no response from server)
 *
 * @param error - The error object from API call
 * @returns True if network error, false otherwise
 */
export function isNetworkError(error: unknown): boolean {
  if (error && typeof error === "object" && "isAxiosError" in error) {
    const axiosError = error as AxiosError;
    return !axiosError.response;
  }
  return false;
}

/**
 * Check if error is a specific HTTP status code
 *
 * @param error - The error object from API call
 * @param statusCode - The status code to check
 * @returns True if error matches status code, false otherwise
 */
export function isStatusCode(error: unknown, statusCode: number): boolean {
  return getErrorStatusCode(error) === statusCode;
}
