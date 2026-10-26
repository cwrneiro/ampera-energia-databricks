"""Export the notebook tasks of a job run as .ipynb files WITH their outputs (spec 15).

Usage: python3 scripts/export_run_notebooks.py <job_run_id> [profile]   -> evidence/notebooks/<task>.ipynb

The Jobs API exports a run as HTML that embeds the executed notebook (commands + results) as a
base64/url-encoded JSON model; this decodes it into a plain Jupyter notebook an evaluator can read
as text on GitHub.
"""
import base64
import json
import os
import re
import subprocess
import sys
import urllib.parse

ANSI = re.compile(r"\x1b\[[0-9;]*m")
OUT = os.path.join(os.path.dirname(__file__), "..", "evidence", "notebooks")


def cli(*args, profile):
    return json.loads(subprocess.run(["databricks", *args, "-p", profile, "-o", "json"],
                                     capture_output=True, text=True, check=True).stdout)


def to_ipynb(model, meta):
    cells = []
    for c in sorted(model["commands"], key=lambda c: c["position"]):
        src = c["command"]
        if src.startswith("%md"):
            cells.append({"cell_type": "markdown", "metadata": {}, "source": src[3:].lstrip("\n").splitlines(True)})
            continue
        outs, r = [], c.get("results") or {}
        data = r.get("data")
        if isinstance(data, list):
            text = "".join(ANSI.sub("", x.get("data", "")) for x in data if x.get("type") in ("ansi", "text"))
            if text:
                outs.append({"output_type": "stream", "name": "stdout", "text": text.splitlines(True)})
        elif isinstance(data, str) and data:
            outs.append({"output_type": "stream", "name": "stdout", "text": ANSI.sub("", data).splitlines(True)})
        if c.get("error"):
            outs.append({"output_type": "error", "ename": "Error", "evalue": ANSI.sub("", str(c["error"]))[:4000], "traceback": []})
        cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "source": src.splitlines(True), "outputs": outs})
    return {"cells": cells, "nbformat": 4, "nbformat_minor": 5,
            "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                         "databricks_job_run": meta}}


def main(run_id, profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "DEFAULT")):
    os.makedirs(OUT, exist_ok=True)
    run = cli("jobs", "get-run", run_id, profile=profile)
    for t in run["tasks"]:
        if "notebook_task" not in t or t["state"].get("result_state") in ("EXCLUDED", "SKIPPED", None):
            continue  # not executed in this run (e.g. train gate off): nothing to export
        html = cli("jobs", "export-run", str(t["run_id"]), "--views-to-export", "CODE", profile=profile)["views"][0]["content"]
        enc = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html).group(1)
        model = json.loads(urllib.parse.unquote(base64.b64decode(enc).decode()))
        meta = {"job": run.get("run_name"), "run_id": run["run_id"], "task": t["task_key"], "task_run_id": t["run_id"],
                "result_state": t["state"].get("result_state"), "start_time_ms": t.get("start_time"),
                "end_time_ms": t.get("end_time")}
        path = os.path.join(OUT, f"{t['task_key']}.ipynb")
        with open(path, "w") as f:
            json.dump(to_ipynb(model, meta), f, ensure_ascii=False, indent=1)
        print(f"{t['task_key']:<20} {meta['result_state']:<8} -> {os.path.relpath(path)}")


if __name__ == "__main__":
    main(*sys.argv[1:])
