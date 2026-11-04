# Task 1: Understanding Data Sources & Legal

**Project:** Competitor Demand Prediction Using Job Postings (CadetX)
**Author:** Abdul-Haque Mohammed (individual track)
**Date:** November 2026 (corrected 4 Nov 2026 after the first live collection run, see section 5)

## 1. Scope

I'm on the individual track, so I cover four companies myself. One of them is my main specialist company, and the other three are there so I can do the competitor comparison (Task 6) and similarity scoring (Task 8).

| Role | Company | Why |
|---|---|---|
| Main specialist | OpenAI | Large volume of open roles, public job-board API, and the API returns pay ranges for most roles (salary benchmarking) |
| Comparison | Anthropic | Direct competitor, public job-board API |
| Comparison | Databricks | Data/AI platform company, public job-board API |
| Comparison | NVIDIA | Hardware/AI infrastructure angle, so the comparison isn't just three model labs (see conditions in 2.3) |

## 2. Data sources assessed

### 2.1 Approved sources

| # | Source | Access | Covers | Status |
|---|---|---|---|---|
| S1 | Ashby public Job Posting API: `GET https://api.ashbyhq.com/posting-api/job-board/openai?includeCompensation=true` | Public, no login or key | OpenAI | **Approved** |
| S2 | Greenhouse Job Board API: `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | Public, no login or key | Anthropic, Databricks | **Approved** |
| S3 | Workday public job search: `POST https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs` | Public, no login | NVIDIA | **Approved with conditions** (see 2.3) |
| S4 | Kaggle: *LinkedIn Job Postings (2023-2024)* by arshkon (~124k postings) | Public download (Kaggle account) | Historical baseline, all companies | **Approved with conditions**: confirm licence on the Kaggle page; use for aggregate analysis only (see 3.4) |

**Verification log (checked live on 4 Nov 2026):**

| Source | robots.txt result | Feed test | Open roles |
|---|---|---|---|
| Greenhouse | `Disallow: /embed/` only, so the `/v1/boards/` API is allowed | HTTP 200 | Anthropic 681, Databricks 921 |
| Ashby | No robots.txt served (HTTP 401). Under the Robots Exclusion Protocol (RFC 9309), an unavailable robots.txt means no restrictions | HTTP 200, 0 unlisted roles | OpenAI 818 (649 with a salary range) |
| Workday (NVIDIA) | `Allow: /NVIDIAExternalCareerSite/`. Disallowed paths (`/talentcommunity/`, `/NVIDIARecruitAds/`, `/refreshFacet/`, research site) are not used | HTTP 200 | NVIDIA 2,756 |

Why S1 and S2 are acceptable: these are the official feeds the job-board vendors provide so that employers' postings can be shown on other sites. They return only what the company has chosen to publish publicly, they need no login, and using them means I'm not scraping HTML pages.

### 2.2 Rejected sources

| Source | Reason |
|---|---|
| Google careers site (direct scraping) | Google's Terms of Service prohibit using automated means to access content in violation of machine-readable instructions such as robots.txt. No public jobs API. |
| Meta careers site (direct scraping) | Meta's Terms say you may not collect data from their products by automated means without prior permission. |
| Microsoft careers site (direct scraping) | No public jobs API, and I couldn't confirm that automated access is allowed, so I'm leaving it out by default. |
| LinkedIn / Indeed / Glassdoor (scraping) | Their terms forbid scraping. Pages also show personal data (recruiter profiles). |

Google, Meta and Microsoft can still appear in the analysis through the Kaggle historical dataset (S4), just not through live collection.

### 2.3 Conditional source: NVIDIA

NVIDIA uses Workday (`nvidia.wd5.myworkdayjobs.com`). Its robots.txt explicitly allows the career site, and the job-search endpoint isn't disallowed. The endpoint isn't documented for third-party use, though, and it can change without notice. Conditions:
- The job list returns titles, locations and relative dates ("Posted Today") but no descriptions. Each job page has to be requested separately (it gives the description and an exact `startDate`), so only **new** job IDs get fetched in each snapshot, with at least 1 second between requests.
- Any one search returns at most 2,000 results, so the list is collected one job family at a time (each family is under 2,000).
- If the endpoint changes, starts blocking requests, or the site terms turn out to forbid automated access, NVIDIA will be replaced with another AI company that uses Greenhouse, Lever or Ashby.

## 3. Legal & ethical requirements

### 3.1 Terms of Service and robots.txt
- Before collecting from any source, read its terms and check `robots.txt`. The collection script checks robots.txt automatically (Python `urllib.robotparser`) and refuses to fetch a disallowed path.
- Log the date and result of every check in `docs/collection_log.csv` (written automatically by the script).

### 3.2 Personal data (UK GDPR)
- Don't collect any personal data. Keep only job-level fields.
- Some job descriptions include recruiter names, emails or phone numbers. These are removed by regex **at collection time**, before anything is saved, and the results are checked by hand (Task 2 found and removed 12 recruiter names in Databricks postings).
- Never collect applicant data, application questions or anything behind a login.

### 3.3 Copyright
- Job descriptions are copyrighted text owned by the employer.
- Copies are made only for computational analysis in a non-commercial project (UK text and data mining exception, CDPA s29A).
- **The full raw descriptions don't go in a public repo.** Raw data stays in `data/raw/`, which is git-ignored. Only derived data (skills, counts, features) and a short sample get committed. If the mentor needs the raw data, the repo is made private and shared with them.

### 3.4 Kaggle dataset
- Use it under its stated Kaggle licence and credit it in the README.
- It was originally collected from LinkedIn, so it's only used for aggregate statistics and isn't redistributed.

### 3.5 Being a good API citizen
- One request per company per snapshot for OpenAI, Anthropic and Databricks (each feed returns all open roles in one response). NVIDIA needs about 140 list requests plus one request per **new** job, all spaced 1 second apart.
- Identify the client with a descriptive User-Agent: `CadetX-student-project`.
- Pause between requests, and stop on errors instead of retrying in a loop.

## 4. Plan for Task 2 (Data Collection)

**The main constraint:** the live feeds only show roles that are open *right now*. Closed roles disappear. A single scrape gives one snapshot, and you can't forecast from that.

**The fix:** collect repeated snapshots across the whole project, and build the time series from those.

| Step | What |
|---|---|
| 1 | Re-run the robots.txt checks automatically at the start of every snapshot (the first check was done on 4 Nov 2026) |
| 2 | Write `src/collect.py`: fetch each feed, map fields to the brief's required schema, save to `data/raw/{company}/{date}.json` |
| 3 | Run a snapshot **twice a week (Mon and Thu)** until the end of the project, which gives about 25 snapshots |
| 4 | Track each `job_id` across snapshots: first seen, last seen, open or closed. This gives `job_status` and hiring velocity |
| 5 | Download the Kaggle dataset (S4) as the historical baseline for trend and forecasting work |
| 6 | Write the Data Collection Report (sources, legal checks, fields, limitations) |

**Field mapping to the brief's required fields:**

| Required field | Ashby (OpenAI) | Greenhouse (Anthropic, Databricks) | Workday (NVIDIA) |
|---|---|---|---|
| job_id | `id` | `id` | `bulletFields[0]` (e.g. JR2025344) |
| company_name | set in script | `company_name` | set in script |
| job_title | `title` | `title` | `title` |
| job_description | `descriptionPlain` | `content` (HTML, unescaped and tags stripped) | `jobDescription` from per-job page |
| posting_date | `publishedAt` | `first_published` | `startDate` from per-job page |
| location | `location` | `location.name` | `locationsText` |
| job_url | `jobUrl` | `absolute_url` | `externalUrl` from per-job page |

Useful extra fields: OpenAI's `compensation` (salary_range), `department`, `employmentType` and `workplaceType`; Greenhouse's `departments` and `updated_at`; NVIDIA's job family and `timeType`.

Field names were confirmed against live responses on 4 Nov 2026.

**Known limitations, to be written up in the Task 2 report:**
- Survivorship bias: the live data only contains roles that are still open. The feeds' posting dates show when open roles were posted (some go back years), but roles that already closed aren't in the data.
- The Kaggle data stops in 2024 and doesn't line up exactly with the live data.
- Workday (NVIDIA) data may be harder to collect, or unavailable.

## 5. Corrections after the first live run (4 Nov 2026)

- NVIDIA has 2,756 open roles, not "2000+": Workday caps each search at 2,000 and then repeats page one, so collection is split by job family.
- NVIDIA's per-job page gives an exact `startDate`, so first-seen dates are no longer needed as its posting date.
- OpenAI: 649 of 818 roles have a salary range, not all of them.
- Kaggle is source S4 (it was mislabelled S3 in two places).

## Sources
- [Public job-posting APIs by ATS (Cavuno)](https://cavuno.com/blog/ats-platforms-public-job-posting-apis): endpoints for Greenhouse, Ashby, Lever and Workday, tested Oct 2026
- [Anthropic uses Greenhouse (ResumeGeni)](https://resumegeni.com/companies/anthropic/how-to-apply)
- [OpenAI uses Ashby (ResumeGeni)](https://resumegeni.com/companies/openai/how-to-apply)
- [Databricks uses Greenhouse (ResumeGeni)](https://resumegeni.com/companies/databricks/how-to-apply)
- [NVIDIA uses Workday (ResumeGeni)](https://resumegeni.com/companies/nvidia/how-to-apply)
- [Google ToS, automated access clause (ConductAtlas)](https://conductatlas.com/platform/google/google-terms-of-service/provision/CA-P-017332/prohibition-on-unauthorized-automated-content-access/)
- [Meta ToS, automated collection clause (ConductAtlas)](https://conductatlas.com/platform/meta/meta-terms-of-service/provision/CA-P-017687/no-automated-data-collection-without-permission/)
- [Kaggle LinkedIn Job Postings dataset](https://www.kaggle.com/datasets/arshkon/linkedin-job-postings)
