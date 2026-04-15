import { useState, useEffect, useCallback, useRef } from 'react';

interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

export function useQuery<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList = []
): QueryState<T> & { refetch: () => void } {
  const [state, setState] = useState<QueryState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const [trigger, setTrigger] = useState(0);

  const refetch = useCallback(() => {
    setTrigger((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    setState((prev) => ({ ...prev, loading: true, error: null }));

    fetcherRef
      .current()
      .then((data) => {
        if (!cancelled) {
          setState({ data, loading: false, error: null });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            data: null,
            loading: false,
            error: err instanceof Error ? err : new Error(String(err)),
          });
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, trigger]);

  return { ...state, refetch };
}
