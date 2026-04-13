import { create } from "zustand";
import { persist } from "zustand/middleware";
import { identifyUser, resetUserIdentity } from "@/lib/analytics/posthog";

interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  username?: string;
  account_type?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isVisitor: boolean;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
}

/**
 * Zustand store for client-side auth state
 * Persists to localStorage for session management
 * NOTE: This is CLIENT state only - use TanStack Query for server data
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      // Computed getter - always derived from user.account_type
      get isVisitor() {
        return get().user?.account_type === "visitor";
      },

      setAuth: (user, token) => {
        // Store token in localStorage for API client
        if (typeof window !== "undefined") {
          localStorage.setItem("auth_token", token);
        }
        set({ user, token, isAuthenticated: true });

        // Identify user in PostHog for session replay tracking
        identifyUser({
          id: user.id,
          email: user.email,
          name: user.name,
          username: user.username,
          account_type: user.account_type,
        });
      },

      logout: () => {
        // Clear token from localStorage
        if (typeof window !== "undefined") {
          localStorage.removeItem("auth_token");
        }
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        });

        // Reset PostHog identity to unlink future events
        resetUserIdentity();
      },
    }),
    {
      name: "auth-storage", // localStorage key
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
        // isVisitor is NOT persisted - computed from user.account_type
      }),
    },
  ),
);
