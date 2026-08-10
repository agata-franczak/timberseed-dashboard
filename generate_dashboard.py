#!/usr/bin/env python3
"""Diagnostic - find hiring pipeline field in jobs API."""

import json, os, sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

API_KEY  = os.environ.get("RECRUITCRM_API_KEY", "")
BASE_URL = "https://api.recruitcrm.io/v1"
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

def rc_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS,
                     params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR"); sys.exit(1)

    # Fetch a few jobs and print ALL fields on each
    body = rc_get("/jobs", {"job_status": "1", "limit": 5, "page": 1})
    jobs = body.get("data", [])
    print(f"Fetched {len(jobs)} jobs\n")

    for j in jobs[:3]:
        print(f"=== {j.get('name')} (owner: {j.get('owner')}) ===")
        for k, v in j.items():
            if v not in (None, "", 0, [], {}):
                print(f"  {k}: {v}")
        print()

    # Also try fetching a known SaaS job (English BDR) specifically
    print("=== Known SaaS job: English BDR ===")
    body2 = rc_get("/jobs/17835152199350098322kWD")
    if isinstance(body2, dict):
        for k, v in body2.items():
            if v not in (None, "", 0, [], {}):
                print(f"  {k}: {v}")

    # Try filtering jobs by hiring_pipeline parameters
    print("\n=== Try hiring_pipeline filter ===")
    for param in ["hiring_pipeline", "hiring_pipeline_id", "pipeline", "pipeline_id"]:
        try:
            r = requests.get(f"{BASE_URL}/jobs", headers=HEADERS,
                             params={"job_status": "1", param: "sales", "limit": 1},
                             timeout=30)
            body3 = r.json()
            jobs3 = body3.get("data", [])
            total = body3.get("total", "?")
            print(f"  {param}=sales → status {r.status_code}, total: {total}, jobs: {len(jobs3)}")
        except Exception as e:
            print(f"  {param}: error — {e}")

    # Try hiring pipelines endpoint
    print("\n=== /hiring-pipelines endpoint ===")
    for path in ["/hiring-pipelines", "/pipelines", "/hiring_pipelines"]:
        try:
            r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)
            print(f"  {path} → {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"  {path}: {e}")

    out = Path("docs"); out.mkdir(exist_ok=True)
    (out / "index.html").write_text("<html><body><h1>Diagnostic</h1></body></html>")
    print("\nDone")
