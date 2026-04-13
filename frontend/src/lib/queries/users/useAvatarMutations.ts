import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";
import type { AxiosError } from "axios";
import { parseApiError, type ApiErrorResponse } from "@/lib/utils/apiError";
import type { UserMeResponse } from "./useUserMe";

/**
 * Response from avatar upload/delete operations
 */
export interface AvatarResponse {
  success: boolean;
  message: string;
  avatar_url?: string;
}

/**
 * Upload avatar image for the current user
 * @param file - Image file (JPEG, PNG, WebP, GIF, max 10MB)
 * @returns Promise with the new avatar URL
 */
const uploadAvatar = async (file: File): Promise<AvatarResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await api.post<AvatarResponse>(
    "/users/me/avatar",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );

  return data;
};

/**
 * Delete avatar image for the current user
 * @returns Promise with success message
 */
const deleteAvatar = async (): Promise<AvatarResponse> => {
  const { data } = await api.delete<AvatarResponse>("/users/me/avatar");
  return data;
};

/**
 * Hook to upload user avatar
 * Immediately updates cache with new avatar URL and invalidates queries
 */
export const useUploadAvatar = () => {
  const queryClient = useQueryClient();

  return useMutation<AvatarResponse, AxiosError<ApiErrorResponse>, File>({
    mutationFn: uploadAvatar,
    onSuccess: (data) => {
      // Immediately update the user cache with the new avatar URL
      // This ensures instant UI update without waiting for refetch
      if (data.avatar_url) {
        queryClient.setQueryData<UserMeResponse>(["user", "me"], (oldData) => {
          if (!oldData) return oldData;
          return { ...oldData, avatar: data.avatar_url! };
        });
      }

      // Also invalidate to ensure consistency with server
      queryClient.invalidateQueries({ queryKey: ["user"], exact: false });
    },
    onError: (error) => {
      const errorMessage = parseApiError(error, "Avatar upload failed");
      Sentry.captureException(error, {
        tags: { operation: "avatar_upload" },
        contexts: { avatar: { error: errorMessage } },
      });
    },
  });
};

/**
 * Hook to delete user avatar
 * Immediately updates cache to remove avatar and invalidates queries
 */
export const useDeleteAvatar = () => {
  const queryClient = useQueryClient();

  return useMutation<AvatarResponse, AxiosError<ApiErrorResponse>, void>({
    mutationFn: deleteAvatar,
    onSuccess: () => {
      // Immediately update the user cache to remove avatar
      // This ensures instant UI update without waiting for refetch
      queryClient.setQueryData<UserMeResponse>(["user", "me"], (oldData) => {
        if (!oldData) return oldData;
        return { ...oldData, avatar: null };
      });

      // Also invalidate to ensure consistency with server
      queryClient.invalidateQueries({ queryKey: ["user"], exact: false });
    },
    onError: (error) => {
      const errorMessage = parseApiError(error, "Avatar deletion failed");
      Sentry.captureException(error, {
        tags: { operation: "avatar_delete" },
        contexts: { avatar: { error: errorMessage } },
      });
    },
  });
};
