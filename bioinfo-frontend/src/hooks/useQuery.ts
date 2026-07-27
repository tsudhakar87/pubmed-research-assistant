import { useCallback, useState } from 'react';
import { postQuery } from '../services/api';
import type { QueryResponse } from '../types/api.types';

interface UseQueryResult {
  data: QueryResponse | null;
  loading: boolean;
  error: string | null;
  submit: (query: string, maxResults?: number) => Promise<void>;
  clear: () => void;
}

export function useQuery(): UseQueryResult {
  const [data, setData] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async (query: string, maxResults = 10) => {
    setLoading(true);
    setError(null);
    try {
      const result = await postQuery(query, maxResults);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  const clear = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return { data, loading, error, submit, clear };
}
