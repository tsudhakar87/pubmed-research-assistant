"""
Study design and organism labels from curated PubMed metadata.

PubMed's PublicationType and MeSH check tags are assigned by NLM, so they are
preferred over AI extraction whenever present. These rules return None when
the metadata doesn't settle the question; the caller then falls back to iCite
or Gemini.
"""
from typing import Dict, List, Literal, Optional

StudyDesign = Literal[
    "meta_analysis", "systematic_review", "rct", "clinical_trial",
    "cohort", "case_control", "cross_sectional", "observational",
    "case_report", "review", "animal", "in_vitro", "other",
]
Organism = Literal["human", "animal", "in_vitro", "mixed", "unknown"]

# Most specific first. Exact matches on NLM publication type names.
_PUBTYPE_EXACT: List[tuple] = [
    ("Meta-Analysis", "meta_analysis"),
    ("Systematic Review", "systematic_review"),
    ("Randomized Controlled Trial", "rct"),
    ("Randomized Controlled Trial, Veterinary", "rct"),
    ("Pragmatic Clinical Trial", "clinical_trial"),
    ("Controlled Clinical Trial", "clinical_trial"),
    ("Clinical Trial, Phase I", "clinical_trial"),
    ("Clinical Trial, Phase II", "clinical_trial"),
    ("Clinical Trial, Phase III", "clinical_trial"),
    ("Clinical Trial, Phase IV", "clinical_trial"),
    ("Clinical Trial", "clinical_trial"),
    ("Observational Study", "observational"),
    ("Case Reports", "case_report"),
    ("Scoping Review", "review"),
    ("Review", "review"),
]
_PUBTYPE_RANK = {name: i for i, (name, _) in enumerate(_PUBTYPE_EXACT)}
_PUBTYPE_DESIGN = dict(_PUBTYPE_EXACT)

# Publication types that mean "not a study": the design is "other" regardless of MeSH.
_NON_STUDY_TYPES = {
    "Published Erratum", "Retraction Notice", "Editorial", "Comment", "Letter",
    "News", "Practice Guideline", "Guideline", "Clinical Trial Protocol",
    "Expression of Concern", "Biography", "Interview", "Congress",
}

DESIGN_TIER: Dict[str, int] = {
    "meta_analysis": 1, "systematic_review": 1,
    "rct": 2,
    "clinical_trial": 3,
    "cohort": 4, "case_control": 4, "observational": 4,
    "cross_sectional": 5,
    "animal": 6,
    "in_vitro": 7, "case_report": 7,
    "review": 8,
    "other": 9,
}

CLINICAL_DESIGNS = {"meta_analysis", "systematic_review", "rct", "clinical_trial",
                    "cohort", "case_control", "cross_sectional", "observational", "case_report"}

# "Animals" is the MeSH check tag for any non-human study; species terms are a backup
_ANIMAL_TERMS = {
    "Animals", "Mice", "Rats", "Mice, Inbred C57BL", "Mice, Knockout", "Mice, Transgenic",
    "Rats, Sprague-Dawley", "Rats, Wistar", "Zebrafish", "Drosophila melanogaster",
    "Caenorhabditis elegans", "Swine", "Dogs", "Macaca mulatta", "Rabbits",
}
# NLM also tags human cell-line work with "Humans", so these separate lab studies
_CELL_TERMS = {"Cell Line", "Cell Line, Tumor", "Cells, Cultured", "Organoids", "HEK293 Cells", "HeLa Cells"}


def design_from_pubtypes(pubtypes: List[str]) -> Optional[str]:
    """Most specific study design named by the publication types, or None."""
    if any(t in _NON_STUDY_TYPES for t in pubtypes):
        if not any(t in _PUBTYPE_DESIGN for t in pubtypes):
            return "other"
    known = [t for t in pubtypes if t in _PUBTYPE_DESIGN]
    if not known:
        return None
    return _PUBTYPE_DESIGN[min(known, key=_PUBTYPE_RANK.__getitem__)]


def organism_from_mesh(mesh: List[str], design: Optional[str] = None) -> Optional[str]:
    """Human / animal / in vitro / mixed from MeSH terms, or None if untagged."""
    terms = set(mesh)
    human = "Humans" in terms
    animal = bool(terms & _ANIMAL_TERMS)
    cells = bool(terms & _CELL_TERMS)

    if human and animal:
        return "mixed"
    if animal:
        return "animal"
    if cells and design not in CLINICAL_DESIGNS:
        return "in_vitro"
    if human:
        return "human"
    return None


def organism_from_icite(human: float, animal: float, molecular_cellular: float) -> Optional[str]:
    """iCite's human/animal/molecular-cellular fractions; a label only if one clearly dominates."""
    scores = {"human": human or 0.0, "animal": animal or 0.0, "in_vitro": molecular_cellular or 0.0}
    label, best = max(scores.items(), key=lambda kv: kv[1])
    return label if best >= 0.6 else None


def design_for_organism(organism: Optional[str]) -> Optional[str]:
    """Design to use when publication types are silent but the organism is known to be non-human."""
    return {"animal": "animal", "in_vitro": "in_vitro"}.get(organism or "")
