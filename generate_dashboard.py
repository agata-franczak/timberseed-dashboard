#!/usr/bin/env python3
"""Diagnostic - probe app.recruitcrm.io reports endpoint."""

import json, os, sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

API_KEY  = os.environ.get("RECRUITCRM_API_KEY", "")
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

def probe(label, url, params=None, method="GET", body=None):
    print(f"\n=== {label} ===")
    print(f"  url: {url}")
    try:
        if method == "POST":
            r = requests.post(url, headers=HEADERS, json=body or {}, timeout=30)
        else:
            r = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
        print(f"  status: {r.status_code}")
        if r.status_code in (200, 201):
            try:
                b = r.json()
                print(f"  type: {type(b).__name__}")
                if isinstance(b, dict):
                    print(f"  keys: {list(b.keys())}")
                    for k in ["total","count","data","results","report","records"]:
                        if k in b:
                            v = b[k]
                            print(f"  {k}: {v if not isinstance(v,(list,dict)) else f'({type(v).__name__}, len={len(v)})'}")
                elif isinstance(b, list):
                    print(f"  list length: {len(b)}")
                    if b:
                        print(f"  first item keys: {list(b[0].keys()) if isinstance(b[0],dict) else b[0]}")
            except:
                print(f"  raw (first 300): {r.text[:300]}")
        else:
            print(f"  body: {r.text[:300]}")
    except Exception as e:
        print(f"  error: {e}")

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: no API key"); sys.exit(1)
    print(f"Key: {API_KEY[:8]}...")

    APP = "https://app.recruitcrm.io/v1"
    API = "https://api.recruitcrm.io/v1"

    # The URL from the browser
    probe("candidate-report (app domain)",
          f"{APP}/reports/candidate-report")

    probe("candidate-report with params",
          f"{APP}/reports/candidate-report",
          params={"from": "2026-07-11", "to": "2026-08-10"})

    probe("candidate-report with owner",
          f"{APP}/reports/candidate-report",
          params={"from": "2026-07-11", "to": "2026-08-10",
                  "owner_id": 140768, "stage": "Call"})

    # Try variations
    probe("reports list (app domain)",
          f"{APP}/reports")

    probe("candidate-lifecycle (app domain)",
          f"{APP}/reports/candidate-lifecycle")

    probe("kpi-report (app domain)",
          f"{APP}/reports/kpi-report")

    # Also try api domain with correct path
    probe("candidate-report (api domain)",
          f"{API}/reports/candidate-report")

    # Try meetings on app domain
    probe("meetings (app domain)",
          f"{APP}/meetings",
          params={"owner_id": 140768, "limit": 1})

    out = Path("docs"); out.mkdir(exist_ok=True)
    (out / "index.html").write_text("<html><body><h1>Diagnostic</h1></body></html>")
    print("\nDone")
