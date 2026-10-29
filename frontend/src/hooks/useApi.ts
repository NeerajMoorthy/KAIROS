import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Load data from the API and keep loading/error state in one place.
 *
 * Re-runs whenever `deps` change; `reload()` runs it again on demand. A
 * response that arrives after a newer request started is ignored, so a slow
 * old answer can never overwrite fresh data.
 */
export function useApi<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const latest = useRef(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  const reload = useCallback(() => {
    const request = ++latest.current;
    setLoading(true);
    loadRef.current()
      .then((result) => {
        if (request !== latest.current) return;
        setData(result);
        setError(null);
      })
      .catch((e: unknown) => {
        if (request !== latest.current) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (request === latest.current) setLoading(false);
      });
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(reload, deps);

  return { data, error, loading, reload, setData };
}
