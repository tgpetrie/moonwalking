import useSWR from "swr";
import { fetchJson } from "../lib/api";

const DATA_URL = "/data";

export function useDataFeed() {
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    DATA_URL,
    () => fetchJson(DATA_URL),
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
