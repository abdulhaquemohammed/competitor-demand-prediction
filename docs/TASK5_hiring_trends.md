# Task 5: Hiring Trend Analysis

**Project:** Competitor Demand Prediction Using Job Postings (CadetX)
**Author:** Abdul-Haque Mohammed (individual track)
**Date:** 20 November 2026, figures refreshed to the 23 November snapshot (tables refresh with every Mon/Thu snapshot; see section 7)

## 1. Summary

`src/trends.py` aggregates new postings by week and month, measures hiring velocity from snapshot to snapshot, and flags growth, decline and spikes. Walkthrough with charts: `notebooks/05_trends.ipynb`.

Two series, with opposite weaknesses:

| Series | Source | Strength | Weakness |
|---|---|---|---|
| Posting-date (weekly, monthly) | `posting_date` of open roles | Long: 26 weeks | Biased: closed roles are missing, so older weeks look emptier. Raw counts look like acceleration even when hiring is flat |
| Snapshot flows | Which jobs were open at each snapshot | Unbiased: we watch jobs open and close | Short: since 4 Nov 2026 (19 days, NVIDIA 12) |

Two data problems were fixed first: missed snapshots (Task 2 report, item 8) and NVIDIA's bulk-repost dates (section 3). Where the two series disagree, trust the snapshot flows.

## 2. Method

| Decision | Choice | Why |
|---|---|---|
| Unit | Unique role: identical `description_hash` within company and week counts once. Raw count kept in `new_postings_raw` | One role posted in ten cities is one hiring decision |
| Window | Last 26 complete weeks (25 May to 16 Nov 2026). A week is complete for a company only if its latest snapshot is after that week's Sunday, so NVIDIA (latest snapshot 16 Nov) stops at the week of 9 Nov and its later weeks are blank. Current incomplete week and month dropped | A partial week looks like a decline |
| Survivorship correction | Weekly closure rate by posting-age band (0-7, 7-14, 14-30, 30-60, 60-90, 90-180, 180+ days) from jobs open at the first snapshot (4 Nov) that closed by the latest. Bands with under 30 jobs use the company-wide rate. `S(age) = exp(-cumulative closure rate)`; adjusted = observed / S(age), factor capped at 3 | Estimates how many roles were posted, not how many survive |
| Spikes | A week is flagged `spike` or `decline` if the adjusted count is outside median +/- 3 x MAD of the previous 8 weeks (at least 4 weeks of history, MAD floor 3) | Robust to one-off weeks; tested on the adjusted series because the raw series ramps up by survivorship alone |
| Snapshot flows | `opened` = in this snapshot but not the previous one, `closed` = the reverse. Real snapshot dates; the baseline is excluded from `opened`; failed snapshots are skipped | A missed snapshot would otherwise show as a mass closure |
| Velocity bucket (company) | New unique roles per week over the last 4 weeks as a share of open roles: low under 5%, medium 5-7%, high 7% or more | Size-neutral. Cut-offs are fixed round numbers set after seeing the four values (range 5.3% to 9.6% at 23 Nov), so treat the labels as relative |
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

**Cross-check: adjusted posting-date series vs snapshot inflow.** The survivorship-adjusted new roles per week (each company's latest 2 complete weeks: 9 and 16 Nov, NVIDIA 2 and 9 Nov) should roughly match the unbiased inflow from the snapshots (`opened_per_week`, 4 to 23 Nov; NVIDIA 4 to 16 Nov).

| Company | Adjusted new roles/week | Snapshot opened/week | Ratio |
|---|---|---|---|
| OpenAI | 105.0 | 82.5 | 1.27 |
| Anthropic | 40.1 | 44.6 | 0.90 |
| Databricks | 41.0 | 50.1 | 0.82 |
| NVIDIA | 242.1 | 145.8 | 1.66 |

Agreement means the survival correction is about right for the recent weeks. For OpenAI, Anthropic and Databricks the two views are within 27%, so the adjusted series is usable as direction, not as a level. OpenAI's ratio moved from 1.13 on 20 Nov to 1.27 on 23 Nov, which shows how unstable the adjusted figure is. NVIDIA disagrees by 66%, mainly because the week of 2 Nov holds 274 unique roles, including the busy days of 2 and 3 Nov (167 postings). NVIDIA's snapshot interval is also a single 12-day one, so I do not trust either figure yet. The snapshot count is postings, not unique roles, so the comparison is approximate.

**Task 4 check.** No skill share for OpenAI, Anthropic or Databricks moved by 3 points or more because of this fix; see the dated note in `docs/TASK4_skill_extraction.md`.

**Sanity checks (all pass on every run of `trends.py`):** weekly and monthly raw sums equal the postings in the window; adjusted is at least unique, and unique is at most raw; no posting date after the latest snapshot; the same 26 weeks for all four companies; no incomplete week for any company (judged by its own latest snapshot); no bulk-repost row in new-posting counts.

## 4. Outputs (`data/processed/`, all committed: no description text)

| File | What | Used in |
|---|---|---|
| `weekly_postings.csv` | Per company and week: `new_postings_raw`, `new_roles_unique`, `new_roles_adjusted`, `rolling_4w`, `wow_change_pct`, `spike_flag`. Weeks a company's snapshots do not yet cover are blank | Tasks 7, 9 |
| `monthly_postings.csv` | Same per complete month, 5 months (June to October). `rolling_3m`, `mom_change_pct`; `spike_flag` empty (too few months) | Task 7 |
| `snapshot_flows.csv` | Per company and snapshot interval: `open_postings`, `opened`, `closed`, `net_change`, `days`, per week | Tasks 7, 9 |
| `velocity_summary.csv` | Per company: last 4 vs previous 4 weeks, growth (raw and adjusted), flows, open-stock change, bucket | Tasks 6, 9 |
| `role_velocity.csv` | Company x role category: last 8 vs previous 8 weeks, growth, bucket | Tasks 6, 9 |
| `posting_weekday.csv` | Share of postings by weekday per company | Task 9 |

## 5. Key hiring patterns

Lead with the snapshot flows (unbiased, 4 to 23 Nov; NVIDIA 4 to 16 Nov, because its snapshots on 19, 20 and 23 Nov were not collected). Adjusted posting-date growth is second and moves a lot between snapshots (section 6). NVIDIA flow figures are **provisional**: one 12-day interval.

| Company | Open roles, change | Opened / closed per week | Adjusted new-role growth, last 4 vs previous 4 weeks | New roles/week (last 4) | Bucket |
|---|---|---|---|---|---|
| OpenAI | 817 to 852 (+4.3%) | 82.5 / 69.6 | +32.6% | 81.5 | high |
| Anthropic | 681 to 635 (-6.8%) | 44.6 / 61.5 | -34.5% (low confidence) | 42.0 | medium |
| Databricks | 925 to 893 (-3.5%) | 50.1 / 61.9 | -2.7% | 47.5 | medium |
| NVIDIA (provisional) | 2,755 to 2,690 (-2.4%) | 145.8 / 183.8 | +88.3% (driven by the week of 2 Nov) | 149.5 | medium |

**OpenAI (main company).**
- Flows first: the only company whose open stock grew (+4.3%). It opened about 83 roles a week and closed about 70, and its new-role rate, 9.6% of open roles per week, is the highest of the four.
- Raw new roles rose 87% (43.5 to 81.5 a week); adjusted growth is +32.6%. That figure was +3.0% on 20 Nov, so treat it as direction only. The flow, more opened than closed, is the headline.
- By role (adjusted, last 8 weeks vs previous 8): fastest growth in Marketing & Comms (4.5 new roles a week, +143%), Product & Design (+96%), Corporate (+94%), Security (+59%) and Data (+56%). Software Engineering (10.5 a week, the biggest category) is down 30%, Solutions & Field down 31% and Research down 29%. So OpenAI's recent hiring leans commercial and operational more than technical.

**Comparison.**
- **Anthropic** is contracting: closures (about 62 a week) exceed openings (about 45), and open stock fell 6.8%. Its adjusted growth of -34.5% is **low confidence**: about 9% of its open roles close each week, so the survival correction is large and the figure leans on it. Growth categories: Marketing & Comms (+75%), Security (+20%) and Solutions & Field (+5%).
- **Databricks** is flat to slightly shrinking: stock -3.5%, closures above openings, adjusted growth -2.7%. Growth sits in Sales & Partnerships (14.5 new roles a week, +89%), consistent with the Task 4 sales-skill signals. Software Engineering is down 14%.
- **NVIDIA** (provisional) is the largest hirer by volume. Its open stock fell 2.4% over the 12 days (about 146 opened and 184 closed a week), so the flows show no growth. The posting-date series shows a sharp rise (+88.3% adjusted) that comes from the week of 2 Nov (274 unique roles, flagged as a spike) and is not confirmed by the flows. Role growth is broad: Research (+175%), Product & Design (+205%), Data (+221%, 13 roles), Hardware and Software Engineering (+43% and +44%).
- **Churn is high everywhere**: 7 to 9% of open roles close each week. At that rate a role's median life is roughly two months.

**Spikes and declines.** Most flags fall in June to August (Anthropic 10 to 24 Aug, OpenAI 3 to 17 Aug and 31 Aug, Databricks 24 Aug, NVIDIA 17 to 24 Aug). The correction is capped at 3 before about August, so earlier weeks are a floor and the August flags partly reflect that step. Treat flags from September onwards as the reliable ones: Anthropic declines in the weeks of 26 Oct, 9 Nov and 16 Nov, Databricks spikes in the weeks of 5, 12 and 26 Oct, OpenAI spikes in the weeks of 2 and 9 Nov, and NVIDIA's week of 2 Nov (274 unique roles).

**Day of week.** Monday to Friday takes 95.8% of OpenAI postings, 94.7% of Anthropic, 95.2% of Databricks and 92.5% of NVIDIA, which has the most weekend postings (7.5%).

## 6. Limitations

- **No monthly or annual seasonality.** There is under a year of usable data, and older months are survivors only. Estimating seasonality would mix real seasonal swing with survivorship. Only day-of-week is reported. This needs a year of snapshots or the Kaggle baseline.
- **The survival curve comes from 19 days.** Closure rates of 4 to 11% a week are measured on one short window and assumed constant for older ages. The 3x cap limits the damage, but adjusted figures for weeks before August are floors. Short-term feed flicker (a role closing and reopening) raises measured closure.
- **Adjusted growth is unstable between snapshots.** OpenAI's adjusted growth moved about 30 points in 3 days (+3.0% on 20 Nov, +32.6% on 23 Nov) while its snapshot flows barely changed (stock +4.4% to +4.3%). The correction rests on a short closure window and a sliding 4-week comparison, so snapshot flows stay the headline signal and adjusted growth is direction only.
- **Snapshot flows are short and uneven.** Intervals are 1 to 7 days (NVIDIA 12); per-week rates from 1-day intervals are noisy. NVIDIA has one interval only (4 to 16 Nov), because its 19 Nov snapshot hit read timeouts and its 20 and 23 Nov runs were stopped by HTTP 429. None was retried, by rule. Its weekly rows from 16 Nov are blank because its data does not cover them.
- **NVIDIA dates.** The two confirmed repost days (30 and 31 Oct, 1,415 postings) are left out of new-posting counts. The 31 Oct decision is close (see the table in section 3). 2 and 3 Nov are kept as genuine, so the week of 2 Nov is very large, and NVIDIA's growth percentages should be read with that in mind. NVIDIA dates are date-only, the others carry a time (UTC).
- **Unique-role collapse** treats identical descriptions as one role. Roles that are reposted with the same text in the same week are also merged.
- **Role categories** are rule-based on titles (Task 4); "Other" is large for OpenAI (81 roles in the window).
- **Small cells.** Role-growth percentages on a base of 1 or 2 roles a week swing widely. Read sign and rank only. 9 of 51 company-category pairs have too little data for a bucket.
- **Velocity buckets are relative.** With four companies the cut-offs are judgement, not statistics.

## 7. Update, 23 November 2026

This report was written on the 20 Nov snapshot. The 23 Nov snapshot (OpenAI, Anthropic, Databricks; NVIDIA not collected) and a window one week further on (last complete week 16 Nov, was 9 Nov) moved these figures:

| Figure | 20 Nov | 23 Nov | Why |
|---|---|---|---|
| OpenAI adjusted new-role growth | +3.0% | +32.6% | Window slid one week (last 4 weeks now 26 Oct to 16 Nov); the latest weeks hold 92 and 99 unique roles. The correction is sensitive to this |
| Anthropic adjusted growth | -29.3% | -34.5% | Same |
| Databricks adjusted growth | -1.4% | -2.7% | Same |
| OpenAI open roles / rate | +4.4%, 8.2% | +4.3%, 9.6% | Snapshot flows barely moved; the new-role rate rose with the busier last weeks |
| Anthropic / Databricks open roles | -6.2% / -3.2% | -6.8% / -3.5% | Two more snapshots |
| OpenAI role growth: Software Engineering / Research | -13% / -41% | -30% / -29% | 8-week windows moved; direction unchanged |
| NVIDIA | stock -2.4%, growth +87.4% | stock -2.4%, growth +88.3% | No new NVIDIA snapshot. Small change from the week-completeness fix below |
| Buckets | high, medium, medium, medium | high, medium, medium, medium | Unchanged |

**Fix made in this update.** NVIDIA's latest snapshot is 16 Nov, but the week of 16 Nov counted as complete for every company. It held only 12 NVIDIA roles, which pulled NVIDIA's last-4-week rate down (bucket "low" at 4.8%) and added a false "decline" flag. `trends.py` now judges completeness per company from its own latest snapshot, so NVIDIA's weeks from 16 Nov are blank and its last 4 weeks are the weeks of 19 Oct to 9 Nov.
