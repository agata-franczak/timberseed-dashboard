#!/usr/bin/env python3
"""Diagnostic - test candidate/pipeline counts via total field."""

import json, os, sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

API_KEY  = os.environ.get("RECRUITCRM_API_KEY", "")
BASE_URL = "https://api.recruitcrm.io/v1"
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

TOBY_DIST = "17798857082070098322oYJ"
JOE_DIST  = "17809259732490098322VkM"
TOBY_ID   = 140768
JOE_ID    = 143107

# Known stage IDs
STAGES = {537163:"CV Sent", 537164:"1st Interviews",
          537165:"Further Interviews", 537166:"Final Interviews", 8:"Placed"}

def probe(label, path, params):
    print(f"\n=== {label} ===")
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=30)
    print(f"  status: {r.status_code}")
    if r.status_code != 200:
        print(f"  body: {r.text[:300]}")
        return {}
    b = r.json()
    print(f"  keys: {list(b.keys())}")
    for k in ["total","total_count","returned_count","from","to","per_page"]:
        if k in b:
            print(f"  {k}: {b[k]}")
    data = b.get("data", b.get("candidates", b.get("assigned_candidates", [])))
    print(f"  records in data: {len(data)}")
    if data:
        print(f"  first record keys: {list(data[0].keys())[:10]}")
    return b

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR"); sys.exit(1)

    # Test 1: candidates filtered by job_slug
    probe("Candidates with job_slug (Toby dist)",
          "/candidates", {"job_slug": TOBY_DIST, "limit": 1})

    # Test 2: candidates filtered by job_id (slug as id)
    probe("Candidates with job_id",
          "/candidates", {"job_id": TOBY_DIST, "limit": 1})

    # Test 3: single job endpoint
    probe("Single job GET", f"/jobs/{TOBY_DIST}", {})

    # Test 4: candidates for a stage
    probe("Candidates at CV Sent stage",
          "/candidates", {"status_id": 537163, "limit": 1})

    # Test 5: candidates owned by Toby at a stage
    probe("Candidates owned by Toby at CV Sent",
          "/candidates", {"owner_id": TOBY_ID, "status_id": 537163, "limit": 1})

    # Test 6: candidates with current_stage filter
    probe("Candidates with current_stage=CV Sent",
          "/candidates", {"current_stage": "CV Sent", "limit": 1})

    # Test 7: all candidates limit 1 — just to confirm total field exists
    probe("All candidates (limit 1)",
          "/candidates", {"limit": 1})

    # Test 8: meetings total without owner
    probe("Meetings (limit 1, no filter)",
          "/meetings", {"limit": 1})

    # Test 9: meetings for Toby with date filter
    probe("Meetings Toby with date filter",
          "/meetings", {"owner_id": TOBY_ID, "starting_from": "2026-07-01",
                        "starting_to": "2026-08-04", "limit": 1})

    out = Path("docs"); out.mkdir(exist_ok=True)
    (out / "index.html").write_text("<html><body><h1>Diagnostic</h1></body></html>")
    print("\nDone")
