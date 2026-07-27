import type {
  AuthResponse,
  CompareResult,
  HistoryItem,
  PaperDetail,
  QueryResponse,
  SimilarQuery,
  VariantScore,
} from '../types/api.types';

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8080/api/v1';

function getToken(): string | null {
  return localStorage.getItem('access_token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as Record<string, string>;
    throw new ApiError(res.status, body['message'] ?? res.statusText, body);
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function authGoogle(idToken: string): Promise<AuthResponse> {
  return request<AuthResponse>('/auth/google', {
    method: 'POST',
    body: JSON.stringify({ id_token: idToken }),
  });
}

export async function getMe(): Promise<AuthResponse['user']> {
  return request('/auth/me');
}

// ── Query ─────────────────────────────────────────────────────────────────────

export async function postQuery(query: string, maxResults = 10): Promise<QueryResponse> {
  return request<QueryResponse>('/query/research', {
    method: 'POST',
    body: JSON.stringify({ query, max_results: maxResults }),
  });
}

export async function getQueryHistory(limit = 50): Promise<{ queries: HistoryItem[] }> {
  return request(`/query/history?limit=${limit}`);
}

export async function reopenQuery(queryId: string): Promise<QueryResponse> {
  return request(`/query/history/${queryId}`);
}

export async function getSimilarQueries(
  q: string,
  limit = 5,
): Promise<{ queries: SimilarQuery[]; method: string }> {
  return request(`/query/similar?q=${encodeURIComponent(q)}&limit=${limit}`);
}

// ── Papers ────────────────────────────────────────────────────────────────────

export async function getPaper(pmid: string): Promise<PaperDetail> {
  return request(`/papers/${pmid}`);
}

export async function comparePapers(pmids: string[]): Promise<CompareResult> {
  return request<CompareResult>('/papers/compare', {
    method: 'POST',
    body: JSON.stringify({ pmids }),
  });
}

export async function scoreVariant(
  pmid: string,
  variant: string,
  gene?: string,
): Promise<VariantScore> {
  const params = new URLSearchParams({ variant });
  if (gene) params.append('gene', gene);
  return request(`/papers/${pmid}/score-variant?${params}`);
}
