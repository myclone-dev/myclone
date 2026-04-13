/**
 * Custom Domains TanStack Query hooks
 *
 * Manages custom domain operations for white-label deployments.
 * Similar to Delphi's standalone integration feature.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

import type {
  AddCustomDomainRequest,
  AddCustomDomainResponse,
  CustomDomainListResponse,
  CustomDomainResponse,
  VerifyDomainResponse,
} from "./interface";

// Query keys
export const getCustomDomainsQueryKey = () => ["custom-domains"];
export const getCustomDomainQueryKey = (domainId: string) => [
  "custom-domains",
  domainId,
];

// Fetch functions

const fetchCustomDomains = async (): Promise<CustomDomainListResponse> => {
  const response = await api.get<CustomDomainListResponse>("/custom-domains");
  return response.data;
};

const fetchCustomDomain = async (
  domainId: string,
): Promise<CustomDomainResponse> => {
  const response = await api.get<CustomDomainResponse>(
    `/custom-domains/${domainId}`,
  );
  return response.data;
};

const addCustomDomain = async (
  request: AddCustomDomainRequest,
): Promise<AddCustomDomainResponse> => {
  try {
    const response = await api.post<AddCustomDomainResponse>(
      "/custom-domains",
      request,
    );
    return response.data;
  } catch (error) {
    // Extract meaningful error message from backend response
    if (error && typeof error === "object" && "response" in error) {
      const axiosError = error as {
        response?: { status?: number; data?: { detail?: string } };
      };
      const status = axiosError.response?.status;
      const detail = axiosError.response?.data?.detail;

      if (status === 409) {
        // Domain conflict - provide actionable guidance
        if (detail?.includes("already in use by another project")) {
          throw new Error(
            "This domain is already connected to another Vercel project. " +
              "Please remove it from the other project first, or use a different domain.",
          );
        }
        throw new Error(
          detail || "This domain is already registered in our system.",
        );
      }

      if (status === 503) {
        throw new Error(
          detail ||
            "Custom domain feature is temporarily unavailable. Please try again later.",
        );
      }

      if (status === 400) {
        throw new Error(detail || "Invalid domain format.");
      }

      if (detail) {
        throw new Error(detail);
      }
    }
    throw error;
  }
};

const verifyCustomDomain = async (
  domainId: string,
): Promise<VerifyDomainResponse> => {
  const response = await api.post<VerifyDomainResponse>(
    `/custom-domains/${domainId}/verify`,
  );
  return response.data;
};

const deleteCustomDomain = async (domainId: string): Promise<void> => {
  await api.delete(`/custom-domains/${domainId}`);
};

// Query hooks

/**
 * Hook to fetch all custom domains for the current user
 */
export const useCustomDomains = () => {
  return useQuery({
    queryKey: getCustomDomainsQueryKey(),
    queryFn: fetchCustomDomains,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 1,
  });
};

/**
 * Hook to fetch a specific custom domain
 */
export const useCustomDomain = (domainId: string | null) => {
  return useQuery({
    queryKey: domainId ? getCustomDomainQueryKey(domainId) : ["custom-domains"],
    queryFn: () => {
      if (!domainId) throw new Error("Domain ID required");
      return fetchCustomDomain(domainId);
    },
    enabled: !!domainId,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
};

// Mutation hooks

/**
 * Hook to add a new custom domain
 */
export const useAddCustomDomain = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: AddCustomDomainRequest) => {
      trackDashboardOperation("custom_domain_add", "started", {
        domain: request.domain,
      });

      try {
        const result = await addCustomDomain(request);
        trackDashboardOperation("custom_domain_add", "success", {
          domain: request.domain,
          domainId: result.domain.id,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("custom_domain_add", "error", {
          domain: request.domain,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      // Add new domain to cache
      queryClient.setQueryData<CustomDomainListResponse>(
        getCustomDomainsQueryKey(),
        (oldData) => {
          if (!oldData) {
            return {
              domains: [data.domain],
              total: 1,
            };
          }
          return {
            domains: [data.domain, ...oldData.domains],
            total: oldData.total + 1,
          };
        },
      );
    },
    onError: (error: Error) => {
      console.error("Failed to add custom domain:", error.message);
    },
  });
};

/**
 * Hook to verify a custom domain
 */
export const useVerifyCustomDomain = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (domainId: string) => {
      trackDashboardOperation("custom_domain_verify", "started", {
        domainId,
      });

      try {
        const result = await verifyCustomDomain(domainId);
        trackDashboardOperation("custom_domain_verify", "success", {
          domainId,
          verified: result.verified,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("custom_domain_verify", "error", {
          domainId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data, domainId) => {
      // Update domain in cache
      queryClient.setQueryData<CustomDomainListResponse>(
        getCustomDomainsQueryKey(),
        (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            domains: oldData.domains.map((d) =>
              d.id === domainId ? data.domain : d,
            ),
          };
        },
      );

      // Update individual domain cache
      queryClient.setQueryData(getCustomDomainQueryKey(domainId), data.domain);

      // Ensure UI reflects latest server state
      queryClient.invalidateQueries({ queryKey: getCustomDomainsQueryKey() });
      queryClient.invalidateQueries({
        queryKey: getCustomDomainQueryKey(domainId),
      });
    },
    onError: (error: Error) => {
      console.error("Failed to verify domain:", error.message);
    },
  });
};

/**
 * Hook to delete a custom domain
 */
export const useDeleteCustomDomain = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (domainId: string) => {
      trackDashboardOperation("custom_domain_delete", "started", {
        domainId,
      });

      try {
        await deleteCustomDomain(domainId);
        trackDashboardOperation("custom_domain_delete", "success", {
          domainId,
        });
      } catch (error) {
        trackDashboardOperation("custom_domain_delete", "error", {
          domainId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (_, domainId) => {
      // Remove domain from cache
      queryClient.setQueryData<CustomDomainListResponse>(
        getCustomDomainsQueryKey(),
        (oldData) => {
          if (!oldData) return oldData;
          return {
            domains: oldData.domains.filter((d) => d.id !== domainId),
            total: Math.max(0, oldData.total - 1),
          };
        },
      );

      // Remove individual domain cache
      queryClient.removeQueries({
        queryKey: getCustomDomainQueryKey(domainId),
      });

      // Force refetch to align with backend state
      queryClient.invalidateQueries({ queryKey: getCustomDomainsQueryKey() });
    },
    onError: (error: Error) => {
      console.error("Failed to delete domain:", error.message);
    },
  });
};
