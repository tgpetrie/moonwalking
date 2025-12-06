import { useEffect, useState } from "react";
import { fetchAllData } from "../api";

export default function useUnifiedData() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [errs, setErrs] = useState({});

  useEffect(() => {
    let alive = true;

    const fetchData = async () => {
      try {
        const json = await fetchAllData();
        if (!alive) return;
        setData(json.data || {});
        setErrs(json.errors || {});
        setLoading(false);
      } catch (e) {
        if (!alive) return;
        setErrs((prev) => ({ ...prev, fetch: e.message }));
        setLoading(false);
      }
    };

    fetchData();
    const id = setInterval(fetchData, 5000); // 5s

    // allow external components to trigger an immediate refresh by dispatching
    // a `unified-data-refresh` event on window
    const onRefresh = () => {
      fetchData();
    };
    window.addEventListener("unified-data-refresh", onRefresh);

    return () => {
      alive = false;
      clearInterval(id);
      window.removeEventListener("unified-data-refresh", onRefresh);
    };
  }, []);

  return { data, loading, errs };
}
