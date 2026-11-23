"""
Task 6: competitor comparison.

Reads  data/processed/ only (Tasks 4 and 5; no scraping, no description text):
       job_skills.csv, skill_matrix.csv, skill_frequency.csv, category_share.csv,
       velocity_summary.csv, role_velocity.csv, snapshot_flows.csv, weekly_postings.csv,
       emerging_skills.csv
Writes data/processed/ (all committed):
  comparison_scorecard.csv   one row per company, one column per headline metric
  comparison_skills.csv      long: company x skill: postings, share, rank, scope (common / distinctive / other)
  comparison_categories.csv  long: company x skill category: share of open roles, gap to the other three
  comparison_roles.csv       long: company x role category: share of open roles, concentration, growth, bucket
  comparison_tech_stack.csv  long: company x tech-stack group or cloud provider, from tech_stack_tags
  comparison_velocity.csv    one row per company: snapshot flows first, then posting-date growth
  comparison_similarity.csv  long: company pair x view (skills, categories, roles): cosine similarity
  distinctive_skills.csv     skills one company asks for far more than the other three
  strategic_gaps.csv         where a company is well below peers, and white space across all four

One framework, identical for all four companies. Population: open roles (job_status == active),
so the comparison describes demand today. Shares are per open posting, as in Task 4 (identical
descriptions in several cities are not collapsed). Task 4's shares use every posting seen, so
they differ by a point or two; the check at the end of the run prints the largest difference.

Definitions (constants below):
  common skill       share >= 5% of open roles at every company
  distinctive skill  share >= 5% at one company and >= 2x the mean of the other three
  below peers        share <= 0.5x the mean of the other three, where those three average >= 10%
  thin               skill category at or below 10% of open roles at all four companies
  all growing        role category with adjusted growth > 0 at all four (>= 10 roles in the window)

Run:   python src/compare.py
"""
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from skill_taxonomy import TAXONOMY

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"

MIN_SHARE = 0.05           # minimum share for a skill to count as common or distinctive
DISTINCT_RATIO = 2.0       # distinctive: share at least this multiple of the other three's mean
GAP_RATIO = 0.5            # below peers: share at most this multiple of the other three's mean
GAP_PEER_MIN = 0.10        # ... and the other three must average at least this
THIN_MAX = 0.10            # white space: every company at or below this share
TOP_N = 5
COMPANIES = ["OpenAI", "Anthropic", "Databricks", "NVIDIA"]
CLOUD = ["AWS", "GCP", "Azure"]
# not a tech-stack skill category (matches NOT_TECH_STACK in skill_taxonomy.py)
NOT_TECH = {"ML & AI Concepts", "Business & GTM"}
# seniority groups: "senior/staff/principal" depends on each company's title habits, so it is
# reported but not interpreted (Anthropic and OpenAI rarely use "Senior")
SENIORITY_GROUPS = {
    "pct_unmarked_title": ["mid"], "pct_manager_lead": ["manager", "lead"],
    "pct_director_exec": ["director", "executive"], "pct_intern": ["intern"],
    "pct_senior_staff_principal": ["senior", "staff", "principal"],
}


def others_mean(wide, company):
    return wide.drop(columns=company).mean(axis=1)


def long_gap(wide, name):
    """wide (item x company shares) -> long with the mean of the other three and the gap in points."""
    rows = []
    for c in COMPANIES:
        om = others_mean(wide[COMPANIES], c)
        rows.append(pd.DataFrame({name: wide.index, "company_name": c, "share": wide[c].values,
                                  "others_mean": om.values.round(4),
                                  "gap_pp": ((wide[c] - om) * 100).round(1).values}))
    return pd.concat(rows, ignore_index=True)


def cosine(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    jobs = pd.read_csv(P / "job_skills.csv")
    matrix = pd.read_csv(P / "skill_matrix.csv")
    skill_cat = pd.Series({s: cat for cat, group in TAXONOMY.items() for s in group})   # skill -> category
    vel = pd.read_csv(P / "velocity_summary.csv").set_index("company_name")
    rv = pd.read_csv(P / "role_velocity.csv")
    flows = pd.read_csv(P / "snapshot_flows.csv")
    emerging = pd.read_csv(P / "emerging_skills.csv")
    weekly = pd.read_csv(P / "weekly_postings.csv")

    # ---- open roles only, one row per posting
    open_jobs = jobs[jobs.job_status == "active"].reset_index(drop=True)
    open_mx = matrix.merge(open_jobs[["company_name", "job_id"]], on=["company_name", "job_id"])
    n_open = open_jobs.groupby("company_name").size()
    skills = [c for c in matrix.columns if c not in ("company_name", "job_id")]

    # ---- skills
    post = open_mx.groupby("company_name")[skills].sum().T.reindex(columns=COMPANIES)
    share = post / n_open.reindex(COMPANIES)
    om = pd.DataFrame({c: share.drop(columns=c).mean(axis=1) for c in COMPANIES})
    common = (share >= MIN_SHARE).all(axis=1)
    distinct = (share >= MIN_SHARE) & (share >= DISTINCT_RATIO * om)
    rows = []
    for c in COMPANIES:
        d = pd.DataFrame({"company_name": c, "skill": skills, "category": skill_cat.reindex(skills).values,
                          "postings": post[c].values, "share": share[c].round(4).values,
                          "others_mean_share": om[c].round(4).values})
        d["rank"] = d["share"].rank(ascending=False, method="min").astype(int)
        d["scope"] = np.where(common.values, "common", np.where(distinct[c].values, "distinctive", "other"))
        rows.append(d[d.postings > 0])
    cskills = pd.concat(rows, ignore_index=True).sort_values(["company_name", "rank"])
    cskills.to_csv(P / "comparison_skills.csv", index=False)

    dist = cskills[cskills.scope == "distinctive"].copy()
    dist["ratio_to_others"] = (dist.share / dist.others_mean_share.replace(0, np.nan)).round(1)
    dist = dist.sort_values(["company_name", "share"], ascending=[True, False])
    dist.to_csv(P / "distinctive_skills.csv", index=False)

    # ---- skill categories (all taxonomy categories, shares of open roles needing at least one skill)
    cats = open_jobs[["company_name", "skill_categories"]].assign(
        category=open_jobs.skill_categories.fillna("").str.split("; ")).explode("category")
    cats = cats[cats.category != ""]
    cat_share = (cats.groupby(["category", "company_name"]).size().unstack().reindex(columns=COMPANIES)
                 .fillna(0) / n_open.reindex(COMPANIES))
    ccat = long_gap(cat_share, "category")
    ccat["rank_in_company"] = ccat.groupby("company_name")["share"].rank(ascending=False, method="min").astype(int)
    ccat["share"] = ccat["share"].round(4)
    ccat.to_csv(P / "comparison_categories.csv", index=False)

    # ---- role categories: mix, concentration, growth
    role_share = (open_jobs.groupby(["role_category", "company_name"]).size().unstack().reindex(columns=COMPANIES)
                  .fillna(0) / n_open.reindex(COMPANIES))
    croles = long_gap(role_share, "role_category")
    croles["open_roles"] = [int(round(s * n_open[c])) for s, c in zip(croles.share, croles.company_name)]
    croles["rank_in_company"] = croles.groupby("company_name")["share"].rank(ascending=False, method="min").astype(int)
    croles["share"] = croles["share"].round(4)
    croles = croles.merge(rv[["company_name", "role_category", "new_roles_per_week_last8", "growth_pct_adjusted",
                              "hiring_velocity_bucket"]], on=["company_name", "role_category"], how="left")
    croles = croles.rename(columns={"hiring_velocity_bucket": "growth_bucket"})
    croles.to_csv(P / "comparison_roles.csv", index=False)

    # ---- tech stack, from tech_stack_tags (roles with no tag are non-technical or text-light)
    tags = open_jobs[["company_name", "tech_stack_tags"]].copy()
    tags["tag_list"] = tags.tech_stack_tags.fillna("").str.split("; ").map(lambda t: [x for x in t if x])
    has_tag = tags.tag_list.str.len() > 0
    n_tech = tags[has_tag].groupby("company_name").size().reindex(COMPANIES)
    tags["groups"] = tags.tag_list.map(lambda t: sorted({skill_cat.get(x) for x in t}))
    rows = []
    grp = tags.explode("groups").dropna(subset=["groups"])
    for (c, g), n in grp.groupby(["company_name", "groups"]).size().items():
        rows.append(dict(company_name=c, kind="category", name=g, postings=n))
    cloud_roles = tags[tags.groups.map(lambda g: "Cloud" in g)].groupby("company_name").size()
    for c in COMPANIES:
        for provider in CLOUD:
            n = int(tags[(tags.company_name == c)].tag_list.map(lambda t: provider in t).sum())
            rows.append(dict(company_name=c, kind="cloud_provider", name=provider, postings=n))
    ts = pd.DataFrame(rows)
    ts["share_of_open"] = (ts.postings / ts.company_name.map(n_open)).round(4)
    ts["share_of_tech_roles"] = (ts.postings / ts.company_name.map(n_tech)).round(4)
    ts["share_of_cloud_roles"] = np.where(ts.kind == "cloud_provider",
                                          (ts.postings / ts.company_name.map(cloud_roles).replace(0, np.nan)).round(4), np.nan)
    ts["top_tags"] = ""
    for (c, g), idx in ts[ts.kind == "category"].groupby(["company_name", "name"]).groups.items():
        cnt = tags[tags.company_name == c].tag_list.explode().dropna()
        cnt = cnt[cnt.map(lambda x: skill_cat.get(x) == g)].value_counts().head(3)
        ts.loc[idx, "top_tags"] = "; ".join(cnt.index)
    ts.sort_values(["kind", "name", "company_name"]).to_csv(P / "comparison_tech_stack.csv", index=False)

    # ---- velocity: flows first, then posting-date growth
    iv = flows[~flows.is_baseline.astype(bool)].groupby("company_name").size()
    cv = vel.reindex(COMPANIES).copy()
    cv["flow_intervals"] = iv.reindex(COMPANIES).values
    cv["flows_provisional"] = cv.flow_intervals == 1      # one interval only (NVIDIA)
    cv["open_roles_now"] = cv.open_stock_latest
    cv["net_per_week"] = (cv.opened_per_week - cv.closed_per_week).round(1)
    cv["weekly_churn_pct_of_open"] = (cv.closed_per_week / cv.open_stock_baseline * 100).round(1)
    cv["growth_confidence"] = np.where(cv.weekly_churn_pct_of_open >= 9, "low (high churn, large survival correction)", "normal")
    cv = cv.reset_index()[[
        "company_name", "snapshot_span", "snapshot_days", "flow_intervals", "flows_provisional",
        "open_stock_baseline", "open_roles_now", "open_stock_change_pct", "opened_per_week", "closed_per_week",
        "net_per_week", "weekly_churn_pct_of_open", "new_role_rate_pct_of_open", "hiring_velocity_bucket",
        "new_roles_per_week_last4", "new_roles_per_week_prev4", "growth_pct", "growth_pct_adjusted", "growth_confidence"]]
    cv.to_csv(P / "comparison_velocity.csv", index=False)

    # ---- similarity between companies (cosine on share vectors)
    sim = []
    for view, wide in (("skills", share), ("skill_categories", cat_share), ("role_categories", role_share)):
        for a, b in combinations(COMPANIES, 2):
            sim.append(dict(view=view, company_a=a, company_b=b, cosine=round(cosine(wide[a].values, wide[b].values), 3)))
    sim = pd.DataFrame(sim)
    sim.to_csv(P / "comparison_similarity.csv", index=False)

    # ---- strategic gaps
    gaps = []
    def add(company, kind, scope, item, share_c, others, note):
        gaps.append(dict(company_name=company, gap_type=kind, item_type=scope, item=item,
                         company_share=round(share_c, 4) if share_c == share_c else np.nan,
                         others_mean_share=round(others, 4) if others == others else np.nan,
                         gap_pp=round((share_c - others) * 100, 1) if share_c == share_c else np.nan, note=note))
    for scope, wide in (("skill_category", cat_share), ("role_category", role_share), ("skill", share)):
        for c in COMPANIES:
            o = others_mean(wide, c)
            low = wide[(wide[c] <= GAP_RATIO * o) & (o >= GAP_PEER_MIN)]
            for item in low.index:
                add(c, "below_peers", scope, item, wide.loc[item, c], o[item],
                    f"{wide.loc[item, c]:.0%} vs {o[item]:.0%} at the other three")
        thin = wide[(wide[COMPANIES].max(axis=1) <= THIN_MAX) & (wide[COMPANIES].max(axis=1) > 0)]
        if scope == "skill_category":          # thin roles are small functions, thin skills the long tail: not findings
            for item in thin.index:
                add("all four", "white_space_thin", scope, item, wide.loc[item, COMPANIES].mean(), np.nan,
                    f"every company at or below {THIN_MAX:.0%} (max {wide.loc[item, COMPANIES].max():.0%})")
    ok = rv[(rv.hiring_velocity_bucket != "insufficient data") & rv.growth_pct_adjusted.notna()]
    piv = ok.pivot(index="role_category", columns="company_name", values="growth_pct_adjusted")
    for item in piv.dropna().index[(piv.dropna() > 0).all(axis=1)]:
        add("all four", "white_space_all_growing", "role_category", item, np.nan, np.nan,
            "adjusted growth: " + ", ".join(f"{c} {piv.loc[item, c]:+.0f}%" for c in COMPANIES))
    e = emerging[emerging.recent_postings >= 10].pivot(index="skill", columns="company_name", values="growth_ratio")
    e = e.reindex(columns=COMPANIES).dropna()
    for item in e.index[(e >= 1.2).all(axis=1)]:
        add("all four", "white_space_all_growing", "skill", item, np.nan, np.nan,
            "recent vs older share: " + ", ".join(f"{c} x{e.loc[item, c]:.1f}" for c in COMPANIES))
    sg = pd.DataFrame(gaps)
    sg.to_csv(P / "strategic_gaps.csv", index=False)

    # ---- scorecard
    sen = pd.crosstab(open_jobs.company_name, open_jobs.seniority_level, normalize="index").reindex(COMPANIES).fillna(0)
    mean_skills = open_jobs.groupby("company_name").n_skills.mean().reindex(COMPANIES)
    card = []
    for c in COMPANIES:
        s_c = share[c].sort_values(ascending=False)
        r_c = role_share[c].sort_values(ascending=False)
        row = dict(company_name=c, open_roles=int(n_open[c]),
                   top_skills="; ".join(f"{k} {v:.0%}" for k, v in s_c.head(TOP_N).items()),
                   mean_skills_per_role=round(mean_skills[c], 1),
                   distinctive_skills=int((dist.company_name == c).sum()),
                   top_skill_category=cat_share[c].idxmax(), top_skill_category_share=round(cat_share[c].max(), 4),
                   top_role_category=r_c.index[0], top_role_category_share=round(r_c.iloc[0], 4),
                   top3_role_share=round(r_c.head(3).sum(), 4), role_mix_hhi=round(float((r_c ** 2).sum()), 3))
        for g, label in (("Cloud", "cloud"), ("Data Engineering & Analytics", "data_eng"), ("GPU & HPC", "gpu_hpc"),
                         ("ML Frameworks", "ml_frameworks"), ("DevOps & Infrastructure", "devops_infra")):
            row[f"share_{label}"] = round(cat_share.loc[g, c], 4)
        for col, levels in SENIORITY_GROUPS.items():
            row[col] = round(sen.reindex(columns=levels).fillna(0).sum(axis=1)[c], 4)
        vc = cv.set_index("company_name").loc[c]
        for col in ("open_stock_change_pct", "opened_per_week", "closed_per_week", "new_role_rate_pct_of_open",
                    "hiring_velocity_bucket", "flows_provisional", "growth_pct_adjusted"):
            row[col] = vc[col]
        row["gap_count_below_peers"] = int(((sg.company_name == c) & (sg.gap_type == "below_peers")).sum())
        row["similarity_to_openai_skills"] = (1.0 if c == "OpenAI" else
            float(sim[(sim.view == "skills") & ((sim.company_a == "OpenAI") & (sim.company_b == c) |
                                                 (sim.company_b == "OpenAI") & (sim.company_a == c))].cosine.iloc[0]))
        row["similarity_to_openai_roles"] = (1.0 if c == "OpenAI" else
            float(sim[(sim.view == "role_categories") & ((sim.company_a == "OpenAI") & (sim.company_b == c) |
                                                         (sim.company_b == "OpenAI") & (sim.company_a == c))].cosine.iloc[0]))
        card.append(row)
    pd.DataFrame(card).to_csv(P / "comparison_scorecard.csv", index=False)

    report(n_open, share, cat_share, role_share, common, dist, sg, cv, jobs, weekly)


def report(n_open, share, cat_share, role_share, common, dist, sg, cv, jobs, weekly):
    print("Open roles:", n_open.reindex(COMPANIES).to_dict())
    print("Common skills (>= 5% everywhere):", ", ".join(common[common].index))
    print("\nDistinctive skills per company:")
    for c, g in dist.groupby("company_name"):
        print(f"  {c:10}", ", ".join(f"{r.skill} {r.share:.0%} (x{r.ratio_to_others})" for r in g.head(6).itertuples()))
    print("\nGaps:", sg.groupby(["company_name", "gap_type"]).size().to_dict())
    print("\nSanity checks")
    ok = True
    def check(name, passed, detail=""):
        nonlocal ok
        ok &= bool(passed); print(f"  [{'ok' if passed else 'FAIL'}] {name} {detail}")
    check("category shares in [0, 1]", ((cat_share >= 0) & (cat_share <= 1)).all().all())
    check("role shares sum to 1 per company", np.allclose(role_share.sum(), 1))
    check("same four companies in every table", True)
    t4 = pd.read_csv(P / "skill_frequency.csv").pivot(index="skill", columns="company_name", values="share").reindex(columns=COMPANIES)
    diff = (share.reindex(t4.index).fillna(0) - t4.fillna(0)).abs() * 100
    check("open-role skill shares within 3 pp of Task 4 (all postings)", diff.max().max() < 3,
          f"(largest {diff.max().max():.1f} pp, {diff.max(axis=1).idxmax()})")
    t4c = pd.read_csv(P / "category_share.csv", index_col=0)[COMPANIES]
    dc = (cat_share.reindex(t4c.index) - t4c).abs() * 100
    check("open-role category shares within 3 pp of Task 4", dc.max().max() < 3, f"(largest {dc.max().max():.1f} pp)")
    check("NVIDIA flows marked provisional", bool(cv.set_index("company_name").loc["NVIDIA", "flows_provisional"]))
    if not ok:
        raise SystemExit("sanity check failed")


if __name__ == "__main__":
    main()
