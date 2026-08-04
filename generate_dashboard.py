#!/usr/bin/env python3
"""Timberseed Dashboard - diagnostic for jobs/candidates endpoints."""

import json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

API_KEY  = os.environ.get("RECRUITCRM_API_KEY", "")
BASE_URL = "https://api.recruitcrm.io/v1"
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

TOBY_DIST_SLUG = "17798857082070098322oYJ"
JOE_DIST_SLUG  = "17809259732490098322VkM"
TOBY_ID = 140768
JOE_ID  = 143107

def rc_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS,
                     params=params or {}, timeout=30)
    print(f"  GET {path} → {r.status_code}")
    if r.status_code != 200:
        print(f"  body: {r.text[:200]}")
        return {}
    body = r.json()
    print(f"  keys: {list(body.keys())}")
    # Print any count-like fields
    for k in ["total","total_count","returned_count","from","to","per_page","current_page"]:
        if k in body:
            print(f"  {k}: {body[k]}")
    return body

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: key not set"); sys.exit(1)

    print("=== Test: Toby dist job candidates (page 1 only) ===")
    rc_get(f"/jobs/{TOBY_DIST_SLUG}/candidates", {"limit": 1})

    print("\n=== Test: Toby dist job candidates - assigned_candidates key ===")
    b = rc_get(f"/jobs/{TOBY_DIST_SLUG}/candidates", {"limit": 1})
    print(f"  'data' length: {len(b.get('data',[]))}")
    print(f"  'assigned_candidates' length: {len(b.get('assigned_candidates',[]))}")

    print("\n=== Test: Jobs for Toby (owner_id + job_status=1) ===")
    rc_get("/jobs", {"owner_id": TOBY_ID, "job_status": "1", "limit": 5})

    print("\n=== Test: Jobs for Toby (no status filter) ===")
    rc_get("/jobs", {"owner_id": TOBY_ID, "limit": 5})

    print("\n=== Test: Jobs with no filter ===")
    b2 = rc_get("/jobs", {"limit": 5})
    jobs = b2.get("data", [])
    print(f"  jobs in data: {len(jobs)}")
    for j in jobs[:3]:
        print(f"    - {j.get('name')} | slug: {j.get('slug','')[:20]}")

    # Write placeholder
    out = Path("docs"); out.mkdir(exist_ok=True)
    (out / "index.html").write_text("<html><body><h1>Diagnostic run</h1></body></html>")
    print("\nDone")
