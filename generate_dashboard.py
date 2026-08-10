#!/usr/bin/env python3
"""Diagnostic - test report.recruitcrm.io endpoint."""

import json, os, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

API_KEY = os.environ.get("RECRUITCRM_API_KEY", "")
JWT     = os.environ.get("RECRUITCRM_JWT", "")  # will test with and without

# Date range: last 30 days
now      = int(time.time())
from_ts  = now - (30 * 24 * 60 * 60)

PAYLOAD = {
    "from_date": str(from_ts),
    "to_date":   str(now),
    "kpi_lists": [{"value": "537178", "label": "Hiring Stage - Call", "checked": True}],
    "recruiter_ids": [140768, 143107, 147065],  # Toby, Joe, Finn
    "team_ids": [1841, 1842, 1855, 1856, 1857],
}

REPORT_URL = "https://report.recruitcrm.io/v1/reports/team-performance-report"

def try_request(label, auth_header):
    print(f"\n=== {label} ===")
    headers = {
        "Accept":       "application/json, text/plain, */*",
        "Authcode":     "kSyfwqb1",
        "Authorization": auth_header,
        "Content-Type": "application/json",
    }
    r = requests.post(REPORT_URL, headers=headers, json=PAYLOAD, timeout=30)
    print(f"  status: {r.status_code}")
    if r.status_code == 200:
        b = r.json()
        print(f"  keys: {list(b.keys())}")
        data = b.get("data", {})
        print(f"  recruiter entries: {len(data)}")
        for rid, val in list(data.items())[:3]:
            print(f"    {rid}: {val}")
    else:
        print(f"  body: {r.text[:300]}")

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: no API key"); sys.exit(1)

    # Test 1: use our API key as Bearer
    try_request("API key as Bearer", f"Bearer {API_KEY}")

    # Test 2: if JWT secret is set, try that
    if JWT:
        try_request("JWT from secret", f"Bearer {JWT}")
    else:
        print("\n=== JWT test skipped (RECRUITCRM_JWT secret not set) ===")

    # Test 3: try refresh-jwt-token with our API key
    print("\n=== Try refresh-jwt-token with API key ===")
    r = requests.post(
        "https://marketplace.api.vonq.com/v3/ats/atsuser/me/refresh-jwt-token/",
        headers={"Authorization": f"Bearer {API_KEY}",
                 "Content-Type": "application/json"},
        timeout=30
    )
    print(f"  status: {r.status_code}")
    print(f"  body: {r.text[:300]}")

    out = Path("docs"); out.mkdir(exist_ok=True)
    (out / "index.html").write_text("<html><body><h1>Diagnostic</h1></body></html>")
    print("\nDone")
