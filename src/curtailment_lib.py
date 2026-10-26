"""Curtailment rules behind the headline figure (spec 11). Pure: imported by notebooks/train_curtailment
(pandas) and notebooks/score_curtailment (Spark Columns), tested by tests/test_curtailment.py.

`flagged` and `value_rs` use only operators, so the same definition runs on floats, pandas Series and
Spark Columns. `lost_mwh` needs a branch and a max, so score_curtailment mirrors it with F.when /
F.greatest (keep the two in sync, like reco_lib / reco_sql).
"""
MIN_EXPECTED_CF = 0.10  # only judge hours where the plant should produce >= 10% of capacity
PRECISION_FLOOR = 0.80  # Y = best recall with precision >= 0.8 vs ONS flags -> a conservative R$ (2026-10-22)


def flagged(cf_expected, cf, y, min_cf=MIN_EXPECTED_CF):
    """Curtailed hour: enough expected output to judge, and actual < Y x expected."""
    return (cf_expected >= min_cf) & (cf < y * cf_expected)


def lost_mwh(mwh_expected, mwh, is_flagged):
    """Energy lost on a flagged hour, never negative."""
    return max(mwh_expected - mwh, 0.0) if is_flagged else 0.0


def value_rs(lost, pld):
    """Lost energy valued at the hour's PLD (R$/MWh)."""
    return lost * pld


def choose_y(rows, floor=PRECISION_FLOOR):
    """From a Y grid ({Y, precision, recall, ...} per row): best recall at precision >= floor, else most precise."""
    ok = [r for r in rows if r["precision"] >= floor]
    return max(ok, key=lambda r: r["recall"]) if ok else max(rows, key=lambda r: r["precision"])
