import useSWR from "swr";
import { API_BASE_URL, fetchAllData } from "../api";

export function useDataFeed() {
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    `${API_BASE_URL || ""}/api/data`,
    fetchAllData,
    {
      refreshInterval: 1500,
      refreshWhenHidden: true,
      refreshWhenOffline: true,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 0,
      errorRetryInterval: 1500,
      shouldRetryOnError: () => true,
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
