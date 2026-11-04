// Shared labels, colors and ordering for the evidence views (panel, timeline, cards)
import type { Organism, PaperResult, Stance, StudyDesign } from '../types/api.types';

export const STANCE_ORDER: Stance[] = ['supports', 'mixed', 'no_effect', 'contradicts'];

export const STANCE_LABEL: Record<Stance, string> = {
  supports: 'Supports',
  mixed: 'Mixed',
  no_effect: 'No effect',
  contradicts: 'Contradicts',
  not_applicable: 'Doesn’t test it',
};

export const STANCE_COLOR: Record<Stance, string> = {
  supports: '#1f7a6c',
  mixed: '#c98a2e',
  no_effect: '#9aa1ab',
  contradicts: '#a3473a',
  not_applicable: '#dbd6c8',
};

export const ORGANISM_LABEL: Record<Organism, string> = {
  human: 'Human',
  animal: 'Animal',
  in_vitro: 'In vitro',
  mixed: 'Human + animal',
  unknown: 'Unknown',
};

export const ORGANISM_COLOR: Record<Organism, string> = {
  human: '#1f7a6c',
  animal: '#c98a2e',
  in_vitro: '#6b5b95',
  mixed: '#1c2430',
  unknown: '#9aa1ab',
};

export const DESIGN_LABEL: Record<StudyDesign, string> = {
  meta_analysis: 'Meta-analysis',
  systematic_review: 'Systematic review',
  rct: 'RCT',
  clinical_trial: 'Clinical trial',
  cohort: 'Cohort',
  case_control: 'Case-control',
  cross_sectional: 'Cross-sectional',
  observational: 'Observational',
  case_report: 'Case report',
  review: 'Review',
  animal: 'Animal study',
  in_vitro: 'In vitro',
  other: 'Other',
};

// Lower is stronger. Mirrors DESIGN_TIER in the backend's study_design.py
export const DESIGN_TIER: Record<StudyDesign, number> = {
  meta_analysis: 1, systematic_review: 1,
  rct: 2,
  clinical_trial: 3,
  cohort: 4, case_control: 4, observational: 4,
  cross_sectional: 5,
  animal: 6,
  in_vitro: 7, case_report: 7,
  review: 8,
  other: 9,
};

export function isPreprint(p: PaperResult): boolean {
  return p.source === 'biorxiv' || p.source === 'medrxiv';
}

// "Strongest evidence" ordering: design tier, then sample size, then citation influence
export function compareEvidenceStrength(a: PaperResult, b: PaperResult): number {
  const ea = a.evidence, eb = b.evidence;
  if (!ea || !eb) return ea ? -1 : eb ? 1 : 0;
  return (
    DESIGN_TIER[ea.design] - DESIGN_TIER[eb.design] ||
    (eb.sample_size ?? 0) - (ea.sample_size ?? 0) ||
    (b.relative_citation_ratio ?? 0) - (a.relative_citation_ratio ?? 0)
  );
}
