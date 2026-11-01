"""Unit tests for variant detection utility."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.variant_detection import detect_variants


def _notations(text):
    return [v["notation"] for v in detect_variants(text)]


class TestVariantDetection:
    def test_protein_short(self):
        variants = detect_variants("The BRAF V600E mutation was observed")
        assert any(v["notation"] == "V600E" for v in variants)

    def test_hgvs_coding(self):
        variants = detect_variants("Harboring c.1799T>A substitution")
        assert any("c." in v["notation"] for v in variants)

    def test_dbsnp(self):
        variants = detect_variants("Common SNP rs113488022 identified")
        assert any(v["notation"].startswith("rs") for v in variants)

    def test_gene_context_extracted(self):
        variants = detect_variants("BRAF V600E drives MAPK signaling")
        braf_var = next((v for v in variants if v["notation"] == "V600E"), None)
        assert braf_var is not None
        assert braf_var.get("gene") == "BRAF"

    def test_no_false_positives_on_clean_text(self):
        variants = detect_variants("Metformin improves insulin sensitivity in type 2 diabetes")
        assert len(variants) == 0

    def test_multiple_variants(self):
        text = "KRAS G12D and BRAF V600E are common oncogenic mutations"
        notations = _notations(text)
        assert len(notations) >= 2
