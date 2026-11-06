export interface PaperResult {
  title: string;
  authors: string[];
  abstract?: string;
  journal?: string;
  publication_date?: string;
  pmid?: string;
  doi?: string;
  keywords: string[];
  // Cosine similarity to the query (0–1). Missing when embeddings were unavailable.
  relevance_score?: number;
  source?: PaperSource;
  // Citation number used by the AI synthesis ([ref]); fixed backend ranking order
  ref?: number;
  publication_types?: string[];
  mesh_terms?: string[];
  trial_ids?: string[];
  citation_count?: number | null;
  relative_citation_ratio?: number | null;
  evidence?: Evidence | null;
  detected_variants?: VariantMention[];
}

export type PaperSource = 'pubmed' | 'biorxiv' | 'medrxiv';

export type Stance = 'supports' | 'contradicts' | 'mixed' | 'no_effect' | 'not_applicable';
export type StudyDesign =
  | 'meta_analysis' | 'systematic_review' | 'rct' | 'clinical_trial'
  | 'cohort' | 'case_control' | 'cross_sectional' | 'observational'
  | 'case_report' | 'review' | 'animal' | 'in_vitro' | 'other';
export type Organism = 'human' | 'animal' | 'in_vitro' | 'mixed' | 'unknown';

export interface Evidence {
  design: StudyDesign;
  design_source: 'pubmed' | 'ai';
  organism: Organism;
  organism_source: 'pubmed' | 'icite' | 'ai';
  sample_size?: number | null;
  population?: string | null;
  intervention?: string | null;
  outcome?: string | null;
  stance: Stance;
  key_finding: string;
  // Verbatim from the abstract; null when the model's quote couldn't be found there
  finding_quote?: string | null;
  verified: boolean;
}

export interface EvidenceSummary {
  question: string;
  answerable: boolean;
  papers_with_evidence: number;
  stance_counts: Partial<Record<Stance, number>>;
  stance_by_organism: Partial<Record<Organism, Partial<Record<Stance, number>>>>;
  design_counts: Partial<Record<StudyDesign, number>>;
  by_year: Array<{ year: number; total: number } & Partial<Record<Stance, number>>>;
  gaps: string[];
  largest_study?: { ref: number; n: number; design: StudyDesign } | null;
  latest_rct_year?: number | null;
  preprint_count: number;
}

export interface VariantMention {
  notation: string;
  type: string;
  gene?: string;
  // Nucleotide context around the variant. Abstract-text detection never
  // populates these — scoring is only available when supplied explicitly.
  ref_sequence?: string;
  alt_sequence?: string;
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
  evidence_summary?: EvidenceSummary | null;
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
  delta_log_likelihood: number;
  ref_log_likelihood: number;
  alt_log_likelihood: number;
  classification: 'disruptive' | 'moderate' | 'neutral';
  ref_sequence: string;
  alt_sequence: string;
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
  | 'searching_preprints'
  | 'retrieving_abstracts'
  | 'scoring_relevance'
  | 'extracting_evidence'
  | 'synthesizing'
  | 'papers_ready'
  | 'done'
  | 'error'
  | 'scoring_variant';
