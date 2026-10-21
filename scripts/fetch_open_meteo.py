"""Fetch Open-Meteo (ERA5) hourly weather for every plant grid cell, within the free-tier limits.

Usage:  python3 scripts/fetch_open_meteo.py [--budget 9500]
Input:  data/raw/open_meteo/cells.json — 0.25° cells with plants, exported with:
          databricks experimental aitools tools query "SELECT round(lat*4)/4 AS lat, round(lon*4)/4 AS lon,
          count(*) plants FROM <catalog>.silver.dim_plant WHERE lat IS NOT NULL GROUP BY 1,2"
          --profile <profile> --output json > data/raw/open_meteo/cells.json
Output: data/raw/open_meteo/raw/<YYYY_MM>/cell_<lat>_<lon>.json — the API's JSON object for that
        location (requests batch 10 cells; bronze ingests these files as-is). Existing files are skipped, so the script can resume.

Open-Meteo counts one location × 2 weeks × ≤10 variables as 1 call; free tier = 600/min, 5,000/hour,
10,000/day. 24 months × 469 cells ≈ 24.5k calls, so this takes ~3 daily runs. Newest months go first,
so the map has recent weather after the first run. Free API = non-commercial use (decision #18).
Spec: specs/03-gold-marts.md
"""
import argparse
import calendar
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from datetime import date

ROOT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "open_meteo")
URL = "https://archive-api.open-meteo.com/v1/archive"
VARS = "temperature_2m,wind_speed_100m,shortwave_radiation,precipitation"
FIRST, LAST = (2024, 10), (2026, 9)  # demo window, decision #14
PER_MINUTE, PER_HOUR = 550, 4500     # stay under 600/min and 5,000/hour
BATCH = 10                           # cells per request

# This Mac's python.org build lacks a CA bundle; the macOS system bundle works.
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem") if os.path.exists("/etc/ssl/cert.pem") else None


def months_newest_first():
    y, m = LAST
    while (y, m) >= FIRST:
        yield y, m
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)


def cost(y, m):
    return calendar.monthrange(y, m)[1] / 14  # weighted calls for one location-month


def fetch(cells, y, m):
    """One request for up to BATCH cells (same call cost as separate requests, ~5x faster)."""
    lat = ",".join(c["lat"] for c in cells)
    lon = ",".join(c["lon"] for c in cells)
    q = (f"{URL}?latitude={lat}&longitude={lon}&start_date={date(y, m, 1)}"
         f"&end_date={date(y, m, calendar.monthrange(y, m)[1])}&hourly={VARS}"
         f"&wind_speed_unit=ms&timezone=America%2FSao_Paulo")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(q, timeout=120, context=CTX) as r:
                body = json.loads(r.read())
            return body if isinstance(body, list) else [body]
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limited: back off and retry
                time.sleep(60 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"gave up after retries: {len(cells)} cells {y}-{m:02d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=9500, help="max weighted calls this run (<10k/day)")
    budget = ap.parse_args().budget
    cells = json.load(open(os.path.join(ROOT, "cells.json")))
    spent = minute_spent = hour_spent = 0.0
    minute_t0 = hour_t0 = time.time()
    done = skipped = 0
    for y, m in months_newest_first():
        out_dir = os.path.join(ROOT, "raw", f"{y}_{m:02d}")
        os.makedirs(out_dir, exist_ok=True)
        todo = [c for c in cells
                if not os.path.exists(os.path.join(out_dir, f"cell_{c['lat']}_{c['lon']}.json"))]
        skipped += len(cells) - len(todo)
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            w = cost(y, m) * len(batch)
            if spent + w > budget:
                print(f"budget reached: {spent:.0f} calls, {done} files written, {skipped} already present")
                return
            now = time.time()
            if now - minute_t0 >= 60:
                minute_t0, minute_spent = now, 0.0
            if now - hour_t0 >= 3600:
                hour_t0, hour_spent = now, 0.0
            if minute_spent + w > PER_MINUTE:
                time.sleep(max(0, 60 - (now - minute_t0)) + 1)
                minute_t0, minute_spent = time.time(), 0.0
            if hour_spent + w > PER_HOUR:
                print(f"hourly cap: sleeping until next hour ({spent:.0f} calls so far)", flush=True)
                time.sleep(max(0, 3600 - (now - hour_t0)) + 5)
                hour_t0, hour_spent, minute_t0, minute_spent = time.time(), 0.0, time.time(), 0.0
            locs = fetch(batch, y, m)
            if len(locs) != len(batch):
                raise RuntimeError(f"asked for {len(batch)} locations, got {len(locs)}")
            for c, loc in zip(batch, locs):  # API returns locations in request order
                path = os.path.join(out_dir, f"cell_{c['lat']}_{c['lon']}.json")
                with open(path + ".tmp", "w") as f:
                    json.dump(loc, f)
                os.replace(path + ".tmp", path)  # atomic: a partial file never looks finished
                done += 1
            spent += w; minute_spent += w; hour_spent += w
        print(f"{y}-{m:02d} complete ({spent:.0f} calls so far)", flush=True)
    print(f"ALL MONTHS COMPLETE: {spent:.0f} calls this run, {done} files written, {skipped} already present")


if __name__ == "__main__":
    main()
