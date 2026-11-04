# Task 2: Data Collection Report

**Project:** Competitor Demand Prediction Using Job Postings (CadetX)
**Author:** Abdul-Haque Mohammed (individual track)
**First snapshot:** 4 November 2026

## 1. Summary

I collected every open job posting for my four companies from their official public job-board feeds, using only the sources approved in Task 1. The first snapshot has **5,182 postings**, with all seven required fields filled for every row and no duplicates. A snapshot now runs automatically every Monday and Thursday until the end of the project, so I can build a real time series (Task 5) and forecast from it (Task 7).

| Company | Role | Source | Postings | Earliest posting date |
|---|---|---|---|---|
| OpenAI | Main specialist | Ashby Job Posting API | 818 | May 2023 |
| Anthropic | Comparison | Greenhouse Job Board API | 682 | Apr 2024 |
| Databricks | Comparison | Greenhouse Job Board API | 926 | Nov 2019 |
| NVIDIA | Comparison | Workday public job search | 2,756 | Dec 2024 |
| **Total** | | | **5,182** | |

## 2. Sources

| Source | Endpoint | Requests per snapshot |
|---|---|---|
| Ashby (OpenAI) | `GET api.ashbyhq.com/posting-api/job-board/openai?includeCompensation=true` | 1 |
| Greenhouse (Anthropic, Databricks) | `GET boards-api.greenhouse.io/v1/boards/{anthropic,databricks}/jobs?content=true` | 1 each |
| Workday (NVIDIA) | `POST nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs`, then one `GET` per new job | ~140 list pages + 1 per new job |

No HTML pages were scraped. All four are the feeds the job-board vendors publish so employers' postings can be shown elsewhere. They need no login and return only what each company chose to make public.

## 3. Legal checks

Every check is done **by the script, every time it runs**, and written to `docs/collection_log.csv` (timestamp, URL, result, rows collected).

| Check | How it's done | Result on 4 Nov 2026 |
|---|---|---|
| robots.txt | `urllib.robotparser` checks the exact URL before each fetch. Disallowed means the company is skipped. 4xx means no robots.txt, so no restrictions (RFC 9309); 5xx means treated as disallowed | Greenhouse: allowed. Workday: allowed. Ashby: no robots.txt (401), so no restrictions |
| Terms of service | Read manually in Task 1 | Feeds are intended for public display of postings; no login or key needed |
| Personal data (UK GDPR) | Only job-level fields are kept. Emails, phone numbers and recruiter names ("Recruiter: Jane Smith") are removed by regex **before anything is saved**. Nothing behind a login, no applicant data | 0 emails and 0 phone numbers found; 12 recruiter names removed (all Databricks). Searched every description for "contact", "recruiter", "email" and "reach out" and checked the matches by hand: none left |
| Copyright | Descriptions are the employer's copyright, used for computational analysis only (CDPA s29A). `data/raw/` and `data/interim/` are git-ignored, so full text never reaches the public repo | Only a 20-row sample per company with descriptions cut to 300 characters is committed |
| Load on the servers | User-Agent `CadetX-student-project`, 1 second between requests, stop on error with no retry loop, NVIDIA job pages fetched once and cached | First NVIDIA run ~80 min; later runs only fetch new jobs |

**Issue found and fixed:** on the first run, NVIDIA's robots.txt returned HTTP 406 because the script asked for JSON. It was treated as "no robots.txt", which is technically correct under RFC 9309 but wasn't a real check. I fixed the request header and re-checked: HTTP 200, path allowed. Both lines are kept in the log.

**Issue found and fixed:** the manual check found Databricks postings naming the recruiter (e.g. "Recruiter: [name]"). I added a name filter for this pattern, re-collected, and re-applied it to the saved NVIDIA files. 12 names removed, none remaining.

## 4. Fields collected

One row per posting, matching the brief's schema.

**Required fields** (100% filled for all four companies):

| Field | OpenAI (Ashby) | Anthropic, Databricks (Greenhouse) | NVIDIA (Workday) |
|---|---|---|---|
| job_id | `id` | `id` | requisition ID, e.g. JR2025344 |
| company_name | set in script | set in script | set in script |
| job_title | `title` | `title` | `title` |
| job_description | `descriptionPlain` | `content` (HTML unescaped, tags stripped) | `jobDescription` (tags stripped) |
| posting_date | `publishedAt` | `first_published` | `startDate` |
| location | `location` | `location.name` | `locationsText` |
| job_url | `jobUrl` | `absolute_url` | `externalUrl` |

**Recommended fields also collected:**

| Field | Coverage |
|---|---|
| department | All four (NVIDIA: job family, e.g. Engineering 1,742, Sales 320) |
| employment_type | OpenAI, NVIDIA |
| workplace_type (remote / hybrid / onsite) | OpenAI |
| salary_range, salary_min, salary_max, salary_currency | OpenAI: 650 of 818 roles (mostly USD; a few GBP, CAD, SGD) |
| updated_at | Anthropic, Databricks |
| scraped_date | All |
| first_seen, last_seen, snapshots_seen, job_status | All, built by `build_dataset.py` across snapshots |
| posting_month, posting_week | All |

**Files:**

| File | Contents | In GitHub? |
|---|---|---|
| `data/raw/{company}/{date}.json` | Raw dataset, one file per company per snapshot | No (copyright) |
| `data/interim/jobs_master.csv` | All snapshots merged, one row per job, with tracking columns | No (copyright) |
| `data/sample/jobs_sample.csv` | 20 rows per company, description cut to 300 characters | Yes |
| `data/sample/snapshot_summary.csv` | Number of postings per company per snapshot | Yes |
| `docs/collection_log.csv` | Every robots.txt check and collection result | Yes |

## 5. Limitations

1. **Survivorship bias.** The feeds only show roles that are open now. Anything that closed before 4 Nov 2026 is missing, so older months look emptier than they really were. Posting dates still go back years for long-open roles, but these are survivors, not the full history. The twice-weekly snapshots fix this from now on: a job that disappears gets marked `closed`.
2. **Short time series.** By the end of the project there will be about 25 snapshots over 3 months. That's enough for short-horizon forecasting (weeks), not 12-month forecasts. The Kaggle dataset (S4) is the planned historical baseline.
3. **NVIDIA posting dates may be refresh dates.** 88% of NVIDIA's roles show a date since August 2026, against 49-69% for the others. Workday's `startDate` may reset when a role is reposted, so NVIDIA can look like it's hiring faster than it is. I'll compare `startDate` with first-seen dates over the coming snapshots before trusting NVIDIA velocity numbers.
4. **Salary only for OpenAI.** Ashby gives structured pay ranges. Anthropic and Databricks put pay inside the description text, so it'll need extracting in Task 4. Some OpenAI values are hourly (intern roles), so they need normalising before comparing.
5. **Different description formats.** Greenhouse and Workday give HTML, Ashby gives plain text. I've stripped tags for all three, but Task 3 has to check they end up at the same quality level so comparisons are fair.
6. **Workday isn't a documented public API.** It can change without notice. It also caps each search at 2,000 results and then repeats page one, which I handle by searching one job family at a time. If it breaks, NVIDIA gets swapped for another AI company on Greenhouse, Lever or Ashby (Task 1, 2.3).
7. **Gaps if a snapshot is missed.** The schedule runs on my Mac, so if it's off for days, those snapshots don't happen. Each missed date is visible in `snapshot_summary.csv`, and the time series in Task 5 will be built on actual snapshot dates rather than assuming a fixed interval.

## 6. How to reproduce

```bash
pip install -r requirements.txt
python src/collect.py          # one snapshot of all four companies
python src/build_dataset.py    # merge snapshots and print quality checks
```
