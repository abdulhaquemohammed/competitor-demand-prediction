# Week 4 (w/c 23 Nov 2026)

**Roles this week:** all four (individual track): Scrum Leader, Data Quality Lead, Documentation Lead, Technical Lead.

## Progress
- Completed Task 6: one comparison framework for OpenAI, Anthropic, Databricks and NVIDIA built from the Task 4 and Task 5 tables (`src/compare.py`): skill categories, common and distinctive skills, role mix, hiring velocity, tech-stack patterns, seniority, similarity, strategic gaps and white space. Nine output tables, notebook and report, including how OpenAI compares.
- Snapshots continued Mon/Thu. NVIDIA was not collected on 20 and 23 Nov (HTTP 429 on its robots.txt check, not retried by rule).

## Decisions
- Compare open roles only (describes demand today); check against Task 4's all-postings shares (within 3 points).
- Snapshot flows are the primary velocity signal; NVIDIA stays flagged provisional.
- Seniority is reported but only the manager, director and intern rows are interpreted, because Anthropic and OpenAI rarely use "Senior" in titles.
- "Thin everywhere" only at skill-category level; thin role categories are small functions, not findings.

## Blockers
- NVIDIA has two usable snapshots (4 and 16 Nov); its robots.txt endpoint has returned HTTP 429 on the last two runs.
- The Task 5 report quotes 20 Nov figures; the refreshed tables have moved since (to be refreshed with the next report update).

## Next steps
- Decide how to handle the NVIDIA 429s (wait, or review the robots check for that endpoint).
- Start Task 7 forecasting on `weekly_postings.csv`.
- Keep snapshots running.
