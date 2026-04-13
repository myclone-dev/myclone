import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useAuthStore } from "@/store/auth.store";
import type { AuthResponse, LoginCredentials, SignupData } from "./interface";

/**
 * Login mutation
 */
const login = async (credentials: LoginCredentials): Promise<AuthResponse> => {
  const { data } = await api.post<AuthResponse>("/auth/login", credentials);
  return data;
};

/**
 * Signup mutation
 */
const signup = async (signupData: SignupData): Promise<AuthResponse> => {
  const { data } = await api.post<AuthResponse>("/auth/signup", signupData);
  return data;
};

/**
 * Logout mutation
 */
const logout = async (): Promise<void> => {
  await api.post("/auth/logout");
};

/**
 * Login mutation hook
 */
export function useLogin() {
  const { setAuth } = useAuthStore();

  return useMutation({
    mutationFn: login,
    onSuccess: (data) => {
      setAuth(data.user, data.token);
    },
  });
}

/**
 * Signup mutation hook
 */
export function useSignup() {
  const { setAuth } = useAuthStore();

  return useMutation({
    mutationFn: signup,
    onSuccess: (data) => {
      setAuth(data.user, data.token);
    },
  });
}

/**
 * Logout mutation hook
 */
export function useLogout() {
  const { logout: logoutStore } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      logoutStore();
      queryClient.clear();
    },
    onError: () => {
      // Even if API call fails, clear local state
      logoutStore();
      queryClient.clear();
    },
  });
}
