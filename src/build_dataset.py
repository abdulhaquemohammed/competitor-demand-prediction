"""
Task 2: combine every snapshot into one job-posting table and track each job over time.

Reads  data/raw/{company}/{date}.json  (all snapshots)
Writes data/interim/jobs_master.csv     (full text, git-ignored: copyrighted descriptions)
       data/sample/jobs_sample.csv      (20 rows per company, description cut to 300 chars, committed)
       data/sample/snapshot_summary.csv (counts per company per snapshot, committed)

Run:   python src/build_dataset.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, INTERIM, SAMPLE = ROOT / "data/raw", ROOT / "data/interim", ROOT / "data/sample"


def load_snapshots():
    frames = []
    for f in sorted(RAW.glob("*/*.json")):          # skips nvidia/details/*
        df = pd.DataFrame(json.loads(f.read_text()))
        df["snapshot_date"] = f.stem
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main():
    snaps = load_snapshots()
    snaps["posting_date"] = pd.to_datetime(snaps["posting_date"], utc=True, errors="coerce", format="ISO8601")
    latest = snaps.groupby("company_name")["snapshot_date"].max()

    # one row per (company, job): keep the most recent version of the posting
    snaps = snaps.sort_values("snapshot_date")
    seen = snaps.groupby(["company_name", "job_id"])["snapshot_date"].agg(
        first_seen="min", last_seen="max", snapshots_seen="nunique").reset_index()
    jobs = snaps.drop_duplicates(["company_name", "job_id"], keep="last").drop(columns="snapshot_date")
    jobs = jobs.merge(seen, on=["company_name", "job_id"])

    # status: still open if it appeared in that company's latest snapshot
    jobs["job_status"] = (jobs["last_seen"] == jobs["company_name"].map(latest)).map(
        {True: "active", False: "closed"})
    # if the feed gave no posting date, fall back to the first snapshot we saw it in
    jobs["posting_date_source"] = jobs["posting_date"].notna().map({True: "feed", False: "first_seen"})
    jobs["posting_date"] = jobs["posting_date"].fillna(pd.to_datetime(jobs["first_seen"], utc=True))
    jobs["posting_month"] = jobs["posting_date"].dt.strftime("%Y-%m")
    jobs["posting_week"] = jobs["posting_date"].dt.strftime("%G-W%V")
    # one consistent date format in the CSV so later tasks can parse it cleanly
    jobs["posting_date"] = jobs["posting_date"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    INTERIM.mkdir(parents=True, exist_ok=True)
    SAMPLE.mkdir(parents=True, exist_ok=True)
    jobs.to_csv(INTERIM / "jobs_master.csv", index=False)

    sample = jobs.groupby("company_name").head(20).copy()
    sample["job_description"] = sample["job_description"].str[:300] + "..."
    sample.to_csv(SAMPLE / "jobs_sample.csv", index=False)

    summary = snaps.groupby(["company_name", "snapshot_date"]).size().unstack(0).fillna(0).astype(int)
    summary.to_csv(SAMPLE / "snapshot_summary.csv")

    # quick data-quality printout for the Data Collection Report
    req = ["job_id", "company_name", "job_title", "job_description", "posting_date", "location", "job_url"]
    print("Rows:", len(jobs))
    print(jobs.groupby("company_name").agg(
        jobs=("job_id", "size"), active=("job_status", lambda s: (s == "active").sum()),
        earliest_post=("posting_date", "min"), with_salary=("salary_range", "count")).to_string())
    print("\nMissing required fields (%):")
    print((jobs[req].isna().mean() * 100).round(2).to_string())
    print("\nDuplicate (company, job_id):", jobs.duplicated(["company_name", "job_id"]).sum())


if __name__ == "__main__":
    main()
