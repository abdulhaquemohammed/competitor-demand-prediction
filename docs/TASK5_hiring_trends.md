# Task 5: Hiring Trend Analysis

**Project:** Competitor Demand Prediction Using Job Postings (CadetX)
**Author:** Abdul-Haque Mohammed (individual track)
**Date:** 20 November 2026 (tables refresh with every Mon/Thu snapshot)

## 1. Summary

`src/trends.py` aggregates new postings by week and month, measures hiring velocity from snapshot to snapshot, and flags growth, decline and spikes. Walkthrough with charts: `notebooks/05_trends.ipynb`.

Two series, with opposite weaknesses:

| Series | Source | Strength | Weakness |
|---|---|---|---|
| Posting-date (weekly, monthly) | `posting_date` of open roles | Long: 26 weeks | Biased: closed roles are missing, so older weeks look emptier. Raw counts look like acceleration even when hiring is flat |
| Snapshot flows | Which jobs were open at each snapshot | Unbiased: we watch jobs open and close | Short: since 4 Nov 2026 (16 days, NVIDIA 12) |

Two data problems were fixed first: missed snapshots (Task 2 report, item 8) and NVIDIA's bulk-repost dates (section 3). Where the two series disagree, trust the snapshot flows.

## 2. Method

| Decision | Choice | Why |
|---|---|---|
| Unit | Unique role: identical `description_hash` within company and week counts once. Raw count kept in `new_postings_raw` | One role posted in ten cities is one hiring decision |
| Window | Last 26 complete weeks (18 May to 9 Nov 2026). Current incomplete week and month dropped | A partial week looks like a decline |
| Survivorship correction | Weekly closure rate by posting-age band (0-7, 7-14, 14-30, 30-60, 60-90, 90-180, 180+ days) from jobs open at the first snapshot (4 Nov) that closed by the latest. Bands with under 30 jobs use the company-wide rate. `S(age) = exp(-cumulative closure rate)`; adjusted = observed / S(age), factor capped at 3 | Estimates how many roles were posted, not how many survive |
| Spikes | A week is flagged `spike` or `decline` if the adjusted count is outside median +/- 3 x MAD of the previous 8 weeks (at least 4 weeks of history, MAD floor 3) | Robust to one-off weeks; tested on the adjusted series because the raw series ramps up by survivorship alone |
| Snapshot flows | `opened` = in this snapshot but not the previous one, `closed` = the reverse. Real snapshot dates; the baseline is excluded from `opened`; failed snapshots are skipped | A missed snapshot would otherwise show as a mass closure |
| Velocity bucket (company) | New unique roles per week over the last 4 weeks as a share of open roles: low under 5%, medium 5-7%, high 7% or more | Size-neutral. Cut-offs are fixed round numbers set after seeing the four values (range 5.1% to 8.2%), so treat the labels as relative |
| Velocity bucket (role) | Terciles of adjusted growth across all company x category pairs. Pairs with under 10 unique roles in the 16-week window or no roles in the earlier 8 weeks are `insufficient data` | Tiny categories cannot be "high growth" |
| Seasonality | Day-of-week only | See limitations |

**Shared time-series structure.** `weekly_postings.csv` and `monthly_postings.csv` are one row per `company_name` + `week_start` (ISO Monday) or `month_start`, with metrics as columns, and the same weeks for every company. Task 7 forecasting can read them directly.

## 3. Validation

**NVIDIA bulk reposts.** 1,351 NVIDIA postings (45%) carried the date 30 Oct, a fake spike in 2026-W44. Their requisition numbers are old (median JR2022589, against JR2027456 for other October roles), so Workday reset `startDate` in a bulk repost. `build_dataset.py` finds candidate days for any company by count (at least 50 postings and 10 times the company's median daily count). For companies with numeric requisition IDs a candidate is only a bulk-repost day if its median requisition number is below the 25th percentile of requisition numbers on non-candidate days within 14 days either side. A genuinely busy day has new requisitions; a repost does not. Companies without numeric IDs use the count rule alone.

| Candidate day (NVIDIA) | Postings | Median req | 25th percentile nearby | Bulk repost? |
|---|---|---|---|---|
| 30 Oct | 1,351 | JR2022589 | JR2024595 | yes |
| 31 Oct | 64 | JR2024465 | JR2024758 | yes |
| 2 Nov | 100 | JR2028307 | JR2024849 | no, genuine new roles |
| 3 Nov | 67 | JR2027828 | JR2024942 | no, genuine new roles |

No other company has a candidate day. Full table: `docs/bulk_repost_candidates.csv`. The 31 Oct margin is thin (JR2024465 against JR2024758).

| Route | Result |
|---|---|
| Impute dates from requisition number (rolling median of date by requisition number, then interpolate) | 5-fold held-out MAE on normal NVIDIA postings: **37.0 days**. Spearman 0.70 |
| Rule | Impute only if MAE is 30 days or less |
| **Route taken** | **Fallback.** Dates kept, `posting_date_source = "bulk_repost"`, original in `posting_date_raw`. These 1,415 postings are left out of new-posting counts and the date-based Task 4 tables, and kept in open-stock counts |

Requisition numbers rise with time but too loosely to date a role within a month, so imputing would invent precision. Detail per company: `docs/posting_date_fix.csv`.

**Cross-check: adjusted posting-date series vs snapshot inflow.** The survivorship-adjusted new roles per week (latest 2 complete weeks, 2 and 9 Nov) should roughly match the unbiased inflow from the snapshots (`opened_per_week`, 4 to 20 Nov; NVIDIA 4 to 16 Nov).

| Company | Adjusted new roles/week | Snapshot opened/week | Ratio |
|---|---|---|---|
| OpenAI | 103.2 | 91.0 | 1.13 |
| Anthropic | 54.4 | 49.9 | 1.09 |
| Databricks | 49.4 | 57.3 | 0.86 |
| NVIDIA | 236.4 | 145.8 | 1.62 |

Agreement means the survival correction is about right for the recent weeks. For OpenAI, Anthropic and Databricks the two views are within 14%, so the adjusted series is usable. NVIDIA disagrees by 62%, mainly because the week of 2 Nov holds 274 unique roles, including the busy days of 2 and 3 Nov (167 postings). The snapshot interval for NVIDIA is also a single 12-day one, so I do not trust either figure yet. The snapshot count is postings, not unique roles, so the comparison is approximate.

**Task 4 check.** No skill share for OpenAI, Anthropic or Databricks moved by 3 points or more because of this fix; see the dated note in `docs/TASK4_skill_extraction.md`.

**Sanity checks (all pass on every run of `trends.py`):** weekly and monthly raw sums equal the postings in the window; adjusted is at least unique, and unique is at most raw; no posting date after the latest snapshot; the same 26 weeks for all four companies; no incomplete week; no bulk-repost row in new-posting counts.

## 4. Outputs (`data/processed/`, all committed: no description text)

| File | What | Used in |
|---|---|---|
| `weekly_postings.csv` | Per company and week: `new_postings_raw`, `new_roles_unique`, `new_roles_adjusted`, `rolling_4w`, `wow_change_pct`, `spike_flag` | Tasks 7, 9 |
| `monthly_postings.csv` | Same per complete month, 5 months (June to October). `rolling_3m`, `mom_change_pct`; `spike_flag` empty (too few months) | Task 7 |
| `snapshot_flows.csv` | Per company and snapshot interval: `open_postings`, `opened`, `closed`, `net_change`, `days`, per week | Tasks 7, 9 |
| `velocity_summary.csv` | Per company: last 4 vs previous 4 weeks, growth (raw and adjusted), flows, open-stock change, bucket | Tasks 6, 9 |
| `role_velocity.csv` | Company x role category: last 8 vs previous 8 weeks, growth, bucket | Tasks 6, 9 |
| `posting_weekday.csv` | Share of postings by weekday per company | Task 9 |

## 5. Key hiring patterns

Lead with the snapshot flows (unbiased, 4 to 20 Nov; NVIDIA 4 to 16 Nov, because its 19 and 20 Nov snapshots failed). Adjusted posting-date growth is second. NVIDIA flow figures are **provisional**: one 12-day interval.

| Company | Open roles, change | Opened / closed per week | Adjusted new-role growth, last 4 vs previous 4 weeks | New roles/week (last 4) | Bucket |
|---|---|---|---|---|---|
| OpenAI | 817 to 853 (+4.4%) | 91.0 / 75.2 | +3.0% | 69.5 | high |
| Anthropic | 681 to 639 (-6.2%) | 49.9 / 68.2 | -29.3% (low confidence) | 44.2 | medium |
| Databricks | 925 to 895 (-3.2%) | 57.3 / 70.4 | -1.4% | 46.0 | medium |
| NVIDIA (provisional) | 2,755 to 2,690 (-2.4%) | 145.8 / 183.8 | +87.4% (driven by the week of 2 Nov) | 149.5 | medium |

**OpenAI (main company).**
- Flows first: the only company whose open stock grew (+4.4%). It opened about 91 roles a week and closed about 75, and its new-role rate, 8.2% of open roles per week, is the highest of the four.
- Adjusted posting-date growth is only +3.0%. Raw new roles rose 57% (44.2 to 69.5 a week), but most of that is survivorship. The flow, more opened than closed, is the real signal.
- By role (adjusted, last 8 weeks vs previous 8): fastest growth in Marketing & Comms (4.0 new roles a week, +229%), Corporate (+163%), Product & Design (+122%) and Security (+95%). Software Engineering (11.0 a week, the biggest category) is down 13% and Research down 41%. So OpenAI's recent hiring leans commercial and operational more than technical.

**Comparison.**
- **Anthropic** is contracting slightly: closures (68 a week) exceed openings (50), and open stock fell 6.2%. Its adjusted growth of -29.3% is **low confidence**: about 10% of its open roles close each week, so the survival correction is large and the figure leans on it. Growth categories: Solutions & Field (+41%), Security (+38%) and Marketing & Comms (+60%).
- **Databricks** is flat to slightly shrinking: stock -3.2%, closures above openings, adjusted growth -1.4%. Growth sits in Sales & Partnerships (14.5 new roles a week, +87%), consistent with the Task 4 sales-skill signals. Software Engineering is down 10%.
- **NVIDIA** (provisional) is the largest hirer by volume. Its open stock fell 2.4% over the 12 days (about 146 opened and 184 closed a week), so the flows show no growth. The posting-date series shows a sharp rise (+87.4% adjusted) that comes from the week of 2 Nov (274 unique roles, flagged as a spike) and is not confirmed by the flows. Role growth is broad: Research (+175%), Product & Design (+205%), Data (+224%, 13 roles), Hardware and Software Engineering (+44% each).
- **Churn is high everywhere**: 7 to 10% of open roles close each week. At that rate a role's median life is roughly two months.

**Spikes and declines.** Most flags fall in June to August (Anthropic 10 to 24 Aug, OpenAI 3 to 17 Aug and 31 Aug, NVIDIA 17 to 24 Aug and the week of 2 Nov). The correction is capped at 3 before about August, so earlier weeks are a floor and the August flags partly reflect that step. Treat flags from September onwards as the reliable ones: Anthropic declines in the weeks of 26 Oct and 9 Nov, Databricks a decline on 28 Sep then a spike on 5 Oct. NVIDIA's week of 2 Nov is a spike (274 unique roles). OpenAI has none since 31 Aug.

**Day of week.** 95 to 96% of OpenAI, Anthropic and Databricks postings land Monday to Friday, and 92% for NVIDIA, which has more weekend postings (about 8%).

## 6. Limitations

- **No monthly or annual seasonality.** There is under a year of usable data, and older months are survivors only. Estimating seasonality would mix real seasonal swing with survivorship. Only day-of-week is reported. This needs a year of snapshots or the Kaggle baseline.
- **The survival curve comes from 16 days.** Closure rates of 4 to 12% a week are measured on one short window and assumed constant for older ages. The 3x cap limits the damage, but adjusted figures for weeks before August are floors. Short-term feed flicker (a role closing and reopening) raises measured closure.
- **Snapshot flows are short and uneven.** Intervals are 1 to 12 days; per-week rates from 1-day intervals are noisy. NVIDIA has one interval only (4 to 16 Nov), because its 19 Nov snapshot hit read timeouts and its 20 Nov run was stopped by HTTP 429. Neither was retried, by rule.
- **NVIDIA dates.** The two confirmed repost days (30 and 31 Oct, 1,415 postings) are left out of new-posting counts. The 31 Oct decision is close (see the table in section 3). 2 and 3 Nov are kept as genuine, so the week of 2 Nov is very large, and NVIDIA's growth percentages should be read with that in mind. NVIDIA dates are date-only, the others carry a time (UTC).
- **Unique-role collapse** treats identical descriptions as one role. Roles that are reposted with the same text in the same week are also merged.
- **Role categories** are rule-based on titles (Task 4); "Other" is large for OpenAI (68 roles in the window).
- **Small cells.** Role-growth percentages on a base of 1 or 2 roles a week swing widely. Read sign and rank only. 10 of 51 company-category pairs have too little data for a bucket.
- **Velocity buckets are relative.** With four companies the cut-offs are judgement, not statistics.
