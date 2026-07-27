import type { PipelineStep, QueryResponse } from '../types/api.types';

const WS_BASE = (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8080/api/v1';

export interface WSEvent {
  event: PipelineStep | string;
  data?: QueryResponse | Record<string, string>;
}

export type WSCallback = (event: WSEvent) => void;

export class QueryWebSocket {
  private ws: WebSocket | null = null;
  private onMessage: WSCallback;
  private onClose: () => void;

  constructor(onMessage: WSCallback, onClose: () => void) {
    this.onMessage = onMessage;
    this.onClose = onClose;
  }

  connect(query: string, token: string, maxResults = 10): void {
    this.ws = new WebSocket(`${WS_BASE}/ws/query`);

    this.ws.onopen = () => {
      this.ws?.send(JSON.stringify({ query, token, max_results: maxResults }));
    };

    this.ws.onmessage = (e: MessageEvent<string>) => {
      try {
        const parsed = JSON.parse(e.data) as WSEvent;
        this.onMessage(parsed);
      } catch {
        // ignore malformed frames
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      this.onClose();
    };

    this.ws.onerror = () => {
      this.onMessage({ event: 'error', data: { message: 'WebSocket connection failed' } });
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
