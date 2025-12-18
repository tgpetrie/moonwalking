import useSWR from "swr";
import { API_BASE_URL, fetchAllData } from "../api";

export function useDataFeed() {
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    `${API_BASE_URL || ""}/data`,
    fetchAllData,
    {
      refreshInterval: 15000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
    }
  );

  return {
    data,
    error,
    isLoading,
    isValidating,
    isError: !!error,
    mutate,
  };
}

export default useDataFeed;
