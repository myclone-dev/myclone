import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { PersonaMonetizationResponse, PricingDisplay } from "./interface";
import { formatPrice } from "./interface";

/**
 * Query key for persona monetization
 */
export const getPersonaMonetizationQueryKey = (personaId: string) => [
  "persona-monetization",
  personaId,
];

/**
 * Fetch persona monetization settings (public endpoint - no auth required)
 */
const fetchPersonaMonetization = async (
  personaId: string,
): Promise<PersonaMonetizationResponse | null> => {
  const response = await api.get<PersonaMonetizationResponse>(
    `/stripe/personas/${personaId}/monetization`,
  );
  return response.data;
};

/**
 * Hook to get persona monetization settings
 * Public endpoint - works for both authenticated and unauthenticated users
 */
export const useGetPersonaMonetization = (personaId: string | null) => {
  return useQuery({
    queryKey: personaId
      ? getPersonaMonetizationQueryKey(personaId)
      : ["persona-monetization", "disabled"],
    queryFn: () => {
      if (!personaId) throw new Error("Persona ID is required");
      return fetchPersonaMonetization(personaId);
    },
    enabled: !!personaId,
    staleTime: 10 * 60 * 1000, // 10 minutes
    retry: 1,
  });
};

/**
 * Helper hook that returns formatted pricing display data
 */
export const usePersonaPricingDisplay = (
  personaId: string | null,
): PricingDisplay => {
  const { data: pricing } = useGetPersonaMonetization(personaId);

  if (!pricing || pricing.pricing_model === "free") {
    return { isFree: true };
  }

  return {
    isFree: false,
    priceDisplay: formatPrice(pricing.price_cents, pricing.currency),
    model: pricing.pricing_model,
    duration: pricing.access_duration_days || undefined,
  };
};
