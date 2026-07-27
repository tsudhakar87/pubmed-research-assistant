export interface PaperResult {
  title: string;
  authors: string[];
  abstract?: string;
  journal?: string;
  publication_date?: string;
  pmid?: string;
  doi?: string;
  keywords: string[];
  relevance_score?: number;
  detected_variants?: VariantMention[];
}

export interface VariantMention {
  notation: string;
  type: string;
  gene?: string;
}

export interface QueryResponse {
  query_id: string;
  original_query: string;
  refined_query?: string;
  query_type?: string;
  status: string;
  literature_results: PaperResult[];
  total_results: number;
  processing_time: number;
  ai_summary?: string;
  metadata?: Record<string, unknown>;
}

export interface HistoryItem {
  query_id: string;
  original_query: string;
  query_type?: string;
  total_results: number;
  created_at: string;
  has_ai_summary: boolean;
}

export interface UserInfo {
  id: string;
  email: string;
  name?: string;
  picture_url?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

export interface PaperDetail {
  pmid: string;
  title: string;
  authors: string[];
  journal?: string;
  publication_date?: string;
  abstract: string;
  doi?: string;
  keywords: string[];
  detected_variants: VariantMention[];
  pubmed_url: string;
}

export interface CompareResult {
  papers: PaperDetail[];
  ai_diff_synthesis: string;
}

export interface VariantScore {
  pmid: string;
  variant: string;
  gene?: string;
  score: number;
  classification: 'disruptive' | 'moderate' | 'neutral';
  sequence_context?: string;
  model: string;
  source: string;
}

export interface SimilarQuery {
  query_id: string;
  original_query: string;
  created_at: string;
  total_results: number;
  similarity?: number;
}

export type PipelineStep =
  | 'idle'
  | 'classifying'
  | 'searching_pubmed'
  | 'retrieving_abstracts'
  | 'synthesizing'
  | 'done'
  | 'error'
  | 'scoring_variant';
