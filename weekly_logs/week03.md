# Week 3 (w/c 16 Nov 2026)

**Roles this week:** all four (individual track): Scrum Leader, Data Quality Lead, Documentation Lead, Technical Lead.

## Progress
- Fixed snapshot reliability: snapshots on 5, 9, 12 and 19 Nov were partly lost to network errors after the Mac woke and to NVIDIA Workday read timeouts. `collect.py` now reports the real reason, retries network errors only (max 3 attempts, 30s then 60s wait), stops a company on HTTP 429, and retries single NVIDIA list pages. `run_snapshot.sh` waits up to 5 minutes for the network.
- Took a fresh snapshot on 20 Nov: OpenAI 853, Anthropic 639, Databricks 895. NVIDIA was stopped by an HTTP 429 and not retried.
- Found and handled NVIDIA's bulk-repost dates: 1,415 postings with reset start dates on 30 and 31 Oct (1,351 on 30 Oct alone). The count rule alone also caught 2 and 3 Nov, so I added a requisition-age check; those two days are genuine new roles. Requisition-number imputation had a 37.0-day held-out error, over my 30-day limit, so the reposted postings are flagged `bulk_repost` and left out of new-posting counts. Task 4 refreshed; no skill share moved by 3 points or more because of this.
- Completed Task 5 (started early, on 20 Nov, instead of 23 Nov): weekly and monthly new-role series with a survivorship correction, snapshot flows, velocity buckets, role-category growth, day-of-week pattern, notebook and report. The trend tables refresh automatically with every snapshot.

## Decisions
- Report velocity on unique roles (identical descriptions in a week count once), raw counts kept as a column.
- Treat the posting-date series as long but biased and the snapshot flows as unbiased but short; show raw and adjusted side by side, correction capped at 3x.
- No monthly or annual seasonality (under a year of data, plus survivorship bias): day-of-week only.
- Do not impute NVIDIA dates when the validation error is above 30 days; flag them instead.

## Blockers
- NVIDIA has only 2 usable snapshots (4 and 16 Nov), so its flow figures cover a single 12-day interval.
- The survival curve rests on 16 days of closures, so adjusted figures for weeks before August are floors.

## Next steps
- Let the Mon/Thu snapshots build up; check that the trend tables and survival curve settle.
- Start Task 6 using `velocity_summary.csv`, `role_velocity.csv` and the Task 4 tables.
- Plan Task 7 forecasting on `weekly_postings.csv`.
- Ask CadetX how they want the raw dataset submitted.
