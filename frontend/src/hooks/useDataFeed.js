import useSWR from "swr";
import { fetchAllData } from "../api";

export function useDataFeed() {
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    "/data",
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
