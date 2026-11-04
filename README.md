# Competitor Demand Prediction Using Job Postings

CadetX virtual work experience (NLP · Forecasting · Competitive Intelligence), individual track.
Author: Abdul-Haque Mohammed

Predicts competitor hiring demand, skill trends and market direction from public job postings.

| Role | Company | Source |
|---|---|---|
| Main specialist | OpenAI | Ashby public Job Posting API |
| Comparison | Anthropic | Greenhouse Job Board API |
| Comparison | Databricks | Greenhouse Job Board API |
| Comparison | NVIDIA | Workday public job search |

## Structure
- `docs/` task write-ups and legal checks
- `src/collect.py` takes one snapshot of all four job boards (checks robots.txt, removes personal data)
- `src/build_dataset.py` merges snapshots and tracks each job over time (first/last seen, open/closed)
- `src/preprocess.py` removes boilerplate, flags non-English postings, builds NLP-ready text and seniority levels
- `scripts/` twice-weekly snapshot schedule (macOS launchd)
- `notebooks/` analysis
- `data/raw/`, `data/interim/` raw snapshots and merged table (git-ignored: copyrighted job text, kept local; available to the mentor on request)
- `data/sample/` 20-row sample per company (descriptions cut to 300 characters) and snapshot counts
- `data/processed/` derived features
- `weekly_logs/` weekly progress notes

## Progress
| Task | Status |
|---|---|
| 1. Data Sources & Legal | Done ([docs](docs/TASK1_data_sources_and_legal.md)) |
| 2. Data Collection | Done ([report](docs/TASK2_data_collection_report.md)), snapshots ongoing Mon/Thu |
| 3. NLP Preprocessing | Done ([report](docs/TASK3_preprocessing.md), [notebook](notebooks/03_preprocessing.ipynb)) |
| 4. Skill Extraction | Next |
| 5-10 | Not started |

## Run
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/collect.py          # one snapshot (first NVIDIA run ~80 min, later runs only fetch new jobs)
python src/build_dataset.py    # merge snapshots, print data-quality checks
python src/preprocess.py       # clean text for NLP (Task 3)
```
