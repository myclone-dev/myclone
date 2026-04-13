import axios from "axios";
import * as Sentry from "@sentry/nextjs";
import { env } from "@/env";

// Check if running in browser
const isBrowser = typeof window !== "undefined";

/**
 * Axios instance configured with:
 * - Base URL from environment variables
 * - Request interceptor for auth token
 * - Response interceptor for 401 handling
 */
export const api = axios.create({
  baseURL: env.NEXT_PUBLIC_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true, // Include cookies in requests (for JWT auth)
});

// Request interceptor - Add auth token with priority order
api.interceptors.request.use(
  (config) => {
    if (isBrowser) {
      // Priority order:
      // 1. auth_token (localStorage) - for logged-in users in main app
      // 2. auth_token (sessionStorage) - for verified visitors in widgets
      // 3. widget_token (sessionStorage) - for anonymous widget users
      const authTokenLocalStorage = localStorage.getItem("auth_token");
      const authTokenSessionStorage = sessionStorage.getItem("auth_token");
      const widgetToken = sessionStorage.getItem("widget_token");

      const authToken = authTokenLocalStorage || authTokenSessionStorage;

      if (authToken) {
        config.headers.Authorization = `Bearer ${authToken}`;
      } else if (widgetToken) {
        config.headers.Authorization = `Bearer ${widgetToken}`;
      }
    }

    // Remove Content-Type header for FormData requests
    // Axios will automatically set the correct multipart/form-data header with boundary
    if (config.data instanceof FormData) {
      delete config.headers["Content-Type"];
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor - Handle 401 Unauthorized and track errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Track API errors in Sentry (except 401 and 404)
    const status = error.response?.status;
    const shouldTrack = status && status !== 401 && status !== 404;

    if (shouldTrack) {
      Sentry.captureException(error, {
        level: status >= 500 ? "error" : "warning",
        tags: {
          api_error: true,
          status_code: status,
          endpoint: error.config?.url,
          method: error.config?.method?.toUpperCase(),
        },
        contexts: {
          response: {
            status: error.response?.status,
            statusText: error.response?.statusText,
            data: error.response?.data,
          },
          request: {
            url: error.config?.url,
            method: error.config?.method,
            baseURL: error.config?.baseURL,
          },
        },
      });
    }

    if (status === 401 && isBrowser) {
      // Clear auth token on 401 errors
      localStorage.removeItem("auth_token");

      // Attach a flag to help components decide if they should redirect
      error.isAuthError = true;
    }
    return Promise.reject(error);
  },
);
