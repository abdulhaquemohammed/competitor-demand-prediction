"""
Task 4: skill extraction and feature engineering.

Reads  data/interim/jobs_clean.csv  (from preprocess.py)
Writes data/processed/ (no description text, so all committed):
  job_skills.csv          one row per posting: skills, categories, tech stack, role category
  skill_matrix.csv        one row per posting, one 0/1 column per skill (skill_frequency_vector)
  skill_frequency.csv     per company and skill: postings and share of postings
  category_share.csv      per company and category: share of postings needing it
  skill_trends_monthly.csv  per company, month and skill: share of that month's postings
  emerging_skills.csv     skills much more common in recent postings than older ones

Run:   python src/extract_skills.py
"""
import re
from pathlib import Path

import pandas as pd

from skill_taxonomy import NOT_TECH_STACK, ROLE_CATEGORIES, SELF_MENTIONS, TAXONOMY

ROOT = Path(__file__).resolve().parents[1]
INTERIM, OUT = ROOT / "data/interim", ROOT / "data/processed"

RECENT_DAYS = 90          # "recent" window for the emerging-skill flag
MIN_MONTH_POSTINGS = 20   # months with fewer postings are too noisy to trend


def compile_taxonomy():
    """skill -> (category, compiled regex). Empty pattern = the skill name as a whole word."""
    out = {}
    for category, skills in TAXONOMY.items():
        for skill, pattern in skills.items():
            pattern = pattern or r"\b" + re.escape(skill) + r"\b"
            out[skill] = (category, re.compile(pattern, re.I))
    return out


def extract(text, company, compiled):
    found = [s for s, (_, rx) in compiled.items() if rx.search(text)]
    return [s for s in found if s not in SELF_MENTIONS.get(company, set())]


def role_category(title):
    t = str(title).lower()
    for name, pattern in ROLE_CATEGORIES:
        if re.search(pattern, t):
            return name
    return "Other"


def main():
    df = pd.read_csv(INTERIM / "jobs_clean.csv")
    df = df[df["is_english"]].copy()            # French/Japanese text would give nonsense matches
    compiled = compile_taxonomy()
    cat_of = {s: c for s, (c, _) in compiled.items()}

    df["skill_list"] = [extract(t, c, compiled) for t, c in zip(df["cleaned_description"], df["company_name"])]
    df["category_list"] = df["skill_list"].map(lambda ss: sorted({cat_of[s] for s in ss}))
    df["tech_list"] = df["skill_list"].map(lambda ss: [s for s in ss if cat_of[s] not in NOT_TECH_STACK])
    df["role_category"] = df["job_title"].map(role_category)
    df["n_skills"] = df["skill_list"].str.len()
    df["posting_date"] = pd.to_datetime(df["posting_date"], utc=True)

    OUT.mkdir(parents=True, exist_ok=True)
    keep = ["company_name", "job_id", "job_title", "role_category", "seniority_level", "department",
            "location", "posting_date", "posting_month", "job_status", "duplicate_count", "n_skills"]
    jobs = df[keep].copy()
    jobs["extracted_skills"] = df["skill_list"].str.join("; ")
    jobs["skill_categories"] = df["category_list"].str.join("; ")
    jobs["tech_stack_tags"] = df["tech_list"].str.join("; ")
    jobs.to_csv(OUT / "job_skills.csv", index=False)

    # one-hot skill matrix: the "skill_frequency_vector" from the brief, input for Tasks 6 and 8
    skills = list(compiled)
    matrix = pd.DataFrame([[int(s in ss) for s in skills] for ss in df["skill_list"]],
                          columns=skills, index=df.index)
    pd.concat([df[["company_name", "job_id"]], matrix], axis=1).to_csv(OUT / "skill_matrix.csv", index=False)

    # skill share per company: % of that company's postings that ask for the skill
    long = df[["company_name", "job_id", "skill_list", "posting_date", "posting_month"]].explode("skill_list")
    long = long.dropna(subset=["skill_list"]).rename(columns={"skill_list": "skill"})
    totals = df.groupby("company_name").size()
    freq = long.groupby(["company_name", "skill"]).size().rename("postings").reset_index()
    freq["share"] = (freq["postings"] / freq["company_name"].map(totals)).round(4)
    freq["category"] = freq["skill"].map(cat_of)
    freq["rank"] = freq.groupby("company_name")["share"].rank(ascending=False, method="min").astype(int)
    freq.sort_values(["company_name", "rank"]).to_csv(OUT / "skill_frequency.csv", index=False)

    cats = df[["company_name", "category_list"]].explode("category_list").dropna()
    cat_share = (cats.groupby(["company_name", "category_list"]).size() / totals).unstack(0).fillna(0).round(4)
    cat_share.index.name = "category"
    cat_share.to_csv(OUT / "category_share.csv")

    # monthly trend: share of each month's postings asking for each skill
    month_tot = df.groupby(["company_name", "posting_month"]).size().rename("month_postings")
    trend = long.groupby(["company_name", "posting_month", "skill"]).size().rename("postings").reset_index()
    trend = trend.join(month_tot, on=["company_name", "posting_month"])
    trend = trend[trend["month_postings"] >= MIN_MONTH_POSTINGS]
    trend["share"] = (trend["postings"] / trend["month_postings"]).round(4)
    trend.to_csv(OUT / "skill_trends_monthly.csv", index=False)

    # emerging: share in postings from the last 90 days vs share in older postings
    cutoff = df["posting_date"].max() - pd.Timedelta(days=RECENT_DAYS)
    df["recent"] = df["posting_date"] >= cutoff
    rows = []
    for company, g in df.groupby("company_name"):
        new, old = g[g.recent], g[~g.recent]
        for s in skills:
            n_new = sum(s in ss for ss in new["skill_list"])
            n_old = sum(s in ss for ss in old["skill_list"])
            sh_new, sh_old = n_new / max(len(new), 1), n_old / max(len(old), 1)
            rows.append(dict(company_name=company, skill=s, category=cat_of[s],
                             recent_postings=n_new, recent_share=round(sh_new, 4),
                             older_postings=n_old, older_share=round(sh_old, 4),
                             growth_ratio=round(sh_new / sh_old, 2) if sh_old else None))
    em = pd.DataFrame(rows)
    em["emerging_skill_flag"] = (em["recent_postings"] >= 10) & (
        (em["growth_ratio"] >= 1.5) | (em["growth_ratio"].isna() & (em["recent_share"] >= 0.02)))
    em.sort_values(["company_name", "emerging_skill_flag", "recent_share"],
                   ascending=[True, False, False]).to_csv(OUT / "emerging_skills.csv", index=False)

    # summary for the note
    print(f"Postings analysed: {len(df)} (non-English excluded). Skills in taxonomy: {len(skills)}")
    print(df.groupby("company_name")["n_skills"].describe()[["mean", "50%"]].round(1).to_string())
    print("\nPostings with no skill found:", (df["n_skills"] == 0).groupby(df["company_name"]).sum().to_dict())
    print("\nTop 8 skills per company:")
    for c, g in freq.sort_values("rank").groupby("company_name"):
        print(f"  {c:10}", ", ".join(f"{r.skill} {r.share:.0%}" for r in g.head(8).itertuples()))
    print("\nRole categories:\n", pd.crosstab(df["company_name"], df["role_category"]).to_string())
    print("\nEmerging flags:", em.groupby("company_name")["emerging_skill_flag"].sum().to_dict())


if __name__ == "__main__":
    main()
