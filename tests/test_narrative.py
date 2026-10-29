"""Runnable check for the curtailment narrative rules (spec 16): `python tests/test_narrative.py`.

PT-BR formatting of the facts, a stable facts hash, and the grounding check that keeps an invented
number out of the app.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import narrative_lib as N  # noqa: E402

PLANT = {"nome": "Ventos de Teste", "fonte": "EOL", "uf": "RN", "submercado": "NE", "capacidade_mw": 120.0,
         "de": date(2024, 10, 1), "ate": date(2026, 9, 30), "mwh_restrito": 41_234.0,
         "valor_rs_perdido": 5_312_000.0, "mwh_esperado": 250_000.0, "horas_restritas_modelo": 1234,
         "horas_restritas_ons": None}
TOP = [{"mes": date(2025, 8, 1), "mwh_restrito": 5_100.0, "valor_rs_perdido": 640_000.0}]


def test_ptbr_formatting():
    assert N.num(1234.56) == "1.234,6" and N.num(0.5, 2) == "0,50"
    assert N.energia(41_234) == "41,2 GWh" and N.energia(812) == "812 MWh"
    assert N.reais(5_312_000) == "R$ 5,31 milhões" and N.reais(640_000) == "R$ 640 mil"
    assert N.mes(date(2025, 8, 1)) == "ago/2025"


def test_facts():
    f = N.facts(PLANT, TOP, 3, 45)
    assert f["energia_perdida"] == "41,2 GWh" and f["valor_perdido"] == "R$ 5,31 milhões"
    assert f["parcela_do_esperado"] == "16,5%" and f["pld_medio_da_energia_perdida"] == "R$ 129/MWh"
    assert f["horas_restritas_ons"] == "sem registro do ONS"
    assert f["ranking"] == "3ª de 45 usinas eólicas em RN por R$ perdido"
    assert N.facts({**PLANT, "fonte": "SOL"}, TOP, 1, 9)["ranking"] == "1ª de 9 usinas solares em RN por R$ perdido"
    assert f["piores_meses"] == [{"mes": "ago/2025", "energia_perdida": "5,1 GWh", "valor_perdido": "R$ 640 mil"}]


def test_facts_hash_is_stable_and_sensitive():
    f = N.facts(PLANT, TOP, 3, 45)
    assert N.facts_hash(f) == N.facts_hash(dict(reversed(list(f.items()))))  # key order doesn't matter
    assert N.facts_hash(f) != N.facts_hash(N.facts({**PLANT, "valor_rs_perdido": 5_400_000.0}, TOP, 3, 45))


def test_grounded():
    f = N.facts(PLANT, TOP, 3, 45)
    ok = ("A Ventos de Teste perdeu ao menos 41,2 GWh (R$ 5,31 milhões) por curtailment de out/2024 a set/2026, "
          "16,5% do esperado; o pior mês foi ago/2025. É a 3ª de 45 eólicas em RN.")
    assert N.grounded(ok, f)
    assert not N.grounded(ok.replace("R$ 5,31 milhões", "R$ 5,3 milhões"), f)  # rounded = not in the facts
    assert not N.grounded(ok + " Isso equivale a 12 dias parada.", f)        # invented figure
    assert not N.grounded("", f) and not N.grounded(None, f)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PASS")
