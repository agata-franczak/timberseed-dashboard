#!/usr/bin/env python3
"""
Timberseed Dashboard Generator
Fetches all meetings from RecruitCRM, identifies each consultant by title pattern.
No owner_id filtering needed — works with standard API key permissions.
"""

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

DAYS_BACK = 90  # how many days of history to embed; filtering is client-side

# Each consultant is identified purely by title pattern — no owner_id needed
CONSULTANTS = [
    {"name":"Toby Ranson",   "initials":"TR", "role":"Consultant",
     "pattern":"Introductory Phone Call | Toby",
     "label":"Candidate intro calls", "note":"Scheduler-booked candidate calls"},
    {"name":"Joe Leonard",   "initials":"JL", "role":"Consultant",
     "pattern":"Joe Leonard x",
     "label":"Candidate intro calls", "note":"Scheduler-booked candidate calls"},
    {"name":"Finn Phillips", "initials":"FP", "role":"Business Development",
     "pattern":"call james pickering",   # Finn's only logged prospect call pattern
     "label":"BD prospect meetings",     # (tasks are where his BD activity really lives)
     "note":"External prospect calls logged in RecruitCRM"},
]

def rc_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS,
                     params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_all_meetings():
    """Fetch ALL meetings for the account, last DAYS_BACK days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).date().isoformat()
    out, page = [], 1
    print(f"Fetching all meetings (cutoff {cutoff})...", flush=True)
    while True:
        data = rc_get("/meetings", {"page": page, "limit": 100})
        batch = data.get("meetings", [])
        # filter to cutoff date
        in_range = [m for m in batch
                    if (m.get("start_date") or "")[:10] >= cutoff]
        out.extend(in_range)
        print(f"  p{page}: {len(batch)} returned, {len(in_range)} in range, total so far: {len(out)}", flush=True)
        # stop if oldest record in this page is before cutoff (sorted desc)
        if batch:
            oldest = min((m.get("start_date") or "")[:10] for m in batch)
            if oldest < cutoff:
                print(f"  reached cutoff, stopping")
                break
        if not data.get("has_more"):
            break
        page += 1
    print(f"Total meetings fetched: {len(out)}")
    return out

def classify_all(all_meetings):
    """Split meetings into per-consultant call lists."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).date().isoformat()
    results = {}
    for c in CONSULTANTS:
        results[c["name"]] = []

    for m in all_meetings:
        t = (m.get("title") or "").replace("&lt;","<").replace("&gt;",">")
        d = (m.get("start_date") or "")[:10]
        if d < cutoff:
            continue
        tl = t.lower()
        for c in CONSULTANTS:
            if c["pattern"].lower() in tl:
                results[c["name"]].append({"date": d, "is_call": True})
                break

    for c in CONSULTANTS:
        n = len(results[c["name"]])
        print(f"  {c['name']}: {n} calls identified")
    return results

def fetch_all():
    now  = datetime.now(timezone.utc)
    data = {"generated_at": now.isoformat(), "consultants": []}

    all_meetings = fetch_all_meetings()
    classified   = classify_all(all_meetings)

    for c in CONSULTANTS:
        meetings = classified[c["name"]]
        data["consultants"].append({
            "name":          c["name"],
            "initials":      c["initials"],
            "role":          c["role"],
            "meeting_label": c["label"],
            "meeting_note":  c["note"],
            "meetings":      meetings,
            "pipeline":      [],   # pipeline requires owner-filtered API; omitted
        })
    return data

def build_html(data):
    dj = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Timberseed · Dashboard</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--p:#534AB7;--pm:#7F77DD;--pl:#EEEDFE;--t:#0f172a;--t2:#475569;--t3:#94a3b8;
  --bg:#f8fafc;--s:#fff;--b:#e2e8f0;--r:10px;--rs:6px}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:var(--bg);color:var(--t);min-height:100vh}}
.hdr{{background:var(--s);border-bottom:1px solid var(--b);padding:1rem 1.5rem;
  display:flex;justify-content:space-between;align-items:center;
  position:sticky;top:0;z-index:50;gap:12px;flex-wrap:wrap}}
.logo{{display:flex;align-items:center;gap:10px}}
.lm{{width:34px;height:34px;border-radius:8px;background:var(--p);display:flex;
  align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff}}
.ln{{font-size:15px;font-weight:600}}.ls{{font-size:12px;color:var(--t3);margin-top:1px}}
.gen{{font-size:11px;color:var(--t3)}}
.ctrl{{background:var(--s);border-bottom:1px solid var(--b);padding:.875rem 1.5rem;
  display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.cl{{font-size:12px;font-weight:500;color:var(--t2)}}
.prs{{display:flex;gap:6px;flex-wrap:wrap}}
.pb{{font-size:12px;font-weight:500;padding:4px 12px;border-radius:20px;
  border:1px solid var(--b);background:var(--s);color:var(--t2);cursor:pointer;transition:all .15s}}
.pb:hover{{border-color:var(--p);color:var(--p)}}.pb.on{{background:var(--p);border-color:var(--p);color:#fff}}
.sep{{width:1px;height:22px;background:var(--b)}}
.cust{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.cust label{{font-size:12px;color:var(--t3)}}
.cust input{{font-size:12px;padding:4px 8px;border:1px solid var(--b);border-radius:var(--rs);
  color:var(--t);background:var(--s);font-family:inherit}}
.ri{{font-size:11px;color:var(--t3);margin-left:auto}}
.main{{padding:1.25rem 1.5rem}}
.sg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:1.25rem}}
.sc{{background:var(--s);border:1px solid var(--b);border-radius:var(--rs);padding:.875rem 1rem}}
.sl{{font-size:10px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--t3);margin-bottom:5px}}
.sv{{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums}}
.ss{{font-size:11px;color:var(--t3);margin-top:3px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}}
.card{{background:var(--s);border:1px solid var(--b);border-radius:var(--r);overflow:hidden}}
.ch{{padding:1rem 1.25rem;border-bottom:1px solid var(--b);display:flex;align-items:center;gap:12px}}
.av{{width:40px;height:40px;border-radius:50%;background:var(--pl);display:flex;
  align-items:center;justify-content:center;font-size:13px;font-weight:700;color:var(--p)}}
.cn{{font-size:15px;font-weight:600}}.cr{{font-size:12px;color:var(--t3);margin-top:1px}}
.cb{{padding:1rem 1.25rem;display:flex;flex-direction:column;gap:16px}}
.secl{{font-size:10px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--t3);margin-bottom:8px}}
.bx{{background:var(--bg);border:1px solid var(--b);border-radius:var(--rs);padding:.875rem 1rem}}
.br{{display:flex;justify-content:space-between;align-items:baseline}}
.bl{{font-size:13px;color:var(--t2)}}.bn{{font-size:28px;font-weight:700;font-variant-numeric:tabular-nums}}
.bsub{{font-size:11px;color:var(--t3);margin-top:4px}}
.mc{{margin-top:10px}}.mbw{{display:flex;align-items:flex-end;gap:2px;height:44px}}
.mb{{flex:1;background:var(--pm);border-radius:2px 2px 0 0;min-width:2px;position:relative;cursor:default}}
.mb:hover{{background:var(--p)}}
.mbn{{position:absolute;top:-14px;left:50%;transform:translateX(-50%);
  font-size:7px;font-weight:700;color:var(--t2);white-space:nowrap}}
.mx{{display:flex;justify-content:space-between;font-size:9px;color:var(--t3);margin-top:3px}}
.note{{font-size:11px;color:var(--t3);border-top:1px solid var(--b);padding-top:10px;line-height:1.5}}
.fn-note{{font-size:12px;color:var(--t2);line-height:1.6;
  background:var(--pl);border-radius:var(--rs);padding:.75rem 1rem}}
</style></head><body>
<header class="hdr">
  <div class="logo"><div class="lm">TS</div>
    <div><div class="ln">Timberseed</div><div class="ls">Consultant Performance Dashboard</div></div>
  </div>
  <div class="gen" id="gen"></div>
</header>
<div class="ctrl">
  <span class="cl">Period:</span>
  <div class="prs">
    <button class="pb" data-d="7">7 days</button>
    <button class="pb" data-d="14">14 days</button>
    <button class="pb on" data-d="30">30 days</button>
    <button class="pb" data-d="60">60 days</button>
    <button class="pb" data-d="90">90 days</button>
  </div>
  <div class="sep"></div>
  <div class="cust">
    <label>From</label><input type="date" id="fd">
    <label>to</label><input type="date" id="td">
  </div>
  <div class="ri" id="ri"></div>
</div>
<main class="main">
  <div class="sg" id="sg"></div>
  <div class="grid" id="grid"></div>
</main>
<script>
const D={dj};
const fGB=d=>d.toLocaleDateString("en-GB",{{day:"numeric",month:"short",year:"numeric"}});
const fS=d=>d.toLocaleDateString("en-GB",{{day:"numeric",month:"short"}});
function inR(ds,s,e){{if(!ds)return false;const d=new Date(ds);d.setHours(12);return d>=s&&d<=e;}}
function bR(days){{const e=new Date();e.setHours(23,59,59,999);const s=new Date();s.setDate(s.getDate()-days);s.setHours(0,0,0,0);return{{s,e}};}}
function render(s,e){{
  const g=new Date(D.generated_at);
  document.getElementById("gen").textContent="Updated "+fGB(g)+" "+g.toLocaleTimeString("en-GB",{{hour:"2-digit",minute:"2-digit"}})+" UTC";
  document.getElementById("ri").textContent=fGB(s)+" \u2013 "+fGB(e);
  document.getElementById("fd").value=s.toISOString().slice(0,10);
  document.getElementById("td").value=e.toISOString().slice(0,10);
  let tC=0;
  const cards=D.consultants.map(c=>{{const r=bC(c,s,e);tC+=r.calls;return r;}});
  document.getElementById("grid").innerHTML=cards.map(c=>c.html).join("");
  document.getElementById("sg").innerHTML=`
    <div class="sc"><div class="sl">Total calls</div><div class="sv">${{tC}}</div><div class="ss">All consultants combined</div></div>`;
}}
function bC(c,s,e){{
  const eod=new Date(e);eod.setHours(23,59,59,999);
  const ci=c.meetings.filter(m=>m.is_call&&inR(m.date,s,eod));
  const calls=ci.length;
  const dm={{}};ci.forEach(m=>{{dm[m.date]=(dm[m.date]||0)+1;}});
  const days=[];const cur=new Date(s);cur.setHours(12);
  while(cur<=eod){{const k=cur.toISOString().slice(0,10);days.push({{d:k,n:dm[k]||0}});cur.setDate(cur.getDate()+1);}}
  const mx=Math.max(...days.map(x=>x.n),1);
  const sn=days.length<=14;
  const bars=days.map(x=>{{
    const h=x.n>0?Math.max(Math.round((x.n/mx)*40),3):1;
    const op=x.n>0?1:.08;
    const num=x.n>0?`<span class="mbn" style="${{sn?'':'display:none'}}">${{x.n}}</span>`:"";
    return `<div class="mb" style="height:${{h}}px;opacity:${{op}}" title="${{x.d}}: ${{x.n}}"
      onmouseenter="this.querySelector('.mbn')&&(this.querySelector('.mbn').style.display='block')"
      onmouseleave="${{sn?'':"this.querySelector('.mbn')&&(this.querySelector('.mbn').style.display='none')"}}">
      ${{num}}</div>`;
  }}).join("");
  const isFinn=c.name==="Finn Phillips";
  const body=isFinn?
    `<div class="fn-note">Finn joined Jul 2026. BD calls are primarily logged as tasks in RecruitCRM. 1 external prospect meeting logged (James Pickering \u00b7 Unily).</div>`:
    `<div class="note">Intro calls identified by scheduler title pattern. Pipeline data not shown (requires elevated API access).</div>`;
  const html=`<div class="card">
    <div class="ch"><div class="av">${{c.initials}}</div>
      <div><div class="cn">${{c.name}}</div><div class="cr">${{c.role}}</div></div></div>
    <div class="cb">
      <div><div class="secl">${{c.meeting_label}}</div>
        <div class="bx">
          <div class="br"><div class="bl">Calls held</div>
            <div class="bn" style="color:var(--p)">${{calls}}</div></div>
          <div class="bsub">${{c.meeting_note}}</div>
          ${{days.length>1?`<div class="mc"><div class="mbw">${{bars}}</div>
            <div class="mx"><span>${{fS(s)}}</span><span>${{fS(eod)}}</span></div></div>`:""}}
        </div></div>
      ${{body}}
    </div></div>`;
  return {{html,calls,pipe:0,placed:0}};
}}
function applyPreset(d){{
  const {{s,e}}=bR(d);
  document.querySelectorAll(".pb").forEach(b=>b.classList.toggle("on",+b.dataset.d===d));
  render(s,e);
}}
document.querySelectorAll(".pb").forEach(b=>b.addEventListener("click",()=>applyPreset(+b.dataset.d)));
function applyCustom(){{
  const fv=document.getElementById("fd").value,tv=document.getElementById("td").value;
  if(!fv||!tv)return;
  const s=new Date(fv);s.setHours(0,0,0,0);const e=new Date(tv);e.setHours(23,59,59,999);
  if(s>e)return;document.querySelectorAll(".pb").forEach(b=>b.classList.remove("on"));render(s,e);
}}
document.getElementById("fd").addEventListener("change",applyCustom);
document.getElementById("td").addEventListener("change",applyCustom);
applyPreset(30);
</script></body></html>"""

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: RECRUITCRM_API_KEY not set"); sys.exit(1)
    print("Fetching from RecruitCRM...", flush=True)
    data = fetch_all()
    out = Path("docs"); out.mkdir(exist_ok=True)
    (out / "index.html").write_text(build_html(data), encoding="utf-8")
    print(f"Done. Generated at {data['generated_at']}")
