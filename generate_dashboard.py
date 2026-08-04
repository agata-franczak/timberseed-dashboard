#!/usr/bin/env python3
"""Diagnostic - check candidate fields and dist job pagination."""

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

def rc_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS,
                     params=params or {}, timeout=30)
    return r.status_code, r.json() if r.status_code == 200 else {}

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR"); sys.exit(1)

    # 1. Get ALL fields for one candidate from dist job
    print("=== Toby dist job - first candidate full record ===")
    status, body = rc_get("/candidates", {"job_slug": TOBY_DIST, "limit": 1})
    print(f"status: {status}")
    data = body.get("data", [])
    if data:
        c = data[0]
        print(f"ALL FIELDS: {json.dumps(c, indent=2, default=str)[:2000]}")
    print(f"next_page_url: {body.get('next_page_url','none')[:80] if body.get('next_page_url') else 'none'}")

    # 2. Count Toby dist job candidates (p1 with limit=100)
    print("\n=== Toby dist job - page 1 (limit 100) ===")
    status, body = rc_get("/candidates", {"job_slug": TOBY_DIST, "limit": 100})
    data = body.get("data", [])
    print(f"p1 count: {len(data)}")
    print(f"has more: {'yes' if body.get('next_page_url') else 'no'}")
    # Show stage breakdown
    stages = {}
    for c in data:
        # Try various stage field names
        for field in ["status_label","current_status","stage","job_stage","pipeline_stage","status"]:
            val = c.get(field)
            if val:
                stages[f"{field}={val}"] = stages.get(f"{field}={val}", 0) + 1
    print(f"stage breakdown: {json.dumps(stages, indent=2)}")

    # 3. Count Joe dist job candidates (p1)
    print("\n=== Joe dist job - page 1 (limit 100) ===")
    status, body2 = rc_get("/candidates", {"job_slug": JOE_DIST, "limit": 100})
    data2 = body2.get("data", [])
    print(f"p1 count: {len(data2)}")
    print(f"has more: {'yes' if body2.get('next_page_url') else 'no'}")

    # 4. Test pipeline - Toby at CV Sent with limit=10 to see names
    print("\n=== Toby candidates at CV Sent (owner_id filter test) ===")
    status, body3 = rc_get("/candidates", {"owner_id": TOBY_ID, "status_id": 537163, "limit": 10})
    data3 = body3.get("data", [])
    print(f"count: {len(data3)}")
    for c in data3[:5]:
        print(f"  {c.get('first_name','')} {c.get('last_name','')} | owner: {c.get('owner_id') or c.get('owner','?')}")

    out = Path("docs"); out.mkdir(exist_ok=True)
    (out / "index.html").write_text("<html><body><h1>Diagnostic</h1></body></html>")
    print("\nDone")
