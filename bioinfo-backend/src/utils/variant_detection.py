"""
Lightweight variant mention detection over abstract text.

Detects common notation styles:
  - Protein: V600E, K-RAS G12D, p.Val600Glu
  - HGVS coding: c.1799T>A
  - Genomic HGVS: g.140453136A>T
  - dbSNP: rs113488022

Returns a list of dicts: [{"notation": "V600E", "gene": "BRAF", "hgvs": "c.1799T>A"}]
Gene context is inferred heuristically from surrounding text (nearest uppercase word).
"""
import re
from typing import Optional

# Protein-level shorthand: single-letter + number + single-letter  (V600E)
_PROTEIN_SHORT = re.compile(
    r"\b([A-Z][a-z]{0,2})?[- ]?([A-Z])(\d{1,6})([A-Z])\b"
)

# HGVS coding / genomic
_HGVS_CODING = re.compile(
    r"\bc\.(\d+(?:[+-]\d+)?[A-Z]>[A-Z])\b"
)
_HGVS_GENOMIC = re.compile(
    r"\bg\.(\d+[A-Z]>[A-Z])\b"
)

# Three-letter protein: p.Val600Glu
_PROTEIN_THREE = re.compile(
    r"\bp\.([A-Z][a-z]{2})(\d{1,6})([A-Z][a-z]{2}|Ter)\b"
)

# dbSNP
_DBSNP = re.compile(r"\brs\d{6,}\b")

# Words that look like gene names preceding a variant (e.g. "BRAF V600E")
_GENE_BEFORE = re.compile(r"\b([A-Z][A-Z0-9\-]{1,10})\s+(?=[A-Z]\d)")


def detect_variants(text: str) -> list[dict]:
    """
    Detect genetic variant mentions in free text.

    Returns:
        List of dicts with keys: notation, gene (optional), type
    """
    results: list[dict] = []
    seen: set[str] = set()

    def add(notation: str, gene: Optional[str], variant_type: str) -> None:
        key = notation.lower()
        if key not in seen:
            seen.add(key)
            entry: dict = {"notation": notation, "type": variant_type}
            if gene:
                entry["gene"] = gene
            results.append(entry)

    # Build a gene-context map: positions of likely gene names
    gene_positions: list[tuple[int, int, str]] = [
        (m.start(), m.end(), m.group(1)) for m in _GENE_BEFORE.finditer(text)
    ]

    def nearest_gene(pos: int) -> Optional[str]:
        """Return the gene name closest (and before) the given position."""
        best: Optional[str] = None
        best_dist = 60  # only look within ~60 chars
        for gstart, gend, gname in gene_positions:
            dist = pos - gend
            if 0 <= dist < best_dist:
                best_dist = dist
                best = gname
        return best

    # Protein short (V600E)
    for m in _PROTEIN_SHORT.finditer(text):
        prefix, ref, pos_str, alt = m.group(1), m.group(2), m.group(3), m.group(4)
        notation = f"{ref}{pos_str}{alt}"
        # Use start of the ref letter (group 2), not m.start(), to avoid the optional space prefix
        ref_pos = m.start(2)
        gene = prefix.upper() if prefix else nearest_gene(ref_pos)
        add(notation, gene, "protein_short")

    # HGVS coding (c.1799T>A)
    for m in _HGVS_CODING.finditer(text):
        notation = f"c.{m.group(1)}"
        add(notation, nearest_gene(m.start()), "hgvs_coding")

    # HGVS genomic (g.140453136A>T)
    for m in _HGVS_GENOMIC.finditer(text):
        notation = f"g.{m.group(1)}"
        add(notation, nearest_gene(m.start()), "hgvs_genomic")

    # Three-letter protein (p.Val600Glu)
    for m in _PROTEIN_THREE.finditer(text):
        notation = f"p.{m.group(1)}{m.group(2)}{m.group(3)}"
        add(notation, nearest_gene(m.start()), "hgvs_protein")

    # dbSNP
    for m in _DBSNP.finditer(text):
        add(m.group(0), None, "dbsnp")

    return results
