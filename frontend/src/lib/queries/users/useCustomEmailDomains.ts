/**
 * Custom Email Domain API hooks
 *
 * Manages custom email domains for whitelabel email sending.
 * Enterprise users can send verification/OTP emails from their own domain.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api/client";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

import type {
  CreateEmailDomainRequest,
  CustomEmailDomain,
  CustomEmailDomainListResponse,
  UpdateEmailDomainRequest,
} from "./interface";

// ============================================================================
// Query Keys
// ============================================================================

export const emailDomainKeys = {
  all: ["email-domains"] as const,
  detail: (id: string) => ["email-domains", id] as const,
};

// ============================================================================
// Queries
// ============================================================================

/**
 * List all custom email domains for the current user
 */
export function useCustomEmailDomains() {
  return useQuery({
    queryKey: emailDomainKeys.all,
    queryFn: async () => {
      const { data } = await api.get<CustomEmailDomainListResponse>(
        "/users/me/email-domains",
      );
      return data.domains;
    },
    staleTime: 60 * 1000, // 1 minute
  });
}

/**
 * Get a specific email domain by ID
 */
export function useCustomEmailDomain(domainId: string | null) {
  return useQuery({
    queryKey: domainId
      ? emailDomainKeys.detail(domainId)
      : ["email-domains", "none"],
    queryFn: async () => {
      if (!domainId) return null;
      const { data } = await api.get<CustomEmailDomain>(
        `/users/me/email-domains/${domainId}`,
      );
      return data;
    },
    enabled: !!domainId,
    staleTime: 30 * 1000, // 30 seconds
  });
}

// ============================================================================
// Mutations
// ============================================================================

/**
 * Add a new custom email domain
 */
export function useAddCustomEmailDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CreateEmailDomainRequest) => {
      trackDashboardOperation("email_domain_create", "started", {
        domain: request.domain,
      });

      const { data } = await api.post<CustomEmailDomain>(
        "/users/me/email-domains",
        request,
      );
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: emailDomainKeys.all });
      trackDashboardOperation("email_domain_create", "success", {
        domain: data.domain,
      });
      toast.success("Email domain added! Configure the DNS records below.");
    },
    onError: (error: Error) => {
      trackDashboardOperation("email_domain_create", "error", {
        error: error.message,
      });
      toast.error(error.message || "Failed to add email domain");
    },
  });
}

/**
 * Verify an email domain's DNS records
 */
export function useVerifyEmailDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (domainId: string) => {
      trackDashboardOperation("email_domain_verify", "started", { domainId });

      const { data } = await api.post<CustomEmailDomain>(
        `/users/me/email-domains/${domainId}/verify`,
      );
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: emailDomainKeys.all });
      trackDashboardOperation("email_domain_verify", "success", {
        domain: data.domain,
        status: data.status,
      });

      if (data.status === "verified") {
        toast.success(
          "Domain verified! Emails will now be sent from your domain.",
        );
      } else if (data.status === "failed") {
        toast.error(
          "Domain verification failed. Please check your DNS records.",
        );
      } else {
        toast.info(
          "Verification in progress. DNS propagation can take up to 48 hours.",
        );
      }
    },
    onError: (error: Error) => {
      trackDashboardOperation("email_domain_verify", "error", {
        error: error.message,
      });
      toast.error(error.message || "Verification failed");
    },
  });
}

/**
 * Update an email domain's settings
 */
export function useUpdateEmailDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      domainId,
      request,
    }: {
      domainId: string;
      request: UpdateEmailDomainRequest;
    }) => {
      const { data } = await api.patch<CustomEmailDomain>(
        `/users/me/email-domains/${domainId}`,
        request,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emailDomainKeys.all });
      toast.success("Email domain settings updated");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to update email domain");
    },
  });
}

/**
 * Delete a custom email domain
 */
export function useDeleteEmailDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (domainId: string) => {
      trackDashboardOperation("email_domain_delete", "started", { domainId });

      await api.delete(`/users/me/email-domains/${domainId}`);
      return domainId;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emailDomainKeys.all });
      trackDashboardOperation("email_domain_delete", "success", {});
      toast.success("Email domain removed");
    },
    onError: (error: Error) => {
      trackDashboardOperation("email_domain_delete", "error", {
        error: error.message,
      });
      toast.error(error.message || "Failed to remove email domain");
    },
  });
}
