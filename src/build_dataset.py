"""
Task 2: combine every snapshot into one job-posting table and track each job over time.

Reads  data/raw/{company}/{date}.json  (all snapshots)
Writes data/interim/jobs_master.csv     (full text, git-ignored: copyrighted descriptions)
       data/sample/jobs_sample.csv      (20 rows per company, description cut to 300 chars, committed)
       data/sample/snapshot_summary.csv (counts per company per snapshot, committed)
       docs/posting_date_fix.csv        (bulk-repost check per company, committed)

Bulk reposts: a day with at least 50 postings and 10x the company's median daily count is a
bulk repost (Workday resets startDate when roles are reposted). The real date is estimated
from the requisition number (it rises over time) if that estimate is accurate enough on
held-out normal postings (MAE <= 30 days). Otherwise the dates are kept and the rows are
flagged posting_date_source = "bulk_repost", so trend work can leave them out of new-posting
counts while still counting them as open roles. The original date is kept in posting_date_raw.

Run:   python src/build_dataset.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, INTERIM, SAMPLE = ROOT / "data/raw", ROOT / "data/interim", ROOT / "data/sample"
DOCS = ROOT / "docs"

BULK_MIN_POSTINGS = 50     # a bulk-repost day has at least this many postings
BULK_MIN_RATIO = 10        # ... and at least this multiple of the company's median daily count
ROLL_WINDOW = 101          # postings in the rolling median of date sorted by requisition number
MAX_MAE_DAYS = 30          # impute only if held-out error is at most this
CV_FOLDS = 5


def load_snapshots():
    frames = []
    for f in sorted(RAW.glob("*/*.json")):          # skips nvidia/details/*
        df = pd.DataFrame(json.loads(f.read_text()))
        df["snapshot_date"] = f.stem
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def req_number(job_ids):
    """Numeric part of IDs like JR2025344 or 4012345; NaN for UUIDs (no time order)."""
    return job_ids.astype(str).str.extract(r"^[A-Za-z]*(\d+)$")[0].astype(float)


def fit_req_dates(req, days):
    """Monotonic req number -> date (days): rolling median of dates sorted by req, then cummax."""
    order = np.argsort(req.values)
    r, d = req.values[order], days.values[order]
    smooth = pd.Series(d).rolling(ROLL_WINDOW, center=True, min_periods=1).median().cummax().values
    return lambda x: np.interp(x, r, smooth)


def cv_mae(req, days):
    """Mean absolute error (days) of the req-number mapping on held-out normal postings."""
    fold = np.random.default_rng(42).integers(0, CV_FOLDS, len(req))
    errs = []
    for k in range(CV_FOLDS):
        test = fold == k
        predict = fit_req_dates(req[~test], days[~test])
        errs.append(np.abs(predict(req[test]) - days[test].values))
    return float(np.concatenate(errs).mean())


def fix_bulk_reposts(jobs):
    """Detect bulk-repost days per company and impute or flag those postings (see docstring)."""
    jobs["posting_date_raw"] = jobs["posting_date"]
    report = []
    for company, g in jobs[jobs["posting_date_source"] == "feed"].groupby("company_name"):
        day = g["posting_date"].dt.normalize()
        daily = day.value_counts()
        median = daily.median()
        bulk_days = daily[(daily >= BULK_MIN_POSTINGS) & (daily >= BULK_MIN_RATIO * median)]
        row = dict(company_name=company, postings=len(g), median_daily=median,
                   bulk_days="; ".join(d.strftime("%Y-%m-%d") for d in bulk_days.index),
                   bulk_postings=int(bulk_days.sum()), mae_days=None, route="none")
        if len(bulk_days):
            bulk = day.isin(bulk_days.index)
            req = req_number(g["job_id"])
            normal = ~bulk & req.notna()
            days = (day - pd.Timestamp("2000-01-01", tz="UTC")).dt.days.astype(float)
            if normal.sum() >= 5 * ROLL_WINDOW and req[bulk].notna().all():
                row["mae_days"] = round(cv_mae(req[normal], days[normal]), 1)
            idx = g.index[bulk]
            if row["mae_days"] is not None and row["mae_days"] <= MAX_MAE_DAYS:
                est = fit_req_dates(req[normal], days[normal])(req[bulk])
                jobs.loc[idx, "posting_date"] = (pd.Timestamp("2000-01-01", tz="UTC")
                                                 + pd.to_timedelta(np.round(est), unit="D"))
                jobs.loc[idx, "posting_date_source"] = "req_id_imputed"
                row["route"] = "req_id_imputed"
            else:
                jobs.loc[idx, "posting_date_source"] = "bulk_repost"
                row["route"] = "bulk_repost (kept dates, excluded from new-posting velocity)"
        report.append(row)
    report = pd.DataFrame(report)
    DOCS.mkdir(exist_ok=True)
    report.to_csv(DOCS / "posting_date_fix.csv", index=False)
    print("Bulk-repost check:\n" + report.to_string(index=False) + "\n")
    return jobs


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
    jobs = fix_bulk_reposts(jobs)
    jobs["posting_month"] = jobs["posting_date"].dt.strftime("%Y-%m")
    jobs["posting_week"] = jobs["posting_date"].dt.strftime("%G-W%V")
    # one consistent date format in the CSV so later tasks can parse it cleanly
    for col in ["posting_date", "posting_date_raw"]:
        jobs[col] = jobs[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

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
