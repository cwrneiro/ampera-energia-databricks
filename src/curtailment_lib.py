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


MONITOR_MONTHS = 3  # drift check window: the trailing labeled months (spec 18)


def drift_reasons(m, floor=PRECISION_FLOOR):
    """Why the model drifted on the monitor window, [] if it didn't.

    m = {precision, mae_model, mae_ons} for one technology. The two promises behind the headline:
    flags at least `floor` precise against ONS, and expected output no worse than ONS's own estimate.
    """
    out = []
    if m["precision"] is None or m["precision"] < floor:
        out.append(f"precision {m['precision']} < {floor}")
    if m["mae_ons"] is not None and (m["mae_model"] is None or m["mae_model"] > m["mae_ons"]):
        out.append(f"MAE {m['mae_model']} > ONS estimate {m['mae_ons']}")
    return out


def beats(challenger, champion, floor=PRECISION_FLOOR):
    """Promote only if the challenger, on the monitor window, keeps the precision floor and has lower error
    than the champion, AND does not lose flag precision over all labeled months (`precision_all`).

    Each arg = {precision, mae_model, precision_all} for one technology. The history guard was added
    2026-10-27: a challenger whose Y is tuned on only the 3-month window can pass on the window yet flag
    less precisely overall (v3: wind 0.71 vs v2's 0.76), which weakens the "at least" reading of R$.
    """
    return (challenger["precision"] >= floor and challenger["mae_model"] < champion["mae_model"]
            and challenger["precision_all"] >= champion["precision_all"])
