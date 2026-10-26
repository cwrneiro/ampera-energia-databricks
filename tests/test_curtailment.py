"""Runnable check for the curtailment headline rules (spec 11): `python tests/test_curtailment.py`.

The flag, lost energy, R$ valuation and the Y-selection rule behind the 65.8 TWh / R$ 8.4 bi figure.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import curtailment_lib as C  # noqa: E402


def test_low_expected_output_is_never_judged():
    # Night / calm hour: expected CF below the 10% floor -> not curtailed, nothing lost, whatever the actual.
    assert not C.flagged(0.05, 0.0, 0.65, C.MIN_EXPECTED_CF)
    assert C.lost_mwh(0.5, 0.0, is_flagged=False) == 0.0


def test_lost_energy_never_negative():
    assert C.lost_mwh(2.0, 5.0, is_flagged=True) == 0.0


def test_worked_example():
    # cf_exp 0.5, cf 0.2, Y 0.65, 10 MW, PLD R$ 100/MWh -> flagged, 3.0 MWh lost, R$ 300.
    cap = 10
    f = C.flagged(0.5, 0.2, 0.65, C.MIN_EXPECTED_CF)
    lost = C.lost_mwh(0.5 * cap, 0.2 * cap, f)
    assert f and lost == 3.0 and C.value_rs(lost, 100) == 300.0
    assert not C.flagged(0.5, 0.4, 0.65, C.MIN_EXPECTED_CF)  # 0.4 >= 0.65 x 0.5: a normal shortfall


def test_choose_y():
    # Best recall among rows with precision >= 0.8 ...
    grid = [{"Y": 0.5, "precision": 0.95, "recall": 0.30}, {"Y": 0.65, "precision": 0.82, "recall": 0.55},
            {"Y": 0.8, "precision": 0.70, "recall": 0.80}]
    assert C.choose_y(grid)["Y"] == 0.65
    # ... else the most precise row.
    low = [{"Y": 0.5, "precision": 0.6, "recall": 0.3}, {"Y": 0.65, "precision": 0.7, "recall": 0.2}]
    assert C.choose_y(low)["Y"] == 0.65


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PASS")
