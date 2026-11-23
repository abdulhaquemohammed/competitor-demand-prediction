# Week 4 (w/c 23 Nov 2026)

**Roles this week:** all four (individual track): Scrum Leader, Data Quality Lead, Documentation Lead, Technical Lead.

## Progress
- Completed Task 6: one comparison framework for OpenAI, Anthropic, Databricks and NVIDIA built from the Task 4 and Task 5 tables (`src/compare.py`): skill categories, common and distinctive skills, role mix, hiring velocity, tech-stack patterns, seniority, similarity, strategic gaps and white space. Nine output tables, notebook and report, including how OpenAI compares.
- Refreshed the Task 5 report to the 23 Nov snapshot (dated update note). Fixed `trends.py` so a week counts as complete per company from its own latest snapshot: NVIDIA's partial week of 16 Nov had made its velocity bucket look "low".
- Made the Task 6 "four companies in every table" check a real check, and corrected OpenAI's skill lane in the Task 6 summary (go-to-market and security, not ML).
- Completed Task 7: 8-week forecasts of weekly new roles for all four companies, seven candidate models (naive, moving average, drift, SES, damped Holt, ARIMA, Prophet) compared by rolling-origin backtest. The 4-week moving average was chosen for OpenAI and Databricks, damped Holt for NVIDIA, naive for Anthropic (nothing beat it). Notebook, report and four output tables.
- Snapshots continued Mon/Thu. NVIDIA was not collected on 20 and 23 Nov (HTTP 429 on its robots.txt check, not retried by rule).

## Decisions
- Compare open roles only (describes demand today); check against Task 4's all-postings shares (within 3 points).
- Snapshot flows are the primary velocity signal; NVIDIA stays flagged provisional.
- Adjusted posting-date growth is unstable between snapshots (OpenAI moved about 30 points in 3 days), so snapshot flows stay the headline signal.
- Seniority is reported but only the manager, director and intern rows are interpreted, because Anthropic and OpenAI rarely use "Senior" in titles.
- "Thin everywhere" only at skill-category level; thin role categories are small functions, not findings.
- Forecast horizon is 8 weeks, not the brief's 3 to 12 months: 26 weekly points cannot support more.
- Forecast the survivorship-adjusted series; trend models on the raw series would extrapolate the survivorship ramp.
- Model choice by the one-standard-error rule (simplest model within one SE of the best); an earlier 5% margin rule, set after the first run, was replaced. Intervals are empirical from backtest errors, checked leave-one-origin-out.

## Blockers
- NVIDIA has two usable snapshots (4 and 16 Nov); its robots.txt endpoint has returned HTTP 429 on the last two runs.

## Next steps
- Decide how to handle the NVIDIA 429s (wait, or review the robots check for that endpoint).
- Rerun `forecast.py` after each snapshot update; check whether Anthropic ever beats naive and whether NVIDIA's trend survives the next snapshot.
- Keep snapshots running.
