import { useCallback, useRef, useState } from 'react';
import { QueryWebSocket } from '../services/websocket';
import type { PipelineStep, QueryResponse } from '../types/api.types';

interface UseWebSocketResult {
  step: PipelineStep;
  result: QueryResponse | null;
  error: string | null;
  isRunning: boolean;
  submitQuery: (query: string, token: string, maxResults?: number) => void;
  loadCachedResult: (response: QueryResponse) => void;
  cancel: () => void;
}

const STEP_ORDER: PipelineStep[] = [
  'idle',
  'classifying',
  'searching_pubmed',
  'retrieving_abstracts',
  'synthesizing',
  'done',
];

// Close code the backend uses when the JWT in the first message is invalid/expired
const WS_UNAUTHORIZED = 4001;

export function useWebSocket(onUnauthorized?: () => void): UseWebSocketResult {
  const [step, setStep] = useState<PipelineStep>('idle');
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef<QueryWebSocket | null>(null);

  const cancel = useCallback(() => {
    wsRef.current?.disconnect();
    setIsRunning(false);
    setStep('idle');
  }, []);

  const submitQuery = useCallback(
    (query: string, token: string, maxResults = 10) => {
      // Clean up previous connection
      wsRef.current?.disconnect();
      setResult(null);
      setError(null);
      setStep('classifying');
      setIsRunning(true);

      const ws = new QueryWebSocket(
        (event) => {
          const evt = event.event as PipelineStep;
          if (evt === 'done') {
            setResult(event.data as QueryResponse);
            setStep('done');
            setIsRunning(false);
          } else if (evt === 'error') {
            const data = event.data as Record<string, string>;
            setError(data?.message ?? 'An error occurred');
            setStep('error');
            setIsRunning(false);
          } else if (STEP_ORDER.includes(evt)) {
            setStep(evt);
          }
        },
        (code) => {
          setIsRunning(false);
          if (code === WS_UNAUTHORIZED) onUnauthorized?.();
        },
      );

      wsRef.current = ws;
      ws.connect(query, token, maxResults);
    },
    [onUnauthorized],
  );

  const loadCachedResult = useCallback((response: QueryResponse) => {
    wsRef.current?.disconnect();
    setResult(response);
    setStep('done');
    setIsRunning(false);
    setError(null);
  }, []);

  return { step, result, error, isRunning, submitQuery, loadCachedResult, cancel };
}
