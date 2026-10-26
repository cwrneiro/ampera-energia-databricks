"""Driver-only Spark Column builders mirroring reco_lib, built from its shared constants.

Why not UDFs: Databricks serverless pickles Python UDFs to workers, which then cannot import a
pipeline-local module (ModuleNotFoundError: reco_lib). These builders return pure Spark Column
expressions evaluated natively on workers — nothing is pickled. reco_lib stays the tested reference
(tests/test_reconciliation.py); keep the two in sync. Spec: specs/02-reconciliation-silver.md
"""
from pyspark.sql import functions as F
import reco_lib as R

_GENERIC_LITS = [F.lit(w) for w in sorted(R._GENERIC)] + [F.lit("")]


def _deaccent_upper(col):
    return F.translate(F.upper(F.col(col)), R.ACCENTED, R.PLAIN)


def name_norm_col(col):
    """Upper, de-accent, strip punctuation, drop generic words, sort tokens (order-independent)."""
    s = F.regexp_replace(_deaccent_upper(col), r"[^A-Z0-9 ]", " ")
    toks = F.array_except(F.split(F.trim(s), r"\s+"), F.array(*_GENERIC_LITS))
    return F.array_join(F.array_sort(toks), " ")


def ceg_norm_col(col):
    """Normalize trailing unit segment ('.01'->'.1'); missing CEG ('-'/'') -> NULL."""
    t = F.trim(F.col(col))
    return F.when(t.isin("", "-"), None).otherwise(F.regexp_replace(t, r"\.0*(\d+)$", ".$1"))


def fuel_cls_col(col):
    k = _deaccent_upper(col)
    return (F.when(k.isin("HIDRAULICA", "UHE", "PCH", "CGH"), "HID")
            .when(k.isin("FOTOVOLTAICA", "UFV"), "SOL")
            .when(k.isin("EOLICA", "EOL"), "EOL")
            .when(k.isin("NUCLEAR", "UTN"), "NUC")
            .when((k == "UTE") | k.rlike("GAS|OLEO|CARVAO|BIOMASSA|BAGACO|DIESEL|TERMICA|TERM"), "THERM")
            .otherwise("OTHER"))


def sim_col(a, b):
    """Normalized Levenshtein similarity in [0,1]. a, b are Columns of already-normalized names."""
    m = F.greatest(F.length(a), F.length(b))
    return F.when(m == 0, F.lit(0.0)).otherwise(F.lit(1.0) - F.levenshtein(a, b) / m)


def numerals_col(name_norm_col):
    """Sorted numeral tokens of an already-normalized name (mirrors reco_lib.numerals)."""
    toks = F.split(name_norm_col, " ")
    return F.array_sort(F.filter(toks, lambda t: t.rlike(R.NUMERAL_RE)))


def ai_accept_col(choice, confidence, plant_id):
    """ai_decide verdict is applied (mirrors reco_lib.ai_accept); NULL -> False."""
    return F.coalesce(choice.isin(*R.AI_CHOICES) & plant_id.isNotNull() & (confidence >= R.AI_CUTOFF), F.lit(False))


def cand_hash_col(*ids):
    """sha256 of the candidate ids joined by '|', missing -> '' (mirrors reco_lib.cand_hash)."""
    return F.sha2(F.concat_ws("|", *[F.coalesce(F.col(c), F.lit("")) for c in ids]), 256)
