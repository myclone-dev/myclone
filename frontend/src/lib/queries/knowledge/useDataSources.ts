import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { DataSourcesResponse } from "./interface";

/**
 * Fetch data sources for a persona
 */
const fetchDataSources = async (
  personaId: string,
): Promise<DataSourcesResponse> => {
  const { data } = await api.get(
    `/api/v1/ingestion/persona/${personaId}/data-sources`,
  );
  return data;
};

export const getDataSourcesQueryKey = (personaId: string) => [
  "data-sources",
  personaId,
];

/**
 * Query hook to get data sources for a persona
 */
export const useDataSources = (personaId: string | undefined) => {
  return useQuery({
    queryKey: personaId
      ? getDataSourcesQueryKey(personaId)
      : ["data-sources", "disabled"],
    queryFn: () => {
      if (!personaId) throw new Error("Persona ID required");
      return fetchDataSources(personaId);
    },
    enabled: !!personaId,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 15 * 1000, // Poll every 15 seconds
  });
};
