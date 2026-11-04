"""Task 2: collect a job-posting snapshot for each company.

Run from the project root:
    python src/collect.py            # full snapshot, all companies
    python src/collect.py --test     # quick test: few jobs per company

Each run:
  1. checks robots.txt for every source and skips any disallowed path
  2. fetches all open roles from each company's public job feed
  3. saves raw responses to data/raw/<company>/<date>.json (git-ignored)
  4. saves a normalised snapshot to data/raw/<company>/<date>.csv (git-ignored)
  5. updates data/processed/job_tracker.csv (first/last seen per job, no text)

Stdlib only, no installs needed.
"""

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date, datetime, timezone
from pathlib import Path

UA = "CadetX-student-project"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
LEGAL_LOG = ROOT / "docs" / "legal_checks.md"
TODAY = date.today().isoformat()

FIELDS = [
    "job_id", "company_name", "job_title", "job_description", "posting_date",
    "location", "job_url", "department", "employment_type", "salary_range",
    "updated_at", "scraped_date",
]

WD_BASE = "https://nvidia.wd5.myworkdayjobs.com"
WD_API = WD_BASE + "/wday/cxs/nvidia/NVIDIAExternalCareerSite"

COMPANIES = {
    "openai": {
        "source": "ashby",
        "robots": "https://api.ashbyhq.com/robots.txt",
        "url": "https://api.ashbyhq.com/posting-api/job-board/openai?includeCompensation=true",
    },
    "anthropic": {
        "source": "greenhouse",
        "robots": "https://boards-api.greenhouse.io/robots.txt",
        "url": "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true",
    },
    "databricks": {
        "source": "greenhouse",
        "robots": "https://boards-api.greenhouse.io/robots.txt",
        "url": "https://boards-api.greenhouse.io/v1/boards/databricks/jobs?content=true",
    },
    "nvidia": {
        "source": "workday",
        "robots": WD_BASE + "/robots.txt",
        "url": WD_API + "/jobs",
    },
}


# ---------- HTTP helpers ----------

def http(url, data=None, timeout=30):
    headers = {"User-Agent": UA, "Accept": "application/json"}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def robots_allows(robots_url, target_url):
    """RFC 9309: robots.txt that is unavailable (4xx) means no restrictions;
    server errors (5xx) or no connection mean assume full disallow.
    (Python's robotparser treats 401/403 as disallow-all, so this is handled here.)"""
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            lines = r.read().decode(errors="replace").splitlines()
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(lines)
        return rp.can_fetch(UA, target_url), "robots.txt parsed"
    except urllib.error.HTTPError as e:
        if 400 <= e.code < 500 and e.code != 429:
            return True, f"robots.txt HTTP {e.code} (unavailable: no restrictions, RFC 9309)"
        return False, f"robots.txt HTTP {e.code} (assume disallow)"
    except Exception as e:  # network failure
        return False, f"robots.txt unreachable: {e} (assume disallow)"


# ---------- per-source parsers ----------

def fetch_ashby(cfg, test):
    raw = http(cfg["url"])
    jobs = [j for j in raw.get("jobs", []) if j.get("isListed", True)]
    if test:
        jobs = jobs[:5]
    rows = []
    for j in jobs:
        comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
        rows.append({
            "job_id": j.get("id"),
            "job_title": j.get("title"),
            "job_description": j.get("descriptionPlain") or "",
            "posting_date": (j.get("publishedAt") or "")[:10],
            "location": j.get("location"),
            "job_url": j.get("jobUrl"),
            "department": j.get("department"),
            "employment_type": j.get("employmentType"),
            "salary_range": comp,
            "updated_at": "",
        })
    return raw, rows


def fetch_greenhouse(cfg, test):
    raw = http(cfg["url"])
    jobs = raw.get("jobs", [])
    if test:
        jobs = jobs[:5]
    rows = []
    for j in jobs:
        rows.append({
            "job_id": j.get("id"),
            "job_title": j.get("title"),
            # HTML-escaped HTML; cleaned in Task 3
            "job_description": j.get("content") or "",
            "posting_date": (j.get("first_published") or "")[:10],
            "location": (j.get("location") or {}).get("name"),
            "job_url": j.get("absolute_url"),
            "department": "; ".join(d.get("name", "") for d in j.get("departments") or []),
            "employment_type": "",
            "salary_range": "",
            "updated_at": (j.get("updated_at") or "")[:10],
        })
    return raw, rows


def fetch_workday(cfg, test, company_dir):
    """List endpoint pages 20 at a time; descriptions need one request per job,
    so details are cached and only fetched for jobs not seen before."""
    # Workday's "total" is unreliable (shows 2000, and 0 after page 1), and the
    # listing caps at 2000 unique postings then repeats (checked 4 Nov 2026), so
    # page until an empty page or a page with no new job IDs.
    listing, seen, offset, total = [], set(), 0, None
    while True:
        page = http(cfg["url"], {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""})
        posts = page.get("jobPostings", [])
        if total is None:
            total = page.get("total", 0)
        fresh = [p for p in posts if (p.get("bulletFields") or [p.get("externalPath")])[0] not in seen]
        for p in fresh:
            seen.add((p.get("bulletFields") or [p.get("externalPath")])[0])
        listing.extend(fresh)
        offset += 20
        if not fresh or offset >= 10000 or (test and len(listing) >= 5):
            break
        time.sleep(1)
    if test:
        listing = listing[:5]

    cache = company_dir / "details"
    cache.mkdir(parents=True, exist_ok=True)
    rows, new = [], 0
    for p in listing:
        jid = (p.get("bulletFields") or [p.get("externalPath", "").split("_")[-1]])[0]
        cache_file = cache / f"{jid}.json"
        if cache_file.exists():
            info = json.loads(cache_file.read_text())
        else:
            try:
                info = http(WD_API + p["externalPath"]).get("jobPostingInfo", {})
            except Exception as e:
                print(f"  ! detail failed for {jid}: {e}")
                info = {}
            cache_file.write_text(json.dumps(info))
            new += 1
            time.sleep(1)
        rows.append({
            "job_id": jid,
            "job_title": p.get("title"),
            "job_description": info.get("jobDescription", ""),
            "posting_date": info.get("startDate", ""),
            "location": info.get("location") or p.get("locationsText"),
            "job_url": WD_BASE + "/NVIDIAExternalCareerSite" + p.get("externalPath", ""),
            "department": "",
            "employment_type": info.get("timeType", ""),
            "salary_range": "",
            "updated_at": "",
        })
    print(f"  workday: {len(listing)} listed (API total {total}), {new} new detail pages fetched")
    return {"total": total, "jobPostings": listing}, rows


# ---------- tracker (no job text, safe to commit) ----------

def update_tracker(company, rows):
    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = PROCESSED / "job_tracker.csv"
    cols = ["company_name", "job_id", "job_title", "location", "department",
            "posting_date", "first_seen", "last_seen", "job_status"]
    tracker = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                tracker[(r["company_name"], r["job_id"])] = r
    open_now = {str(r["job_id"]) for r in rows}
    for r in rows:
        key = (company, str(r["job_id"]))
        t = tracker.get(key) or {"first_seen": TODAY}
        t.update({
            "company_name": company, "job_id": str(r["job_id"]),
            "job_title": r["job_title"], "location": r["location"],
            "department": r["department"], "posting_date": r["posting_date"],
            "last_seen": TODAY, "job_status": "active",
        })
        tracker[key] = t
    for (c, jid), t in tracker.items():
        if c == company and jid not in open_now:
            t["job_status"] = "closed"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(sorted(tracker.values(), key=lambda t: (t["company_name"], t["job_id"])))


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="fetch ~5 jobs per company")
    ap.add_argument("--only", choices=list(COMPANIES), help="run one company")
    args = ap.parse_args()

    log_lines = []
    for company, cfg in COMPANIES.items():
        if args.only and company != args.only:
            continue
        print(f"[{company}]")
        allowed, reason = robots_allows(cfg["robots"], cfg["url"])
        log_lines.append(f"| {TODAY} | {company} | {cfg['robots']} | {'allowed' if allowed else 'BLOCKED'} | {reason} |")
        if not allowed:
            print(f"  skipped: {reason}")
            continue

        company_dir = RAW / company
        company_dir.mkdir(parents=True, exist_ok=True)
        try:
            if cfg["source"] == "ashby":
                raw, rows = fetch_ashby(cfg, args.test)
            elif cfg["source"] == "greenhouse":
                raw, rows = fetch_greenhouse(cfg, args.test)
            else:
                raw, rows = fetch_workday(cfg, args.test, company_dir)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        for r in rows:
            r["company_name"] = company
            r["scraped_date"] = TODAY
        suffix = "_test" if args.test else ""
        (company_dir / f"{TODAY}{suffix}.json").write_text(json.dumps(raw))
        with (company_dir / f"{TODAY}{suffix}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        if not args.test:
            update_tracker(company, rows)
        print(f"  saved {len(rows)} jobs")

    if not LEGAL_LOG.exists():
        LEGAL_LOG.write_text("# Legal checks log\n\n| Date | Company | robots.txt | Result | Detail |\n|---|---|---|---|---|\n")
    with LEGAL_LOG.open("a") as f:
        f.write("\n".join(log_lines) + "\n")
    print("done", datetime.now(timezone.utc).isoformat(timespec="seconds"))


if __name__ == "__main__":
    main()
