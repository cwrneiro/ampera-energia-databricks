"""Runnable check for the reconciliation matching primitives (SUCCESS_CRITERIA #9).

No cluster, no framework: `python tests/test_reconciliation.py`. Fails loudly if the logic breaks.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "transformations"))
import reco_lib as R  # noqa: E402


def test_normalize_ceg():
    # ONS ends .01, SIGA ends .1 — normalization is what makes them join.
    assert R.normalize_ceg("UHE.PH.AM.000190-2.01") == "UHE.PH.AM.000190-2.1"
    assert R.normalize_ceg("PCH.PH.MG.000008-6.1") == "PCH.PH.MG.000008-6.1"
    assert R.normalize_ceg("UHE.PH.AM.000190-2.01") == R.normalize_ceg("UHE.PH.AM.000190-2.1")
    assert R.normalize_ceg("-") is None
    assert R.normalize_ceg("") is None
    assert R.normalize_ceg(None) is None


def test_normalize_name():
    assert R.normalize_name("UHE Balbina") == "BALBINA"
    assert R.normalize_name("Usina Hidrelétrica Balbina") == "BALBINA"
    # token-order independent
    assert R.normalize_name("Santa Clara") == R.normalize_name("Clara Santa")


def test_fuel_class():
    assert R.fuel_class("Hidráulica") == "HID"
    assert R.fuel_class("UHE") == "HID"
    assert R.fuel_class("UFV") == R.fuel_class("Fotovoltaica") == "SOL"
    assert R.fuel_class("UTE") == "THERM"
    assert R.fuel_class("Bagaço de Cana") == "THERM"
    assert R.fuel_class(None) == "OTHER"


def test_name_sim_crosses_threshold():
    # a realistic name variant should clear the fuzzy bar...
    a = R.normalize_name("Parque Eólico Serra do Vento")
    b = R.normalize_name("EOL Serra do Vento")
    assert R.name_sim(a, b) >= R.THRESHOLD, R.name_sim(a, b)
    # ...and unrelated plants must not.
    assert R.name_sim(R.normalize_name("Balbina"), R.normalize_name("Itaipu")) < R.THRESHOLD


def test_numbered_plants_never_fuzzy_match():
    # Real false match found in the data: ONS "Prosperidade III" scored 0.94 against SIGA "Prosperidade II".
    a, b = R.normalize_name("Prosperidade III"), R.normalize_name("Prosperidade II")
    assert R.name_sim(a, b) >= R.THRESHOLD          # edit distance alone can't tell them apart...
    assert not R.numerals_match(a, b)               # ...the numeral guard does
    assert R.numerals_match(R.normalize_name("UFV Sol do Sertão 2"), R.normalize_name("Sol do Sertão 2"))
    assert not R.numerals_match(R.normalize_name("Conj. Ventos 1"), R.normalize_name("Ventos 2"))
    assert R.numerals_match(R.normalize_name("Balbina"), R.normalize_name("UHE Balbina"))  # no numerals


def test_ai_accept():
    # The one acceptance rule the pipeline and the blind eval share (spec 12): a real candidate at or
    # above the cutoff; "nenhum" or a missing confidence is never applied.
    assert R.ai_accept("A", 0.95, "X.1")
    assert not R.ai_accept("A", 0.89, "X.1")
    assert not R.ai_accept("nenhum", 0.99, None)
    assert not R.ai_accept("B", None, "Y.1")
    assert not R.ai_accept(None, 0.99, None)
    assert not R.ai_accept("C", 0.99, None)  # chose a slot with no candidate (fewer than 3 in the UF)


def test_verdict_key():
    # A stored verdict is reused only for the same plant, candidate set and prompt (spec 12).
    k = R.verdict_key("ONS-1", ["X.1", "Y.1", None], "prompt v1")
    assert k == R.verdict_key("ONS-1", ["X.1", "Y.1", None], "prompt v1")
    assert k[0] == "ONS-1"
    assert k != R.verdict_key("ONS-1", ["X.1", "Z.1", None], "prompt v1")   # a candidate changed
    assert k != R.verdict_key("ONS-1", ["X.1", "Y.1", None], "prompt v2")   # the prompt changed
    assert k != R.verdict_key("ONS-1", ["Y.1", "X.1", None], "prompt v1")   # A/B/C order is part of the question


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PASS")
