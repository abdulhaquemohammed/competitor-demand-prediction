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

Two data problems were fixed first: missed snapshots (Task 2 report, item 8) and NVIDIA's bulk-repost dates (section 3).

## 2. Method

| Decision | Choice | Why |
|---|---|---|
| Unit | Unique role: identical `description_hash` within company and week counts once. Raw count kept in `new_postings_raw` | One role posted in ten cities is one hiring decision |
| Window | Last 26 complete weeks (18 May to 9 Nov 2026). Current incomplete week and month dropped | A partial week looks like a decline |
| Survivorship correction | Weekly closure rate by posting-age band (0-7, 7-14, 14-30, 30-60, 60-90, 90-180, 180+ days) from jobs open at the first snapshot (4 Nov) that closed by the latest. Bands with under 30 jobs use the company-wide rate. `S(age) = exp(-cumulative closure rate)`; adjusted = observed / S(age), factor capped at 3 | Estimates how many roles were posted, not how many survive |
| Spikes | A week is flagged `spike` or `decline` if the adjusted count is outside median +/- 3 x MAD of the previous 8 weeks (at least 4 weeks of history, MAD floor 3) | Robust to one-off weeks; tested on the adjusted series because the raw series ramps up by survivorship alone |
| Snapshot flows | `opened` = in this snapshot but not the previous one, `closed` = the reverse. Real snapshot dates; the baseline is excluded from `opened`; failed snapshots are skipped | A missed snapshot would otherwise show as a mass closure |
| Velocity bucket (company) | New unique roles per week over the last 4 weeks as a share of open roles: low under 5%, medium 5-7%, high 7% or more | Size-neutral. Cut-offs are fixed round numbers set after seeing the four values (range 4.0% to 8.2%), so treat the labels as relative |
| Velocity bucket (role) | Terciles of adjusted growth across all company x category pairs. Pairs with under 10 unique roles in the 16-week window or no roles in the earlier 8 weeks are `insufficient data` | Tiny categories cannot be "high growth" |
| Seasonality | Day-of-week only | See limitations |

**Shared time-series structure.** `weekly_postings.csv` and `monthly_postings.csv` are one row per `company_name` + `week_start` (ISO Monday) or `month_start`, with metrics as columns, and the same weeks for every company. Task 7 forecasting can read them directly.

## 3. Validation

**NVIDIA bulk reposts.** 1,351 NVIDIA postings (45%) carried the date 30 Oct, a fake spike in 2026-W44. Their requisition numbers are old (median JR2022589, against JR2027456 for other October roles), so Workday reset `startDate` in a bulk repost. `build_dataset.py` detects such days for any company (a day with at least 50 postings and 10 times the company's median daily count). Only NVIDIA has any (30 Oct, plus 31 Oct, 2 Nov and 3 Nov, 1,582 postings in all).

| Route | Result |
|---|---|
| Impute dates from requisition number (rolling median of date by requisition number, then interpolate) | 5-fold held-out MAE on normal NVIDIA postings: **36.6 days**. Spearman 0.68 |
| Rule | Impute only if MAE is 30 days or less |
| **Route taken** | **Fallback.** Dates kept, `posting_date_source = "bulk_repost"`, original in `posting_date_raw`. These 1,582 postings are left out of new-posting counts and the date-based Task 4 tables, and kept in open-stock counts |

Requisition numbers rise with time but too loosely to date a role within a month, so imputing would invent precision. Detail per company: `docs/posting_date_fix.csv`.

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

Snapshot figures are 4 to 20 Nov (NVIDIA 4 to 16 Nov, because its 19 and 20 Nov snapshots failed).

| Company | New roles/week (last 4 wks) | Adjusted growth vs previous 4 | Opened / closed per week | Open roles, change | Bucket |
|---|---|---|---|---|---|
| OpenAI | 69.5 | +3.0% | 91.0 / 75.2 | 817 to 853 (+4.4%) | high |
| Anthropic | 44.2 | -29.3% | 49.9 / 68.2 | 681 to 639 (-6.2%) | medium |
| Databricks | 46.0 | -1.4% | 57.3 / 70.4 | 925 to 895 (-3.2%) | medium |
| NVIDIA | 107.8 | +35.5% | 145.8 / 183.8 | 2,755 to 2,690 (-2.4%) | low |

**OpenAI (main company).**
- The only company whose open stock grew (+4.4%): it opened about 91 roles a week and closed about 75. Its new-role rate, 8.2% of open roles per week, is the highest of the four.
- Raw new roles rose 57% (44.2 to 69.5 a week), but adjusted growth is only +3%. Most of the raw rise is survivorship. The real signal is the flow: more opened than closed.
- By role (adjusted, last 8 weeks vs previous 8): fastest growth in Marketing & Comms (4.0 new roles a week, +229%), Corporate (+163%), Product & Design (+122%) and Security (+95%). Software Engineering (11.0 a week, the biggest category) is down 13% and Research down 41%. So OpenAI's recent hiring leans commercial and operational more than technical.
- Posts on weekdays: 96% Monday to Friday.

**Comparison.**
- **Anthropic** is contracting slightly: closures (68 a week) exceed openings (50), and adjusted growth is negative. Growth categories: Solutions & Field (+41%), Security (+38%) and Marketing & Comms (+60%).
- **Databricks** is flat (adjusted -1.4%). Growth sits in Sales & Partnerships (14.5 new roles a week, +87%), consistent with the Task 4 sales-skill signals. Software Engineering is down 10%.
- **NVIDIA** is the largest hirer in volume (about 108 new unique roles a week) but the lowest rate against its open stock. Growth is broad: Research (+133%), Data (+224%), Hardware and Software Engineering (+22% and +17%). Treat its posting-date growth with caution (section 6) and use the flows.
- **Churn is high everywhere**: 7 to 10% of open roles close each week. At that rate a role's median life is roughly two months.

**Spikes and declines.** Most flags fall in June to August (Anthropic 10 to 24 Aug, OpenAI 3 to 17 Aug and 31 Aug, NVIDIA 17 to 24 Aug). The correction is capped at 3 before about August, so earlier weeks are a floor and the August flags partly reflect that step. Treat flags from September onwards as the reliable ones: Anthropic declines in the weeks of 26 Oct and 9 Nov, Databricks a decline on 28 Sep then a spike on 5 Oct. OpenAI has none since 31 Aug.

**Day of week.** 95 to 96% of OpenAI, Anthropic and Databricks postings land Monday to Friday, and 91% for NVIDIA, which has more weekend postings (about 9%).

## 6. Limitations

- **No monthly or annual seasonality.** There is under a year of usable data, and older months are survivors only. Estimating seasonality would mix real seasonal swing with survivorship. Only day-of-week is reported. This needs a year of snapshots or the Kaggle baseline.
- **The survival curve comes from 16 days.** Closure rates of 4 to 12% a week are measured on one short window and assumed constant for older ages. The 3x cap limits the damage, but adjusted figures for weeks before August are floors. Short-term feed flicker (a role closing and reopening) raises measured closure.
- **Snapshot flows are short and uneven.** Intervals are 1 to 12 days; per-week rates from 1-day intervals are noisy. NVIDIA has one interval only (4 to 16 Nov), because its 19 Nov snapshot hit read timeouts and its 20 Nov run was stopped by HTTP 429. Neither was retried, by rule.
- **NVIDIA dates.** The bulk-repost rule also removes 31 Oct, 2 Nov and 3 Nov, which probably include some genuinely new roles, so NVIDIA's most recent weeks are somewhat understated and its growth percentages are unreliable. NVIDIA dates are date-only, the others carry a time (UTC).
- **Unique-role collapse** treats identical descriptions as one role. Roles that are reposted with the same text in the same week are also merged.
- **Role categories** are rule-based on titles (Task 4); "Other" is large for OpenAI (68 roles in the window).
- **Small cells.** Role-growth percentages on a base of 1 or 2 roles a week swing widely. Read sign and rank only. 10 of 51 company-category pairs have too little data for a bucket.
- **Velocity buckets are relative.** With four companies the cut-offs are judgement, not statistics.
