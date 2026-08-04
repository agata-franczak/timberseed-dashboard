#!/usr/bin/env python3
"""Timberseed Dashboard - Debug version to diagnose API response."""

import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

API_KEY  = os.environ.get("RECRUITCRM_API_KEY", "")
BASE_URL = "https://api.recruitcrm.io/v1"
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: RECRUITCRM_API_KEY not set"); sys.exit(1)

    print(f"API key starts with: {API_KEY[:8]}...", flush=True)
    print(f"API key length: {len(API_KEY)}", flush=True)

    # Test 1: meetings with no params
    print("\n--- Test 1: GET /meetings (no params) ---")
    r = requests.get(f"{BASE_URL}/meetings", headers=HEADERS, timeout=30)
    print(f"Status: {r.status_code}")
    try:
        body = r.json()
        print(f"Keys in response: {list(body.keys())}")
        print(f"returned_count: {body.get('returned_count')}")
        print(f"total_count: {body.get('total_count')}")
        print(f"has_more: {body.get('has_more')}")
        meetings = body.get('meetings', [])
        print(f"meetings list length: {len(meetings)}")
        if meetings:
            print(f"First meeting title: {meetings[0].get('title')}")
            print(f"First meeting date: {meetings[0].get('start_date')}")
    except Exception as ex:
        print(f"Could not parse JSON: {ex}")
        print(f"Raw response (first 500 chars): {r.text[:500]}")

    # Test 2: candidates
    print("\n--- Test 2: GET /candidates (no params) ---")
    r2 = requests.get(f"{BASE_URL}/candidates", headers=HEADERS, timeout=30)
    print(f"Status: {r2.status_code}")
    try:
        body2 = r2.json()
        print(f"returned_count: {body2.get('returned_count')}")
        print(f"total_count: {body2.get('total_count')}")
    except Exception as ex:
        print(f"Could not parse JSON: {ex}")
        print(f"Raw (first 300): {r2.text[:300]}")

    # Test 3: jobs
    print("\n--- Test 3: GET /jobs (no params) ---")
    r3 = requests.get(f"{BASE_URL}/jobs", headers=HEADERS, timeout=30)
    print(f"Status: {r3.status_code}")
    try:
        body3 = r3.json()
        print(f"returned_count: {body3.get('returned_count')}")
        jobs = body3.get('jobs', [])
        print(f"jobs list length: {len(jobs)}")
        if jobs:
            print(f"First job: {jobs[0].get('name')}")
    except Exception as ex:
        print(f"Could not parse JSON: {ex}")
        print(f"Raw (first 300): {r3.text[:300]}")

    # Write a placeholder dashboard so the commit step works
    out = Path("docs"); out.mkdir(exist_ok=True)
    (out / "index.html").write_text(
        "<html><body><h1>Timberseed Dashboard</h1>"
        "<p>Diagnosing API access — check Actions logs.</p></body></html>",
        encoding="utf-8"
    )
    print("\nDone (debug run)")
