import { DependencyList, useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../lib/format";

export interface FetchState<T> { data: T | null; loading: boolean; error: string | null; reload: () => void }

/** Runs `fn` on mount and whenever `deps` change; exposes loading / error / reload. Ignores stale responses. */
export function useFetch<T>(fn: () => Promise<T> | Promise<null>, deps: DependencyList = []): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const seq = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    fnRef.current()
      .then((d) => { if (id === seq.current) setData(d as T | null); })
      .catch((e) => { if (id === seq.current) setError(errorMessage(e)); })
      .finally(() => { if (id === seq.current) setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, reload };
}
