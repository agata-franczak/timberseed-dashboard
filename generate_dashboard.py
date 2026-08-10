#!/usr/bin/env python3
"""Diagnostic - all open jobs, candidates at key stages, filter by owner."""

import json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

API_KEY  = os.environ.get("RECRUITCRM_API_KEY", "")
BASE_URL = "https://api.recruitcrm.io/v1"
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

# We want candidates owned by Toby or Joe
TOBY_ID = 140768
JOE_ID  = 143107
OWNERS  = {TOBY_ID: "Toby", JOE_ID: "Joe"}

KEY_STAGES = {537163:"CV Sent", 537164:"1st Interviews",
              537165:"Further Interviews", 537166:"Final Interviews", 8:"Placed"}

CUTOFF = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

def rc_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS,
                     params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR"); sys.exit(1)

    # Step 1: all open jobs updated in last 90 days
    print(f"Scanning all open jobs updated since {CUTOFF}...", flush=True)
    all_jobs, page = [], 1
    while True:
        body = rc_get("/jobs", {"job_status": "1", "limit": 100, "page": page})
        jobs = body.get("data", [])
        if not jobs: break
        oldest = min((j.get("updated_on") or "")[:10] for j in jobs)
        in_range = [j for j in jobs if (j.get("updated_on") or "")[:10] >= CUTOFF]
        all_jobs.extend(in_range)
        print(f"  p{page}: {len(jobs)} total, {len(in_range)} in range, oldest: {oldest}", flush=True)
        if oldest < CUTOFF or not body.get("next_page_url"):
            break
        page += 1

    print(f"\nOpen jobs updated in last 90 days: {len(all_jobs)}")

    # Step 2: for each job, get candidates at key stages
    stage_param = ",".join(str(k) for k in KEY_STAGES)
    pipeline = []
    owner_counts = {}

    for j in all_jobs:
        slug = j.get("slug")
        if not slug: continue
        try:
            body = rc_get("/candidates", {
                "job_slug":  slug,
                "status_id": stage_param,
                "limit": 100,
            })
            cands = body.get("data", [])
            if not cands: continue

            for c in cands:
                owner = c.get("owner_id") or c.get("owner") or 0
                owner_counts[owner] = owner_counts.get(owner, 0) + 1

                if owner in OWNERS:
                    pipeline.append({
                        "owner":      OWNERS[owner],
                        "name":       f"{c.get('first_name','')} {c.get('last_name','')}".strip(),
                        "stage":      c.get("status_label") or KEY_STAGES.get(c.get("status_id"), "?"),
                        "stage_date": (c.get("updated_on") or "")[:10],
                        "job":        j.get("name",""),
                    })
        except Exception as e:
            print(f"  {j.get('name')}: {e}", flush=True)

    print(f"\nPipeline candidates (Toby+Joe): {len(pipeline)}")
    for p in pipeline:
        print(f"  {p['owner']}: {p['name']} | {p['stage']} | {p['stage_date']} | {p['job']}")

    print(f"\nTop owner IDs seen across all candidates:")
    for oid, cnt in sorted(owner_counts.items(), key=lambda x:-x[1])[:15]:
        print(f"  {oid}: {cnt} candidates")

    out = Path("docs"); out.mkdir(exist_ok=True)
    (out / "index.html").write_text("<html><body><h1>Diagnostic</h1></body></html>")
    print("\nDone")
