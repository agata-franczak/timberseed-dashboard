#!/usr/bin/env python3
"""
Timberseed Dashboard Generator
Fetches live data from RecruitCRM and generates a self-contained HTML dashboard.
Reads RECRUITCRM_API_KEY from environment variable.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing dependency: requests. Run: pip install requests")
    sys.exit(1)

# ── Config ───────────────────────────────────────────────────────────────────

API_KEY  = os.environ.get("RECRUITCRM_API_KEY", "")
BASE_URL = "https://api.recruitcrm.io/v1"
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

CONSULTANTS = [
    {
        "id": 140768, "name": "Toby Ranson", "initials": "TR",
        "role": "Consultant",
        "meeting_pattern": "Introductory Phone Call",
        "meeting_label": "Candidate intro calls",
        "meeting_note": "Scheduler-booked candidate calls",
        "dist_slug": "17798857082070098322oYJ",
    },
    {
        "id": 143107, "name": "Joe Leonard", "initials": "JL",
        "role": "Consultant",
        "meeting_pattern": "Joe Leonard x",
        "meeting_label": "Candidate intro calls",
        "meeting_note": "Scheduler-booked candidate calls",
        "dist_slug": "17809259732490098322VkM",
    },
    {
        "id": 147065, "name": "Finn Phillips", "initials": "FP",
        "role": "Business Development",
        "meeting_pattern": None,
        "meeting_label": "BD prospect meetings",
        "meeting_note": "External prospect calls (excl. CRM vendor)",
        "dist_slug": None,
    },
]

FINN_EXCLUDE = [
    "eod update", "bd daily updates", "pt", "finn a/l",
    "inbox training", "cancelled event", "sourcewhale", "dhruv",
]

STAGE_IDS   = {537163: "CV Sent", 537164: "1st Interviews",
               537165: "Further Interviews", 537166: "Final Interviews", 8: "Placed"}
STAGE_ORDER = ["CV Sent", "1st Interviews", "Further Interviews", "Final Interviews", "Placed"]

# ── API helpers ───────────────────────────────────────────────────────────────

def rc_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS,
                     params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

def paginate(path, params, key, label=""):
    out, page = [], 1
    while True:
        data = rc_get(path, {**params, "page": page, "limit": 100})
        batch = data.get(key, [])
        out.extend(batch)
        print(f"  {label} p{page}: {len(batch)}", flush=True)
        if not data.get("has_more"):
            break
        page += 1
    return out

# ── Fetch meetings ────────────────────────────────────────────────────────────

def fetch_meetings(owner_id, days=90):
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return paginate("/meetings",
                    {"owner_id": owner_id,
                     "starting_from": start.strftime("%Y-%m-%d"),
                     "starting_to":   end.strftime("%Y-%m-%d")},
                    "meetings", f"meetings owner={owner_id}")

def classify_meetings(raw, consultant):
    out = []
    pattern = consultant["meeting_pattern"]
    for m in raw:
        t = (m.get("title") or "").replace("&lt;","<").replace("&gt;",">")
        d = (m.get("start_date") or "")[:10]
        if pattern:
            is_call = pattern in t
        else:
            # Finn: any meeting not matching exclusions
            is_call = not any(p in t.lower() for p in FINN_EXCLUDE)
        out.append({"date": d, "is_call": is_call})
    return out

# ── Fetch distribution job ────────────────────────────────────────────────────

def fetch_dist_job(slug):
    if not slug:
        return None, []
    cands = paginate(f"/jobs/{slug}/candidates", {}, "assigned_candidates",
                     f"dist {slug[:12]}")
    stages = {}
    for c in cands:
        lbl = c.get("status_label", "Unknown")
        stages[lbl] = stages.get(lbl, 0) + 1
    return len(cands), [{"stage": k, "count": v} for k, v in stages.items()]

# ── Fetch pipeline ────────────────────────────────────────────────────────────

def fetch_pipeline(owner_id):
    """Get owned candidates currently at key stages across all this consultant's jobs."""
    # Get owned candidate slugs
    owned = {c["slug"] for c in paginate("/candidates",
             {"owner_id": owner_id}, "candidates", f"owned owner={owner_id}")
             if c.get("slug")}

    # Get active jobs owned by this consultant
    jobs = rc_get("/jobs", {"owner_id": owner_id, "limit": 50,
                             "job_status": "1"}).get("jobs", [])

    pipeline = []
    for job in jobs:
        slug = job.get("slug")
        if not slug:
            continue
        stage_param = ",".join(str(s) for s in STAGE_IDS)
        cands = rc_get(f"/jobs/{slug}/candidates",
                       {"limit": 100, "status_id": stage_param}
                       ).get("assigned_candidates", [])
        for c in cands:
            if c.get("candidate_slug") in owned:
                pipeline.append({
                    "name":       f"{c.get('first_name','')} {c.get('last_name','')}".strip(),
                    "stage":      c.get("status_label", ""),
                    "stage_date": (c.get("stage_date") or "")[:10],
                    "job":        job.get("name", ""),
                })
    return pipeline

# ── Main fetch ────────────────────────────────────────────────────────────────

def fetch_all():
    now = datetime.now(timezone.utc)
    data = {"generated_at": now.isoformat(), "consultants": []}

    for c in CONSULTANTS:
        print(f"\n▶ {c['name']}", flush=True)

        raw = fetch_meetings(c["id"])
        meetings = classify_meetings(raw, c)

        dist_total, dist_stages = fetch_dist_job(c["dist_slug"])

        if c["dist_slug"]:
            pipeline = fetch_pipeline(c["id"])
        else:
            pipeline = []

        data["consultants"].append({
            "name":                 c["name"],
            "initials":             c["initials"],
            "role":                 c["role"],
            "meeting_label":        c["meeting_label"],
            "meeting_note":         c["meeting_note"],
            "meetings":             meetings,
            "dist_total":           dist_total,
            "dist_stages":          dist_stages,
            "pipeline":             pipeline,
        })

    return data

# ── HTML ──────────────────────────────────────────────────────────────────────

def build_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Timberseed · Dashboard</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--purple:#534AB7;--purple-mid:#7F77DD;--purple-light:#EEEDFE;
  --teal:#1D9E75;--blue:#185FA5;
  --text:#0f172a;--text2:#475569;--text3:#94a3b8;
  --bg:#f8fafc;--surface:#fff;--border:#e2e8f0;--r:10px;--rs:6px}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;
  background:var(--bg);color:var(--text);min-height:100vh}}
/* header */
.hdr{{background:var(--surface);border-bottom:1px solid var(--border);
  padding:1rem 1.5rem;display:flex;justify-content:space-between;
  align-items:center;position:sticky;top:0;z-index:50;gap:12px;flex-wrap:wrap}}
.logo{{display:flex;align-items:center;gap:10px}}
.lm{{width:34px;height:34px;border-radius:8px;background:var(--purple);
  display:flex;align-items:center;justify-content:center;
  font-size:12px;font-weight:700;color:#fff}}
.ln{{font-size:15px;font-weight:600}}.ls{{font-size:12px;color:var(--text3);margin-top:1px}}
.gen{{font-size:11px;color:var(--text3)}}
/* controls */
.ctrl{{background:var(--surface);border-bottom:1px solid var(--border);
  padding:.875rem 1.5rem;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.cl{{font-size:12px;font-weight:500;color:var(--text2)}}
.presets{{display:flex;gap:6px;flex-wrap:wrap}}
.pb{{font-size:12px;font-weight:500;padding:4px 12px;border-radius:20px;
  border:1px solid var(--border);background:var(--surface);color:var(--text2);
  cursor:pointer;transition:all .15s}}
.pb:hover{{border-color:var(--purple);color:var(--purple)}}
.pb.on{{background:var(--purple);border-color:var(--purple);color:#fff}}
.sep{{width:1px;height:22px;background:var(--border);flex-shrink:0}}
.cust{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.cust label{{font-size:12px;color:var(--text3)}}
.cust input[type=date]{{font-size:12px;padding:4px 8px;border:1px solid var(--border);
  border-radius:var(--rs);color:var(--text);background:var(--surface);
  cursor:pointer;font-family:inherit}}
.ri{{font-size:11px;color:var(--text3);margin-left:auto}}
/* layout */
.main{{padding:1.25rem 1.5rem}}
.sg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:12px;margin-bottom:1.25rem}}
.sc{{background:var(--surface);border:1px solid var(--border);
  border-radius:var(--rs);padding:.875rem 1rem}}
.sl{{font-size:10px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;
  color:var(--text3);margin-bottom:5px}}
.sv{{font-size:24px;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums}}
.ss{{font-size:11px;color:var(--text3);margin-top:3px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}}
/* card */
.card{{background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r);overflow:hidden}}
.ch{{padding:1rem 1.25rem;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:12px}}
.av{{width:40px;height:40px;border-radius:50%;background:var(--purple-light);
  display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;color:var(--purple);flex-shrink:0}}
.cn{{font-size:15px;font-weight:600}}.cr{{font-size:12px;color:var(--text3);margin-top:1px}}
.cb{{padding:1rem 1.25rem;display:flex;flex-direction:column;gap:16px}}
.secl{{font-size:10px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;
  color:var(--text3);margin-bottom:8px}}
.bx{{background:var(--bg);border:1px solid var(--border);border-radius:var(--rs);padding:.875rem 1rem}}
.br{{display:flex;justify-content:space-between;align-items:baseline}}
.bl{{font-size:13px;color:var(--text2)}}
.bn{{font-size:28px;font-weight:700;font-variant-numeric:tabular-nums}}
.bsub{{font-size:11px;color:var(--text3);margin-top:4px}}
/* chart */
.mc{{margin-top:10px}}
.mb-wrap{{display:flex;align-items:flex-end;gap:2px;height:44px}}
.mb{{flex:1;background:var(--purple-mid);border-radius:2px 2px 0 0;
  min-width:2px;position:relative;cursor:default;transition:background .1s}}
.mb:hover{{background:var(--purple)}}
.mb-n{{position:absolute;top:-14px;left:50%;transform:translateX(-50%);
  font-size:7px;font-weight:700;color:var(--text2);white-space:nowrap;line-height:1}}
.mx{{display:flex;justify-content:space-between;font-size:9px;color:var(--text3);margin-top:3px}}
/* stage bar */
.sb{{display:flex;height:6px;border-radius:3px;overflow:hidden;
  margin-top:8px;background:var(--border)}}
.ss-seg{{height:100%}}
.sl2{{display:flex;gap:10px;margin-top:6px;flex-wrap:wrap}}
.leg{{display:flex;align-items:center;gap:4px;font-size:11px;color:var(--text3)}}
.ld{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
/* funnel */
.fn{{display:flex;flex-direction:column;gap:6px}}
.fr{{display:flex;align-items:center;gap:8px}}
.fl{{width:130px;font-size:12px;color:var(--text2);flex-shrink:0}}
.ft{{flex:1;height:18px;background:var(--bg);border-radius:4px;overflow:hidden}}
.ff{{height:100%;border-radius:4px;transition:width .4s ease}}
.fnum{{width:24px;font-size:13px;font-weight:700;font-variant-numeric:tabular-nums;text-align:right}}
.fnames{{padding-left:138px;font-size:11px;color:var(--text3);
  margin-top:1px;margin-bottom:2px;line-height:1.4}}
.nodata{{font-size:12px;color:var(--text3);font-style:italic}}
.note{{font-size:11px;color:var(--text3);border-top:1px solid var(--border);
  padding-top:10px;line-height:1.5}}
.finn-note{{font-size:12px;color:var(--text2);line-height:1.6;
  background:var(--purple-light);border-radius:var(--rs);padding:.75rem 1rem}}
</style>
</head>
<body>
<header class="hdr">
  <div class="logo">
    <div class="lm">TS</div>
    <div><div class="ln">Timberseed</div><div class="ls">Consultant Performance Dashboard</div></div>
  </div>
  <div class="gen" id="gen-at"></div>
</header>
<div class="ctrl">
  <span class="cl">Period:</span>
  <div class="presets" id="presets">
    <button class="pb" data-days="7">7 days</button>
    <button class="pb" data-days="14">14 days</button>
    <button class="pb on" data-days="30">30 days</button>
    <button class="pb" data-days="60">60 days</button>
    <button class="pb" data-days="90">90 days</button>
  </div>
  <div class="sep"></div>
  <div class="cust">
    <label>From</label><input type="date" id="from-date">
    <label>to</label><input type="date" id="to-date">
  </div>
  <div class="ri" id="ri"></div>
</div>
<main class="main">
  <div class="sg" id="sg"></div>
  <div class="grid" id="grid"></div>
</main>
<script>
const DATA={data_json};
const SC={{"CV Sent":"#534AB7","1st Interviews":"#185FA5",
  "Further Interviews":"#0F6E56","Final Interviews":"#854F0B","Placed":"#1D9E75"}};
const SO=["CV Sent","1st Interviews","Further Interviews","Final Interviews","Placed"];
function dt(s){{const d=new Date(s);d.setHours(12);return d;}}
function inR(ds,s,e){{if(!ds)return false;const d=dt(ds);return d>=s&&d<=e;}}
function fmt(d){{return d.toLocaleDateString("en-GB",{{day:"numeric",month:"short",year:"numeric"}});}}
function fmtS(d){{return d.toLocaleDateString("en-GB",{{day:"numeric",month:"short"}});}}
function bldR(days){{
  const e=new Date();e.setHours(23,59,59,999);
  const s=new Date();s.setDate(s.getDate()-days);s.setHours(0,0,0,0);
  return {{s,e}};
}}
function render(s,e){{
  const gen=new Date(DATA.generated_at);
  document.getElementById("gen-at").textContent=
    "Updated "+gen.toLocaleDateString("en-GB",{{day:"numeric",month:"short",year:"numeric"}})
    +" "+gen.toLocaleTimeString("en-GB",{{hour:"2-digit",minute:"2-digit"}})+" UTC";
  document.getElementById("ri").textContent=fmt(s)+" – "+fmt(e);
  document.getElementById("from-date").value=s.toISOString().slice(0,10);
  document.getElementById("to-date").value=e.toISOString().slice(0,10);
  let tC=0,tD=0,tP=0,tPl=0;
  const cards=DATA.consultants.map(c=>{{
    const r=bldCard(c,s,e);
    tC+=r.calls;if(c.dist_total)tD+=c.dist_total;tP+=r.pipe;tPl+=r.placed;
    return r;
  }});
  document.getElementById("grid").innerHTML=cards.map(c=>c.html).join("");
  document.getElementById("sg").innerHTML=`
    <div class="sc"><div class="sl">Total calls</div><div class="sv">${{tC}}</div>
      <div class="ss">All consultants</div></div>
    <div class="sc"><div class="sl">Distribution</div><div class="sv">${{tD}}</div>
      <div class="ss">Candidates assigned</div></div>
    <div class="sc"><div class="sl">At key stages</div><div class="sv">${{tP}}</div>
      <div class="ss">Owned pipeline</div></div>
    <div class="sc"><div class="sl">Placed</div><div class="sv">${{tPl}}</div>
      <div class="ss">In period</div></div>`;
}}
function bldCard(c,s,e){{
  const eod=new Date(e);eod.setHours(23,59,59,999);
  const ci=c.meetings.filter(m=>m.is_call&&inR(m.date,s,eod));
  const calls=ci.length;
  const dm={{}};ci.forEach(m=>{{dm[m.date]=(dm[m.date]||0)+1;}});
  const days=[];const cur=new Date(s);cur.setHours(12);
  while(cur<=eod){{const k=cur.toISOString().slice(0,10);days.push({{d:k,n:dm[k]||0}});cur.setDate(cur.getDate()+1);}}
  const mxD=Math.max(...days.map(x=>x.n),1);
  const sn=days.length<=14;
  const bars=days.map(x=>{{
    const h=x.n>0?Math.max(Math.round((x.n/mxD)*40),3):1;
    const op=x.n>0?1:.08;
    const num=x.n>0?(sn?`<span class="mb-n">${{x.n}}</span>`:`<span class="mb-n" style="display:none">${{x.n}}</span>`):"";
    return `<div class="mb" style="height:${{h}}px;opacity:${{op}}" title="${{x.d}}: ${{x.n}}"
      onmouseenter="this.querySelector('.mb-n')&&(this.querySelector('.mb-n').style.display='block')"
      onmouseleave="${{sn?'':"this.querySelector('.mb-n')&&(this.querySelector('.mb-n').style.display='none')"}}">
      ${{num}}</div>`;
  }}).join("");
  const byS={{}};SO.forEach(st=>byS[st]=[]);
  c.pipeline.filter(p=>inR(p.stage_date,s,eod)).forEach(p=>{{if(byS[p.stage])byS[p.stage].push(p);}});
  const pipe=c.pipeline.filter(p=>inR(p.stage_date,s,eod)).length;
  const placed=byS["Placed"].length;
  const mxP=Math.max(...SO.map(st=>byS[st].length),1);
  let distHtml="";
  if(c.dist_total!=null){{
    const segs=c.dist_stages.map(ds=>{{
      const col=ds.stage==="Assigned"?"#CECBF6":"#534AB7";
      return `<div class="ss-seg" style="flex:${{ds.count}};background:${{col}}" title="${{ds.stage}}: ${{ds.count}}"></div>`;
    }}).join("");
    const legs=c.dist_stages.map(ds=>{{
      const col=ds.stage==="Assigned"?"#CECBF6":"#534AB7";
      return `<div class="leg"><div class="ld" style="background:${{col}}"></div>${{ds.stage}}: ${{ds.count}}</div>`;
    }}).join("");
    distHtml=`<div><div class="secl">Distribution job — current</div>
      <div class="bx"><div class="br"><div class="bl">${{c.name.split(" ")[0]}}'s dist. job</div>
        <div class="bn">${{c.dist_total}}</div></div>
        <div class="bsub">candidates assigned</div>
        <div class="sb">${{segs}}</div><div class="sl2">${{legs}}</div></div></div>`;
  }}
  const funnelHtml=SO.map(st=>{{
    const cands=byS[st];
    const pct=Math.round((cands.length/mxP)*100);
    const names=cands.slice(0,4).map(p=>{{
      const pts=p.name.split(" ");
      const sh=pts[0]+(pts[1]?" "+pts[1][0]+".":"");
      const pd=p.stage_date?new Date(p.stage_date):null;
      return sh+(pd?" ("+pd.toLocaleDateString("en-GB",{{day:"numeric",month:"short"}})+")":"");
    }}).join(" · ");
    return `<div class="fr"><div class="fl">${{st}}</div>
      <div class="ft"><div class="ff" style="width:${{pct}}%;background:${{SC[st]}}"></div></div>
      <div class="fnum">${{cands.length}}</div></div>
      ${{names?`<div class="fnames">${{names}}</div>`:""}}`;
  }}).join("");
  const isFinn=c.name==="Finn Phillips";
  const body=isFinn?
    `<div class="finn-note">Finn joined Jul 2026. BD calls are logged as tasks in RecruitCRM
      rather than meetings — see task log for full call activity.
      1 confirmed external prospect call (James Pickering · Unily) in this period.</div>`:
    `<div><div class="secl">Owned candidates at key stages — period</div>
      ${{pipe===0?`<div class="nodata">No owned candidates moved to key stages in this period.</div>`:
        `<div class="fn">${{funnelHtml}}</div>`}}
    </div>
    <div class="note">Pipeline covers active client jobs. Stage dates reflect when candidate last moved.</div>`;
  const html=`<div class="card">
    <div class="ch"><div class="av">${{c.initials}}</div>
      <div><div class="cn">${{c.name}}</div><div class="cr">${{c.role}}</div></div></div>
    <div class="cb">
      <div><div class="secl">${{c.meeting_label}}</div>
        <div class="bx">
          <div class="br"><div class="bl">Calls held</div>
            <div class="bn" style="color:var(--purple)">${{calls}}</div></div>
          <div class="bsub">${{c.meeting_note}}</div>
          ${{days.length>1?`<div class="mc"><div class="mb-wrap">${{bars}}</div>
            <div class="mx"><span>${{fmtS(s)}}</span><span>${{fmtS(eod)}}</span></div></div>`:""}}
        </div></div>
      ${{distHtml}}
      ${{body}}
    </div></div>`;
  return {{html,calls,pipe,placed}};
}}
function applyPreset(days){{
  const {{s,e}}=bldR(days);
  document.querySelectorAll(".pb").forEach(b=>b.classList.toggle("on",+b.dataset.days===days));
  render(s,e);
}}
document.querySelectorAll(".pb").forEach(b=>b.addEventListener("click",()=>applyPreset(+b.dataset.days)));
function applyCustom(){{
  const fv=document.getElementById("from-date").value,tv=document.getElementById("to-date").value;
  if(!fv||!tv)return;
  const s=new Date(fv);s.setHours(0,0,0,0);
  const e=new Date(tv);e.setHours(23,59,59,999);
  if(s>e)return;
  document.querySelectorAll(".pb").forEach(b=>b.classList.remove("on"));
  render(s,e);
}}
document.getElementById("from-date").addEventListener("change",applyCustom);
document.getElementById("to-date").addEventListener("change",applyCustom);
applyPreset(30);
</script>
</body>
</html>"""

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: RECRUITCRM_API_KEY environment variable not set.")
        sys.exit(1)

    print("Fetching data from RecruitCRM...", flush=True)
    data = fetch_all()

    out_dir = Path("docs")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "index.html"
    out_file.write_text(build_html(data), encoding="utf-8")

    print(f"\nDone. Dashboard saved to {out_file}")
    print(f"Generated at: {data['generated_at']}")
