import { AxiosError } from "axios";

/**
 * Parse API error response and return user-friendly message
 * Handles common HTTP status codes and Pydantic validation errors
 */
export function getErrorMessage(error: unknown, context?: string): string {
  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    // Handle validation errors (422)
    if (status === 422) {
      if (typeof detail === "string") {
        return detail;
      }
      if (Array.isArray(detail)) {
        // Pydantic validation error format
        const messages = detail.map(
          (err: { msg?: string; loc?: (string | number)[] }) => {
            const field = err.loc?.slice(-1)[0] || "field";
            const msg = err.msg || "Invalid value";
            // Make field names more readable
            const readableField = String(field)
              .replace(/_/g, " ")
              .replace(/\b\w/g, (l) => l.toUpperCase());
            return `${readableField}: ${msg}`;
          },
        );
        return messages.join(". ");
      }
      return "Invalid input. Please check your values and try again.";
    }

    // Handle common HTTP errors
    if (status === 400) {
      return typeof detail === "string"
        ? detail
        : "Bad request. Please check your input.";
    }
    if (status === 401) {
      return "Session expired. Please log in again.";
    }
    if (status === 403) {
      return "You don't have permission to perform this action.";
    }
    if (status === 404) {
      return "The requested resource was not found.";
    }
    if (status === 409) {
      return typeof detail === "string"
        ? detail
        : "A conflict occurred. Please refresh and try again.";
    }
    if (status && status >= 500) {
      return "Server error. Please try again later.";
    }

    // Fallback for other Axios errors
    return error.message || `Request failed${status ? ` (${status})` : ""}`;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return context
    ? `Failed to ${context}. Please try again.`
    : "An unexpected error occurred. Please try again.";
}
