import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { AxiosError } from "axios";
import { parseApiError, type ApiErrorResponse } from "@/lib/utils/apiError";
import {
  trackDashboardOperation,
  trackFileUpload,
} from "@/lib/monitoring/sentry";

/**
 * Response from persona avatar upload/delete operations
 */
export interface PersonaAvatarResponse {
  success: boolean;
  message: string;
  persona_avatar_url?: string;
}

/**
 * Upload avatar image for a specific persona
 * @param personaId - The persona ID
 * @param file - Image file (JPEG, PNG, WebP, max 10MB)
 * @returns Promise with the new avatar URL
 */
const uploadPersonaAvatar = async (
  personaId: string,
  file: File,
): Promise<PersonaAvatarResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await api.post<PersonaAvatarResponse>(
    `/personas/${personaId}/avatar`,
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
 * Delete avatar image for a specific persona
 * @param personaId - The persona ID
 * @returns Promise with success message
 */
const deletePersonaAvatar = async (
  personaId: string,
): Promise<PersonaAvatarResponse> => {
  const { data } = await api.delete<PersonaAvatarResponse>(
    `/personas/${personaId}/avatar`,
  );
  return data;
};

/**
 * Hook to upload persona avatar
 * Immediately updates cache with new avatar URL and invalidates queries
 */
export const useUploadPersonaAvatar = () => {
  const queryClient = useQueryClient();

  return useMutation<
    PersonaAvatarResponse,
    AxiosError<ApiErrorResponse>,
    { personaId: string; file: File }
  >({
    mutationFn: ({ personaId, file }) => {
      // Track upload start
      trackDashboardOperation("persona_avatar_upload", "started", {
        personaId,
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
      });
      trackFileUpload("avatar", "started", {
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
        action: "persona_avatar_upload",
      });

      return uploadPersonaAvatar(personaId, file);
    },
    onSuccess: (data, variables) => {
      // Track upload success
      trackDashboardOperation("persona_avatar_upload", "success", {
        personaId: variables.personaId,
        fileName: variables.file.name,
        avatarUrl: data.persona_avatar_url,
      });
      trackFileUpload("avatar", "success", {
        fileName: variables.file.name,
        action: "persona_avatar_upload",
      });

      // Invalidate persona-related queries to refresh data
      queryClient.invalidateQueries({ queryKey: ["personas"], exact: false });
      queryClient.invalidateQueries({
        queryKey: ["persona", variables.personaId],
        exact: false,
      });
    },
    onError: (error, variables) => {
      const errorMessage = parseApiError(error, "Persona avatar upload failed");

      // Track upload error
      trackDashboardOperation("persona_avatar_upload", "error", {
        personaId: variables.personaId,
        fileName: variables.file.name,
        error: errorMessage,
      });
      trackFileUpload("avatar", "error", {
        fileName: variables.file.name,
        error: errorMessage,
        action: "persona_avatar_upload",
      });
    },
  });
};

/**
 * Hook to delete persona avatar
 * Immediately updates cache to remove avatar and invalidates queries
 */
export const useDeletePersonaAvatar = () => {
  const queryClient = useQueryClient();

  return useMutation<
    PersonaAvatarResponse,
    AxiosError<ApiErrorResponse>,
    string
  >({
    mutationFn: (personaId) => {
      // Track delete start
      trackDashboardOperation("persona_avatar_delete", "started", {
        personaId,
      });

      return deletePersonaAvatar(personaId);
    },
    onSuccess: (_data, personaId) => {
      // Track delete success
      trackDashboardOperation("persona_avatar_delete", "success", {
        personaId,
      });

      // Invalidate persona-related queries to refresh data
      queryClient.invalidateQueries({ queryKey: ["personas"], exact: false });
      queryClient.invalidateQueries({
        queryKey: ["persona", personaId],
        exact: false,
      });
    },
    onError: (error, personaId) => {
      const errorMessage = parseApiError(
        error,
        "Persona avatar deletion failed",
      );

      // Track delete error
      trackDashboardOperation("persona_avatar_delete", "error", {
        personaId,
        error: errorMessage,
      });
    },
  });
};
