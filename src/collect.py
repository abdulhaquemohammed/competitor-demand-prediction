"""
Task 2: Data Collection
Takes one snapshot of open job postings for OpenAI, Anthropic, Databricks and NVIDIA
from their public job-board feeds (approved in Task 1) and saves them to
data/raw/{company}/{YYYY-MM-DD}.json

Run:  python src/collect.py            (all companies)
      python src/collect.py openai     (one company)
"""
import csv
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LOG = ROOT / "docs" / "collection_log.csv"
UA = "CadetX-student-project"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json"})

# ---------------------------------------------------------------- legal checks

def robots_allowed(url):
    """Check robots.txt before every fetch. Returns (allowed, note)."""
    p = urlparse(url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        r = session.get(robots_url, timeout=20, headers={"Accept": "text/plain, */*"})
    except requests.RequestException as e:
        return False, f"robots.txt unreachable ({e.__class__.__name__}), not fetching"
    if 400 <= r.status_code < 500:
        # RFC 9309: 4xx (unavailable) means no restrictions apply
        return True, f"robots.txt HTTP {r.status_code}: unavailable, no restrictions (RFC 9309)"
    if r.status_code >= 500:
        # RFC 9309: 5xx (unreachable) means assume complete disallow
        return False, f"robots.txt HTTP {r.status_code}: server error, assume disallowed"
    rp = robotparser.RobotFileParser()
    rp.parse(r.text.splitlines())
    ok = rp.can_fetch(UA, url)
    return ok, f"robots.txt HTTP 200: {'allowed' if ok else 'DISALLOWED'} for {p.path}"


def log_check(company, url, allowed, note, n_jobs=""):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp_utc", "company", "url", "robots_allowed", "note", "jobs_collected"])
        w.writerow([NOW, company, url, allowed, note, n_jobs])

# ---------------------------------------------------------------- personal data

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# "Recruiter: Jane Smith" style lines (names after a hiring-contact label)
NAME = re.compile(r"(?i:\b(recruiter|recruiting contact|talent partner|sourcer|hiring manager|point of contact))(\s*[:\-\u2013]\s*)[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)?")
PHONE = re.compile(r"(?<![\w=/&?.-])(?:\+\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]\d{3,4}[\s.-]\d{3,4}(?!\w)")

def redact(text):
    """Remove emails and phone numbers so no personal contact data is ever stored."""
    if not text:
        return text
    text = EMAIL.sub("[EMAIL_REMOVED]", text)
    text = NAME.sub(r"\1\2[NAME_REMOVED]", text)
    return PHONE.sub("[PHONE_REMOVED]", text)

# ---------------------------------------------------------------- record builder

def record(**kw):
    """One row in the brief's schema (required fields first, then recommended)."""
    base = dict(job_id=None, company_name=None, job_title=None, job_description=None,
                posting_date=None, location=None, job_url=None,
                employment_type=None, department=None, workplace_type=None,
                salary_range=None, salary_min=None, salary_max=None, salary_currency=None,
                updated_at=None, scraped_date=TODAY, source=None)
    base.update(kw)
    base["job_description"] = redact(base["job_description"])
    return base

# ---------------------------------------------------------------- sources

def get_json(url, **kw):
    r = session.get(url, timeout=60, **kw)
    r.raise_for_status()
    return r.json()


def ashby(company, board):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
    ok, note = robots_allowed(url)
    if not ok:
        log_check(company, url, ok, note); return None
    jobs = get_json(url)["jobs"]
    out = []
    for j in jobs:
        if not j.get("isListed", True):
            continue  # only collect publicly listed roles
        comp = j.get("compensation") or {}
        smin = smax = cur = None
        for tier in comp.get("compensationTiers", []):
            for c in tier.get("components", []):
                if c.get("compensationType") == "Salary" and c.get("minValue"):
                    smin, smax, cur = c["minValue"], c.get("maxValue"), c.get("currencyCode")
                    break
            if smin:
                break
        out.append(record(
            job_id=j["id"], company_name=company, job_title=j["title"],
            job_description=j.get("descriptionPlain"), posting_date=j.get("publishedAt"),
            location=j.get("location"), job_url=j.get("jobUrl"),
            employment_type=j.get("employmentType"), department=j.get("department"),
            workplace_type=j.get("workplaceType"),
            salary_range=comp.get("scrapeableCompensationSalarySummary"),
            salary_min=smin, salary_max=smax, salary_currency=cur, source="ashby"))
    log_check(company, url, ok, note, len(out))
    return out


TAG = re.compile(r"<[^>]+>")

def greenhouse(company, board):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    ok, note = robots_allowed(url)
    if not ok:
        log_check(company, url, ok, note); return None
    jobs = get_json(url)["jobs"]
    out = []
    for j in jobs:
        # Greenhouse returns HTML that is itself HTML-escaped: unescape, then keep the
        # HTML (full cleaning is Task 3), but also store a plain-text version.
        raw_html = html.unescape(j.get("content") or "")
        plain = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", raw_html))).strip()
        depts = [d["name"] for d in j.get("departments", [])]
        out.append(record(
            job_id=str(j["id"]), company_name=company, job_title=j["title"],
            job_description=plain, posting_date=j.get("first_published"),
            location=(j.get("location") or {}).get("name"), job_url=j.get("absolute_url"),
            department="; ".join(depts) or None, updated_at=j.get("updated_at"),
            source="greenhouse"))
    log_check(company, url, ok, note, len(out))
    return out


WD_BASE = "https://nvidia.wd5.myworkdayjobs.com"
WD_SITE = "/wday/cxs/nvidia/NVIDIAExternalCareerSite"

def workday_nvidia(company="NVIDIA", delay=1.0):
    list_url = WD_BASE + WD_SITE + "/jobs"
    ok, note = robots_allowed(list_url)
    if not ok:
        log_check(company, list_url, ok, note); return None

    # 1) list every open role (20 per page).
    # Workday caps any one search at 2000 results and then loops back to page 1,
    # so search one job family at a time (each family is under 2000) and stop
    # at that family's count. De-duplicate by job ID.
    def search(facets, offset):
        r = session.post(list_url, json={"appliedFacets": facets, "limit": 20,
                                         "offset": offset, "searchText": ""}, timeout=60)
        r.raise_for_status()
        return r.json()

    first = search({}, 0)
    families = next(f["values"] for f in first["facets"] if f["facetParameter"] == "jobFamilyGroup")
    listing, skipped = {}, 0
    for fam in families:
        n = min(fam["count"], 2000)
        for offset in range(0, n, 20):
            for p in search({"jobFamilyGroup": [fam["id"]]}, offset).get("jobPostings", []):
                if not p.get("title") or not p.get("externalPath"):
                    skipped += 1  # Workday occasionally returns incomplete entries
                    continue
                jid = (p.get("bulletFields") or [p["externalPath"].rsplit("_", 1)[-1]])[0]
                p["_family"] = fam["descriptor"]
                listing[jid] = p
            time.sleep(delay)
    total_reported = sum(f["count"] for f in families)

    # 2) fetch the description page only for job IDs we have not seen before
    cache_dir = RAW / "nvidia" / "details"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out, fetched = [], 0
    for jid, p in listing.items():
        cache = cache_dir / f"{jid}.json"
        if cache.exists():
            info = json.loads(cache.read_text())
        else:
            try:
                info = get_json(WD_BASE + WD_SITE + p["externalPath"])["jobPostingInfo"]
            except requests.RequestException:
                info = {}  # skip description this time, retried next snapshot
            else:
                info["jobDescription"] = redact(info.get("jobDescription"))
                cache.write_text(json.dumps(info))
            fetched += 1
            time.sleep(delay)
        desc_html = info.get("jobDescription") or ""
        plain = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", desc_html))).strip() or None
        out.append(record(
            job_id=jid, company_name=company, job_title=p["title"], job_description=plain,
            posting_date=info.get("startDate"), location=p.get("locationsText"),
            job_url=info.get("externalUrl") or f"{WD_BASE}/NVIDIAExternalCareerSite{p['externalPath']}",
            employment_type=info.get("timeType"), department=p["_family"], source="workday"))
    log_check(company, list_url, ok,
              note + f"; Workday reported {total_reported}; {fetched} new detail pages; "
                     f"{skipped} incomplete list entries skipped", len(out))
    return out


COMPANIES = {
    "openai":     lambda: ashby("OpenAI", "openai"),
    "anthropic":  lambda: greenhouse("Anthropic", "anthropic"),
    "databricks": lambda: greenhouse("Databricks", "databricks"),
    "nvidia":     lambda: workday_nvidia(),
}

# ---------------------------------------------------------------- main

def main(names):
    failed = []
    for name in names:
        try:
            rows = COMPANIES[name]()
        except Exception as e:
            # one company failing must not stop the others; no retry loop (Task 1, 3.5)
            print(f"[{name}] FAILED: {e.__class__.__name__}: {e}")
            log_check(name, "-", "-", f"failed: {e.__class__.__name__}: {e}")
            failed.append(name)
            continue
        if rows is None:
            print(f"[{name}] skipped: robots.txt disallows")
            continue
        path = RAW / name / f"{TODAY}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        print(f"[{name}] {len(rows)} postings -> {path.relative_to(ROOT)}")
        time.sleep(1)
    return failed


if __name__ == "__main__":
    failed = main(sys.argv[1:] or list(COMPANIES))
    sys.exit(1 if failed else 0)  # non-zero so the scheduler shows the failure
