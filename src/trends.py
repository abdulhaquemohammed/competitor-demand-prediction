"""
Task 5: hiring trend analysis.

Reads  data/interim/jobs_clean.csv   (from preprocess.py; dates already fixed by build_dataset.py)
       data/raw/{company}/{date}.json (job IDs only, to rebuild which jobs were open at each snapshot)
Writes data/processed/ (no description text, so all committed):
  weekly_postings.csv    company_name, week_start, new_postings_raw, new_roles_unique, new_roles_adjusted,
                         rolling_4w, wow_change_pct, spike_flag     (last 26 complete weeks)
  monthly_postings.csv   the same per complete calendar month (month_start, rolling_3m, mom_change_pct)
  snapshot_flows.csv     per company and snapshot interval: open, opened, closed, net, per week
  velocity_summary.csv   per company: last 4 vs previous 4 weeks, snapshot flows, velocity bucket
  role_velocity.csv      company x role_category: last 8 vs previous 8 weeks, growth, bucket
  posting_weekday.csv    share of postings by weekday per company

Shared time-series structure (read by Task 7): company_name + week_start / month_start + metrics.

Two views, with opposite weaknesses:
  posting-date series  long (months) but biased: feeds only list roles that are still open, so older
                       weeks lose postings that already closed. The adjusted column divides by a
                       survival curve S(age) estimated from the snapshots (factor capped at 3).
  snapshot flows       unbiased (we watch jobs open and close) but short (since 4 Nov 2026).
Headline unit is the unique role: identical descriptions within a company and week (one role posted
per city) count once. Postings flagged bulk_repost (build_dataset.py) are left out of new-posting
counts. The current incomplete week and month are dropped.

Run:   python src/trends.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from extract_skills import role_category

ROOT = Path(__file__).resolve().parents[1]
INTERIM, RAW, OUT = ROOT / "data/interim", ROOT / "data/raw", ROOT / "data/processed"

WINDOW_WEEKS = 26          # posting-date trend window (complete weeks)
SURVIVAL_CAP = 3.0         # largest survivorship correction factor
AGE_BANDS = [0, 7, 14, 30, 60, 90, 180, np.inf]    # posting age in days at the baseline snapshot
MIN_BAND_JOBS = 30         # bands with fewer open jobs use the company-wide closure rate
SPIKE_LOOKBACK = 8         # weeks of history behind each spike test
SPIKE_MIN_HISTORY = 4
SPIKE_K = 3.0              # flag if outside median +/- K x MAD of the previous weeks
SPIKE_MAD_FLOOR = 3.0      # avoids flagging every wobble when a company is very steady (adjusted roles)
ROLE_WEEKS = 8             # role velocity compares the last 8 weeks with the 8 before
ROLE_MIN_ROLES = 10        # minimum unique roles across both windows to get a bucket
BUCKET_LOW, BUCKET_HIGH = 5.0, 7.0   # new unique roles per week as % of open roles (last 4 weeks)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ---------------------------------------------------------------- load

def snapshot_ids():
    """company -> {snapshot_date: set(job_id)} from the raw files (IDs only)."""
    out = {}
    for f in sorted(RAW.glob("*/*.json")):
        ids = {str(j["job_id"]) for j in json.loads(f.read_text())}
        out.setdefault(f.parent.name, {})[f.stem] = ids
    return out


def load_jobs():
    df = pd.read_csv(INTERIM / "jobs_clean.csv", usecols=[
        "company_name", "job_id", "job_title", "posting_date", "posting_date_source",
        "description_hash", "job_status"], dtype={"job_id": str})
    df["posting_date"] = pd.to_datetime(df["posting_date"], utc=True).dt.tz_localize(None).dt.normalize()
    df["role_category"] = df["job_title"].map(role_category)
    df["description_hash"] = df["description_hash"].fillna(df["job_id"])
    df["week_start"] = df["posting_date"] - pd.to_timedelta(df["posting_date"].dt.day_of_week, unit="D")
    df["month_start"] = df["posting_date"].dt.to_period("M").dt.to_timestamp()
    return df


# ---------------------------------------------------------------- survivorship correction

def survival_curves(jobs, snaps):
    """Per company: piecewise-constant weekly closure rate by posting-age band, from jobs open at the
    first snapshot that had closed by the latest one. Returns {company: function(age_days) -> S}."""
    curves, info = {}, []
    for company, by_date in snaps.items():
        dates = sorted(by_date)
        base, last = dates[0], dates[-1]
        weeks = (pd.Timestamp(last) - pd.Timestamp(base)).days / 7
        g = jobs[(jobs.company_name.str.lower() == company) & jobs.job_id.isin(by_date[base])
                 & (jobs.posting_date_source != "bulk_repost")].copy()
        g["age"] = (pd.Timestamp(base) - g.posting_date).dt.days.clip(lower=0)
        g["closed"] = ~g.job_id.isin(by_date[last])
        g["band"] = pd.cut(g.age, AGE_BANDS, right=False, labels=False)
        overall = g.closed.sum() / (len(g) * weeks)
        rates = []
        for b in range(len(AGE_BANDS) - 1):
            gb = g[g.band == b]
            rate = gb.closed.sum() / (len(gb) * weeks) if len(gb) >= MIN_BAND_JOBS else overall
            rates.append(rate)
            info.append(dict(company_name=company, band=f"{AGE_BANDS[b]}-{AGE_BANDS[b + 1]}d",
                             open_at_baseline=len(gb), closed_by_latest=int(gb.closed.sum()),
                             weekly_closure_rate=round(rate, 4)))
        curves[company] = rates
    return curves, pd.DataFrame(info)


def survival(rates, age_days):
    """S(age) = exp(-cumulative hazard) for weekly closure rates per age band."""
    age = np.asarray(age_days, float)
    cum = np.zeros_like(age)
    for b, rate in enumerate(rates):
        lo, hi = AGE_BANDS[b], AGE_BANDS[b + 1]
        cum += rate * (np.clip(age, lo, hi) - lo) / 7
    return np.exp(-cum)


# ---------------------------------------------------------------- weekly / monthly

def spike_flags(values):
    """'spike' / 'decline' if a week is outside median +/- K x MAD of the previous weeks."""
    flags = []
    for i in range(len(values)):
        hist = values[max(0, i - SPIKE_LOOKBACK):i]
        if len(hist) < SPIKE_MIN_HISTORY:
            flags.append(""); continue
        med = np.median(hist)
        mad = max(np.median(np.abs(hist - med)), SPIKE_MAD_FLOOR)
        flags.append("spike" if values[i] > med + SPIKE_K * mad else
                     "decline" if values[i] < med - SPIKE_K * mad else "")
    return flags


def series(posts, key, periods, roll, spikes):
    """One row per company and period (zero-filled so every company has the same range)."""
    rows = []
    for company, g in posts.groupby("company_name"):
        grp = g.groupby(key)
        raw = grp.size().reindex(periods, fill_value=0)
        uniq = grp["description_hash"].nunique().reindex(periods, fill_value=0)
        # unique roles weighted by the correction factor (mean factor within each identical-role group)
        per_role = g.groupby([key, "description_hash"])["factor"].mean().groupby(key).sum()
        adj = per_role.reindex(periods, fill_value=0.0)
        d = pd.DataFrame({"company_name": company, key: periods, "new_postings_raw": raw.values,
                          "new_roles_unique": uniq.values, "new_roles_adjusted": adj.round(1).values})
        d[roll[0]] = d["new_roles_unique"].rolling(roll[1], min_periods=roll[1]).mean().round(2)
        d[roll[2]] = (d["new_roles_unique"].pct_change().replace([np.inf, -np.inf], np.nan) * 100).round(1)
        d["spike_flag"] = spike_flags(d["new_roles_adjusted"].values.astype(float)) if spikes else ""
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------- snapshot flows

def flows(snaps, display):
    rows = []
    for company, by_date in snaps.items():
        dates = sorted(by_date)
        for i, d in enumerate(dates):
            row = dict(company_name=display[company], interval_start="", snapshot_date=d, days="",
                       open_postings=len(by_date[d]), opened="", closed="", net_change="",
                       opened_per_week="", closed_per_week="", is_baseline=(i == 0))
            if i:
                prev = by_date[dates[i - 1]]
                days = (pd.Timestamp(d) - pd.Timestamp(dates[i - 1])).days
                opened, closed = len(by_date[d] - prev), len(prev - by_date[d])
                row.update(interval_start=dates[i - 1], days=days, opened=opened, closed=closed,
                           net_change=opened - closed, opened_per_week=round(opened / days * 7, 1),
                           closed_per_week=round(closed / days * 7, 1))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["company_name", "snapshot_date"])


# ---------------------------------------------------------------- summaries

def growth(new, old):
    return round((new / old - 1) * 100, 1) if old else np.nan


def summary(weekly, fl):
    rows = []
    for company, w in weekly.groupby("company_name"):
        w = w.sort_values("week_start")
        last, prev = w.tail(4), w.iloc[-8:-4]
        f = fl[(fl.company_name == company)].sort_values("snapshot_date")
        iv = f[~f.is_baseline.astype(bool)]
        days = iv["days"].astype(float).sum()
        opened, closed = iv["opened"].astype(float).sum(), iv["closed"].astype(float).sum()
        new_per_week = last.new_roles_unique.mean()
        rate = new_per_week / f.open_postings.iloc[-1] * 100
        rows.append(dict(
            company_name=company,
            new_roles_per_week_last4=round(new_per_week, 1),
            new_roles_per_week_prev4=round(prev.new_roles_unique.mean(), 1),
            growth_pct=growth(last.new_roles_unique.sum(), prev.new_roles_unique.sum()),
            growth_pct_adjusted=growth(last.new_roles_adjusted.sum(), prev.new_roles_adjusted.sum()),
            snapshot_span=f"{f.snapshot_date.iloc[0]} to {f.snapshot_date.iloc[-1]}",
            snapshot_days=int(days),
            opened_per_week=round(opened / days * 7, 1), closed_per_week=round(closed / days * 7, 1),
            open_stock_baseline=int(f.open_postings.iloc[0]), open_stock_latest=int(f.open_postings.iloc[-1]),
            open_stock_change_pct=round((f.open_postings.iloc[-1] / f.open_postings.iloc[0] - 1) * 100, 1),
            new_role_rate_pct_of_open=round(rate, 2),
            hiring_velocity_bucket="low" if rate < BUCKET_LOW else "high" if rate >= BUCKET_HIGH else "medium"))
    return pd.DataFrame(rows)


def role_velocity(posts, weeks, as_adjusted_by):
    """company x role_category: unique new roles per week, last 8 weeks vs the 8 before."""
    recent, older = weeks[-ROLE_WEEKS:], weeks[-2 * ROLE_WEEKS:-ROLE_WEEKS]
    rows = []
    for (company, cat), g in posts[posts.week_start.isin(weeks[-2 * ROLE_WEEKS:])].groupby(
            ["company_name", "role_category"]):
        u = g.drop_duplicates(["week_start", "description_hash"])
        adj = g.groupby(["week_start", "description_hash"])["factor"].mean().reset_index()
        n_new, n_old = u.week_start.isin(recent).sum(), u.week_start.isin(older).sum()
        a_new = adj[adj.week_start.isin(recent)].factor.sum()
        a_old = adj[adj.week_start.isin(older)].factor.sum()
        rows.append(dict(company_name=company, role_category=cat,
                         new_roles_per_week_last8=round(n_new / ROLE_WEEKS, 2),
                         new_roles_per_week_prev8=round(n_old / ROLE_WEEKS, 2),
                         growth_pct=growth(n_new, n_old), growth_pct_adjusted=growth(a_new, a_old),
                         roles_in_window=int(n_new + n_old)))
    rv = pd.DataFrame(rows)
    ok = (rv.roles_in_window >= ROLE_MIN_ROLES) & rv.growth_pct_adjusted.notna()
    rv["hiring_velocity_bucket"] = "insufficient data"
    rv.loc[ok, "hiring_velocity_bucket"] = pd.qcut(
        rv.loc[ok, "growth_pct_adjusted"].rank(method="first"), 3, labels=["low", "medium", "high"]).astype(str)
    return rv.sort_values(["company_name", "role_category"])


def weekday_table(posts):
    """Share of postings by weekday, only postings with a real feed date."""
    p = posts[posts.posting_date_source == "feed"]
    t = p.groupby(["company_name", p.posting_date.dt.day_of_week]).size().rename("postings").reset_index()
    t["weekday"] = t["posting_date"].map(dict(enumerate(WEEKDAYS)))
    t["share"] = (t.postings / t.groupby("company_name").postings.transform("sum")).round(4)
    return t[["company_name", "weekday", "postings", "share"]].assign(
        _o=t["posting_date"]).sort_values(["company_name", "_o"]).drop(columns="_o")


# ---------------------------------------------------------------- main

def main():
    jobs, snaps = load_jobs(), snapshot_ids()
    display = {c.lower(): c for c in jobs.company_name.unique()}
    as_of = pd.Timestamp(max(max(d) for d in snaps.values()))

    # last complete week/month: a week is complete once its Sunday is before the latest snapshot date
    this_week = as_of - pd.Timedelta(days=as_of.weekday())
    last_week = this_week - pd.Timedelta(days=7)
    weeks = pd.date_range(end=last_week, periods=WINDOW_WEEKS, freq="7D")
    first_month = (weeks[0] + pd.offsets.MonthBegin(0)).normalize()
    last_month = as_of.to_period("M").to_timestamp() - pd.offsets.MonthBegin(1)
    months = pd.date_range(first_month, last_month, freq="MS")

    curves, band_info = survival_curves(jobs, snaps)
    jobs["age_days"] = (as_of - jobs.posting_date).dt.days.clip(lower=0)
    jobs["factor"] = 1.0
    for company, rates in curves.items():
        m = jobs.company_name.str.lower() == company
        s = survival(rates, jobs.loc[m, "age_days"])
        jobs.loc[m, "factor"] = np.minimum(1 / s, SURVIVAL_CAP)

    posts = jobs[jobs.posting_date_source != "bulk_repost"]       # new-posting counts leave bulk rows out
    in_weeks = posts[posts.week_start.isin(weeks)]
    weekly = series(in_weeks, "week_start", weeks, ("rolling_4w", 4, "wow_change_pct"), True)
    in_months = posts[posts.month_start.isin(months)]
    monthly = series(in_months, "month_start", months, ("rolling_3m", 3, "mom_change_pct"), False)

    fl = flows(snaps, display)
    summ = summary(weekly, fl)
    rv = role_velocity(in_weeks, list(weeks), None)
    wd = weekday_table(in_weeks)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in [("weekly_postings", weekly), ("monthly_postings", monthly), ("snapshot_flows", fl),
                     ("velocity_summary", summ), ("role_velocity", rv), ("posting_weekday", wd)]:
        for c in ("week_start", "month_start"):
            if c in df:
                df[c] = df[c].dt.strftime("%Y-%m-%d")
        df.to_csv(OUT / f"{name}.csv", index=False)

    # ---- report and sanity checks
    print(f"As of {as_of.date()}; weeks {weeks[0].date()} to {weeks[-1].date()} ({len(weeks)}); "
          f"months {months[0].date()} to {months[-1].date()}")
    print("\nClosure rate by age band (per week):\n", band_info.to_string(index=False))
    print("\nVelocity summary:\n", summ.to_string(index=False))
    print("\nSnapshot flows:\n", fl.to_string(index=False))
    checks(jobs, posts, in_weeks, in_months, weekly, monthly, as_of, weeks)


def checks(jobs, posts, in_weeks, in_months, weekly, monthly, as_of, weeks):
    print("\nSanity checks")
    ok = True
    def report(name, passed, detail=""):
        nonlocal ok
        ok &= bool(passed)
        print(f"  [{'ok' if passed else 'FAIL'}] {name} {detail}")
    w = weekly.groupby("company_name").new_postings_raw.sum()
    n = in_weeks.groupby("company_name").size()
    report("weekly raw sums equal postings in window", (w == n.reindex(w.index)).all(), str(w.to_dict()))
    m = monthly.groupby("company_name").new_postings_raw.sum()
    report("monthly raw sums equal postings in months", (m == in_months.groupby("company_name").size().reindex(m.index)).all())
    report("adjusted >= unique", (weekly.new_roles_adjusted + 0.05 >= weekly.new_roles_unique).all())
    report("unique <= raw", (weekly.new_roles_unique <= weekly.new_postings_raw).all())
    late = jobs[jobs.posting_date > as_of]
    report("no posting dates after the latest snapshot", late.empty, f"({len(late)} found)" if len(late) else "")
    report("same weeks for every company", weekly.groupby("company_name").week_start.apply(tuple).nunique() == 1)
    report("no incomplete week", pd.Timestamp(weekly.week_start.max()) + pd.Timedelta(days=6) < as_of)
    bulk = jobs[jobs.posting_date_source == "bulk_repost"]
    report("bulk-repost rows excluded from new-posting counts", not posts.posting_date_source.eq("bulk_repost").any(),
           f"({len(bulk)} rows left out)")
    if not ok:
        raise SystemExit("sanity check failed")


if __name__ == "__main__":
    main()
