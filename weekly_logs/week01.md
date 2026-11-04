# Week 1 (w/c 2 Nov 2026)

**Roles this week:** all four (individual track): Scrum Leader, Data Quality Lead, Documentation Lead, Technical Lead.

## Progress
- Read the brief; confirmed individual (solo) track with CadetX support.
- Completed Task 1: assessed data sources, legal and ethical requirements, plan for Task 2.
- Verified robots.txt and live API access for Greenhouse, Ashby and Workday (4 Nov).
- Set up project repo and folder structure.
- Completed Task 2: collection script, first snapshot on 4 Nov (5,182 postings: OpenAI 818, Anthropic 682, Databricks 926, NVIDIA 2,756), Data Collection Report.

## Decisions
- Cover four companies myself (OpenAI main; Anthropic, Databricks, NVIDIA comparison) so Tasks 6 and 8 are possible solo.
- Use official public job-board feeds only; rejected direct scraping of Google, Meta, Microsoft, LinkedIn.
- Raw job descriptions git-ignored (copyright); commit derived data only.
- Collect snapshots twice a week to build a time series.

- Remove personal data (emails, phones, recruiter names) at collection time, not later.
- Collect NVIDIA one job family at a time to get round Workday's 2,000-result cap.

## Blockers
- Live feeds only show open roles, so history must be built from repeated snapshots. Kaggle dataset added as historical baseline.
- Workday caps searches at 2,000 results and loops; fixed by searching per job family.

## Next steps
- Start the Mon/Thu snapshot schedule.
- Ask CadetX how they want the raw dataset submitted (it can't go in the public repo).
- Task 3: NLP preprocessing.
