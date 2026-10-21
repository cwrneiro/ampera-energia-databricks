"""Runnable check for the Genie space (spec 07): `python tests/test_genie_space.py`.

Offline: the API's shape rules (ids 32-hex, unique, arrays sorted). Live (set GENIE_LIVE=1, plus
DATABRICKS_CONFIG_PROFILE and, off the demo catalog, CATALOG): every
example and benchmark SQL runs on the warehouse and returns rows, and the all-history total ties to
the app's 1,404.19 TWh.
"""
import json
import os
import re
import subprocess

SPACE = json.load(open(os.path.join(os.path.dirname(__file__), "..", "resources", "genie",
                                    "ampera.geniespace.json")))
INS = SPACE["instructions"]
SNIP = INS["sql_snippets"]


def ids(xs):
    return [x["id"] for x in xs]


def test_shape():
    questions = SPACE["config"]["sample_questions"] + SPACE["benchmarks"]["questions"]
    instructions = (INS["example_question_sqls"] + INS["text_instructions"] + INS["join_specs"]
                    + SNIP["measures"] + SNIP["filters"])
    for group in (questions, instructions):
        assert all(re.fullmatch(r"[0-9a-f]{32}", i) for i in ids(group))
        assert len(set(ids(group))) == len(group)
    for xs in (SPACE["config"]["sample_questions"], SPACE["benchmarks"]["questions"],
               INS["example_question_sqls"], INS["join_specs"], SNIP["measures"], SNIP["filters"]):
        assert ids(xs) == sorted(ids(xs))
    tables = SPACE["data_sources"]["tables"]
    assert [t["identifier"] for t in tables] == sorted(t["identifier"] for t in tables)
    for t in tables:
        cols = [c["column_name"] for c in t["column_configs"]]
        assert cols == sorted(cols), t["identifier"]
    assert len(INS["text_instructions"][0]["content"][0]) < 2000


def query(sql):
    # Profile from DATABRICKS_CONFIG_PROFILE; CATALOG retargets the payload's literal catalog name.
    sql = sql.replace("ampera_catalog.", os.environ.get("CATALOG", "ampera_catalog") + ".")
    out = subprocess.run(["databricks", "experimental", "aitools", "tools", "query", sql],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_sql_live():
    if not os.environ.get("GENIE_LIVE"):
        print("skip live check (GENIE_LIVE unset)")
        return
    sqls = ([e["sql"][0] for e in INS["example_question_sqls"]]
            + [b["answer"][0]["content"][0] for b in SPACE["benchmarks"]["questions"]])
    for sql in sqls:
        assert query(sql), sql
    total = [b for b in SPACE["benchmarks"]["questions"] if "todo o histórico" in b["question"][0]][0]
    assert float(query(total["answer"][0]["content"][0])[0]["geracao_twh"]) == 1404.19


if __name__ == "__main__":
    test_shape()
    test_sql_live()
    print("ok")
