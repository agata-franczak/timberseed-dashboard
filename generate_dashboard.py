#!/usr/bin/env python3
"""
Timberseed Dashboard Generator
Fetches live data from RecruitCRM and generates dashboard HTML.
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

CONSULTANTS = [
    {"id":140768,"name":"Toby Ranson","initials":"TR","role":"Consultant",
     "pattern":"Introductory Phone Call","label":"Candidate intro calls",
     "note":"Scheduler-booked candidate calls"},
    {"id":143107,"name":"Joe Leonard","initials":"JL","role":"Consultant",
     "pattern":"Joe Leonard x","label":"Candidate intro calls",
     "note":"Scheduler-booked candidate calls"},
    {"id":147065,"name":"Finn Phillips","initials":"FP","role":"Business Development",
     "pattern":None,"label":"BD prospect meetings",
     "note":"External prospect calls (excl. CRM vendor)"},
]

FINN_EXCLUDE = ["eod update","bd daily updates","pt","finn a/l",
                "inbox training","cancelled event","sourcewhale","dhruv"]

STAGE_IDS   = {537163:"CV Sent",537164:"1st Interviews",
               537165:"Further Interviews",537166:"Final Interviews",8:"Placed"}
STAGE_ORDER = ["CV Sent","1st Interviews","Further Interviews","Final Interviews","Placed"]

DAYS_BACK = 90  # fetch 90 days of data; filtering happens client-side

def rc_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS,
                     params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

def paginate(path, params, key, label=""):
    out, page = [], 1
    while True:
        try:
            data = rc_get(path, {**params, "page": page, "limit": 100})
        except requests.HTTPError as e:
            print(f"  {label} HTTP {e.response.status_code} on p{page} — stopping")
            break
        batch = data.get(key, [])
        out.extend(batch)
        print(f"  {label} p{page}: {len(batch)}", flush=True)
        if not data.get("has_more"):
            break
        page += 1
    return out

def fetch_meetings(owner_id):
    """Fetch meetings by owner only — date filtering done in Python."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).date().isoformat()
    raw = paginate("/meetings", {"owner_id": owner_id}, "meetings",
                   f"meetings {owner_id}")
    # filter to last DAYS_BACK days
    filtered = [m for m in raw if (m.get("start_date") or "")[:10] >= cutoff]
    print(f"  after date filter (>={cutoff}): {len(filtered)}")
    return filtered

def classify(raw, consultant):
    out = []
    pat = consultant["pattern"]
    for m in raw:
        t = (m.get("title") or "").replace("&lt;","<").replace("&gt;",">")
        d = (m.get("start_date") or "")[:10]
        if pat:
            is_call = pat in t
        else:
            is_call = not any(p in t.lower() for p in FINN_EXCLUDE)
        out.append({"date": d, "is_call": is_call})
    return out

def fetch_pipeline(owner_id):
    """Owned candidates at key stages."""
    owned = {c.get("slug") for c in
             paginate("/candidates", {"owner_id": owner_id}, "candidates",
                      f"owned {owner_id}") if c.get("slug")}
    print(f"  owned: {len(owned)}")

    try:
        jobs = rc_get("/jobs", {"owner_id": owner_id, "job_status": "1",
                                "limit": 50}).get("jobs", [])
    except Exception as e:
        print(f"  jobs error: {e}"); return []

    pipeline, stage_param = [], ",".join(str(s) for s in STAGE_IDS)
    for job in jobs:
        slug = job.get("slug")
        if not slug: continue
        try:
            cands = rc_get(f"/jobs/{slug}/candidates",
                           {"limit": 100, "status_id": stage_param}
                           ).get("assigned_candidates", [])
        except Exception as e:
            print(f"  job {slug[:10]} error: {e}"); continue
        for c in cands:
            if c.get("candidate_slug") in owned:
                pipeline.append({
                    "name": f"{c.get('first_name','')} {c.get('last_name','')}".strip(),
                    "stage": c.get("status_label",""),
                    "stage_date": (c.get("stage_date") or "")[:10],
                    "job": job.get("name",""),
                })
    return pipeline

def fetch_all():
    now  = datetime.now(timezone.utc)
    data = {"generated_at": now.isoformat(), "consultants": []}
    for c in CONSULTANTS:
        print(f"\n▶ {c['name']}", flush=True)
        raw      = fetch_meetings(c["id"])
        meetings = classify(raw, c)
        calls    = sum(1 for m in meetings if m["is_call"])
        print(f"  calls classified: {calls}")
        if c.get("role") == "Consultant":
            pipeline = fetch_pipeline(c["id"])
        else:
            pipeline = []
        data["consultants"].append({
            "name": c["name"], "initials": c["initials"], "role": c["role"],
            "meeting_label": c["label"], "meeting_note": c["note"],
            "meetings": meetings, "pipeline": pipeline,
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
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--t)}}
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
.fn{{display:flex;flex-direction:column;gap:6px}}
.fr{{display:flex;align-items:center;gap:8px}}
.fl{{width:130px;font-size:12px;color:var(--t2);flex-shrink:0}}
.ft{{flex:1;height:18px;background:var(--bg);border-radius:4px;overflow:hidden}}
.ff{{height:100%;border-radius:4px;transition:width .4s}}
.fnum{{width:24px;font-size:13px;font-weight:700;text-align:right}}
.fnames{{padding-left:138px;font-size:11px;color:var(--t3);margin-top:1px;margin-bottom:2px;line-height:1.4}}
.nodata{{font-size:12px;color:var(--t3);font-style:italic}}
.note{{font-size:11px;color:var(--t3);border-top:1px solid var(--b);padding-top:10px;line-height:1.5}}
.fn-note{{font-size:12px;color:var(--t2);line-height:1.6;background:var(--pl);border-radius:var(--rs);padding:.75rem 1rem}}
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
const SC={{"CV Sent":"#534AB7","1st Interviews":"#185FA5","Further Interviews":"#0F6E56","Final Interviews":"#854F0B","Placed":"#1D9E75"}};
const SO=["CV Sent","1st Interviews","Further Interviews","Final Interviews","Placed"];
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
  let tC=0,tP=0,tPl=0;
  const cards=D.consultants.map(c=>{{const r=bC(c,s,e);tC+=r.calls;tP+=r.pipe;tPl+=r.placed;return r;}});
  document.getElementById("grid").innerHTML=cards.map(c=>c.html).join("");
  document.getElementById("sg").innerHTML=`
    <div class="sc"><div class="sl">Total calls</div><div class="sv">${{tC}}</div><div class="ss">All consultants</div></div>
    <div class="sc"><div class="sl">At key stages</div><div class="sv">${{tP}}</div><div class="ss">Owned pipeline</div></div>
    <div class="sc"><div class="sl">Placed</div><div class="sv">${{tPl}}</div><div class="ss">In period</div></div>`;
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
  const byS={{}};SO.forEach(st=>byS[st]=[]);
  c.pipeline.filter(p=>inR(p.stage_date,s,eod)).forEach(p=>{{if(byS[p.stage])byS[p.stage].push(p);}});
  const pipe=c.pipeline.filter(p=>inR(p.stage_date,s,eod)).length;
  const placed=byS["Placed"].length;
  const mxP=Math.max(...SO.map(st=>byS[st].length),1);
  const funnel=SO.map(st=>{{
    const ca=byS[st];const pct=Math.round((ca.length/mxP)*100);
    const nm=ca.slice(0,4).map(p=>{{
      const pts=p.name.split(" ");const sh=pts[0]+(pts[1]?" "+pts[1][0]+".":"");
      const pd=p.stage_date?new Date(p.stage_date):null;
      return sh+(pd?" ("+pd.toLocaleDateString("en-GB",{{day:"numeric",month:"short"}})+")":"");
    }}).join(" \u00b7 ");
    return `<div class="fr"><div class="fl">${{st}}</div>
      <div class="ft"><div class="ff" style="width:${{pct}}%;background:${{SC[st]}}"></div></div>
      <div class="fnum">${{ca.length}}</div></div>
      ${{nm?`<div class="fnames">${{nm}}</div>`:""}}`;
  }}).join("");
  const isFinn=c.name==="Finn Phillips";
  const body=isFinn?
    `<div class="fn-note">Finn joined Jul 2026. BD calls are logged as tasks in RecruitCRM rather than meetings. 1 confirmed external prospect call (James Pickering \u00b7 Unily) this period.</div>`:
    `<div><div class="secl">Owned candidates at key stages</div>
      ${{pipe===0?`<div class="nodata">No owned candidates moved to key stages in this period.</div>`:
        `<div class="fn">${{funnel}}</div>`}}</div>
    <div class="note">Pipeline covers active client jobs. Stage dates reflect when candidate last moved.</div>`;
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
  return {{html,calls,pipe,placed}};
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
  if(s>e)return;
  document.querySelectorAll(".pb").forEach(b=>b.classList.remove("on"));
  render(s,e);
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
    print(f"\nDone. Generated at {data['generated_at']}")
