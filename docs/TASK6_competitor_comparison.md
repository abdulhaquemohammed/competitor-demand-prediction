# Task 6: Competitor Comparison

**Project:** Competitor Demand Prediction Using Job Postings (CadetX)
**Author:** Abdul-Haque Mohammed (individual track)
**Date:** 23 November 2026 (snapshots to 23 Nov; tables refresh with every Mon/Thu snapshot)

## 1. Summary

`src/compare.py` compares OpenAI (main), Anthropic, Databricks and NVIDIA in **one shared framework**, applied identically to all four, using only the Task 4 and Task 5 tables. It covers skills, role categories, hiring velocity, tech-stack patterns, seniority and strategic gaps. Walkthrough with charts: `notebooks/06_comparison.ipynb`.

| | Skill lane | Hiring mix | Velocity (snapshot flows) |
|---|---|---|---|
| OpenAI | ML, go-to-market, security; few named tools | Balanced: Software Eng 27%, Solutions & Field 14%, Sales 12% | Open roles +4.3%, bucket high |
| Anthropic | ML and AI safety; closest to OpenAI | Balanced: Sales 22%, Software Eng 20% | Open roles -6.8%, medium |
| Databricks | Cloud, data engineering | Concentrated: Solutions & Field 39% | Open roles -3.5%, medium |
| NVIDIA | GPU, hardware, C++ | Software Eng 40%, Hardware 21% | Open roles -2.4%, low (provisional) |

## 2. Method

**Population.** Open roles (`job_status == active`): 852 OpenAI, 625 Anthropic, 892 Databricks, 2,690 NVIDIA. This describes demand today. Shares are per posting, as in Task 4 (one role posted in several cities counts per posting). Task 4's shares use every posting seen, so open-role shares differ by up to 1.9 points for skills and 2.7 for categories; `compare.py` checks both stay under 3.

| Dimension | Definition | Source |
|---|---|---|
| Skill categories | Share of open roles asking for at least one skill in the category | `job_skills.csv` |
| Common skill | At least 5% of open roles at every company | `skill_matrix.csv` |
| Distinctive skill | At least 5% at one company and at least 2x the mean of the other three | `skill_matrix.csv` |
| Role mix | Share of open roles per `role_category`; concentration = top-3 share and HHI | `job_skills.csv` |
| Velocity | Snapshot flows first (open-stock change, opened and closed per week, new-role rate as % of open roles, bucket). Posting-date growth second | `velocity_summary.csv`, `snapshot_flows.csv`, `weekly_postings.csv` |
| Role growth | Adjusted growth, last 8 vs previous 8 weeks, and its tercile bucket | `role_velocity.csv` |
| Tech stack | Share of open roles per skill group, from `tech_stack_tags` (no concept or business skills); cloud mix = share of cloud-tagged roles naming each provider | `job_skills.csv` |
| Seniority | Title-based level, grouped (see limitations) | `job_skills.csv` |
| Similarity | Cosine similarity of share vectors (skills, skill categories, role categories) | derived |
| Below peers | Share at most 0.5x the mean of the other three, where those three average at least 10% | derived |
| White space | Skill categories at or below 10% at all four; role categories or skills whose adjusted growth is positive at all four | `role_velocity.csv`, `emerging_skills.csv` |

Thresholds are fixed round numbers (constants at the top of `compare.py`), not tuned to give a particular count.

## 3. Validation

- Role shares sum to 1 per company; category shares lie in [0, 1]; all four companies appear in every table.
- Open-role skill and category shares agree with Task 4 within 3 points (largest 1.9 and 2.7).
- NVIDIA flows are marked provisional (`flows_provisional`): one 12-day interval, because its snapshots on 19, 20 and 23 Nov were not collected (read timeout, then HTTP 429, not retried by rule).
- I read the distinctive-skill lists. They match the Task 4 fingerprints: Databricks cloud and Spark, NVIDIA GPU, CUDA and HPC, Anthropic AI safety.

## 4. Outputs (`data/processed/`, all committed: no description text)

| File | What | Used in |
|---|---|---|
| `comparison_scorecard.csv` | One row per company, one column per headline metric (skills, role mix, tech stack, seniority, velocity, similarity to OpenAI, gap count) | Tasks 8, 9, 10 |
| `comparison_skills.csv` | Long: company x skill: `postings`, `share`, `others_mean_share`, `rank`, `scope` (common, distinctive, other) | Tasks 8, 9 |
| `comparison_categories.csv` | Long: company x skill category: `share`, `others_mean`, `gap_pp` (points vs the other three) | Tasks 8, 9 |
| `comparison_roles.csv` | Long: company x role category: `share`, `open_roles`, `gap_pp`, `new_roles_per_week_last8`, `growth_pct_adjusted`, `growth_bucket` | Tasks 7, 9 |
| `comparison_tech_stack.csv` | Long: company x tech group or cloud provider (`kind`): `postings`, `share_of_open`, `share_of_tech_roles`, `share_of_cloud_roles`, `top_tags` | Tasks 8, 9 |
| `comparison_velocity.csv` | One row per company: flows, churn, new-role rate, bucket, posting-date growth, `flows_provisional`, `growth_confidence` | Tasks 7, 9 |
| `comparison_similarity.csv` | Long: company pair x view: cosine similarity | Task 8 |
| `distinctive_skills.csv` | Skills one company asks for at least 2x more than the others, with `ratio_to_others` | Task 9 |
| `strategic_gaps.csv` | `gap_type` (below_peers, white_space_thin, white_space_all_growing) by item and company | Task 9 |

`share` is a fraction of that company's open roles (0.3 = 30%). `gap_pp` is the company's share minus the mean of the other three, in percentage points. The tables join to Task 5 on `company_name`.

## 5. How OpenAI compares

| Dimension | OpenAI | Against the other three |
|---|---|---|
| Top skills | Go-to-market 30%, Python 26%, AI agents 17%, observability 16%, distributed systems 15% | Few named tools: 3.1 skills per role, against 3.9 (Anthropic), 6.3 (Databricks), 6.9 (NVIDIA) |
| Closest peer | Anthropic: skill similarity 0.85, role-mix similarity 0.93 | Databricks 0.56 and NVIDIA 0.54 on skills |
| Distinctive skills | 3: JavaScript 10%, evals 8%, incident response 8% | Anthropic has 6, Databricks 19, NVIDIA 27. Evals is shared with Anthropic |
| Role mix | Software Engineering 27%, Solutions & Field 14%, Sales & Partnerships 12%, Research 8% | Most balanced with Anthropic (concentration index 0.13, against 0.22 to 0.25) |
| Tech stack | DevOps and infrastructure 28% of roles; cloud 5%, data engineering 7%, GPU 6%, ML frameworks 1% | Databricks 45% cloud, NVIDIA 70% GPU and HPC |
| Seniority | 59% of titles carry no level word, 30% manager or lead, 7% director or executive (highest) | Title habits differ, so read only the manager and director rows |
| Velocity | Open roles 817 to 852 (+4.3%), 82.5 opened and 69.6 closed a week, new roles 9.6% of open roles a week (high) | Only company whose stock grew. Anthropic -6.8%, Databricks -3.5%, NVIDIA -2.4% (provisional) |
| Role growth (adjusted, 8 vs 8 weeks) | Up: Marketing & Comms +143%, Other +158%, Product & Design +96%, Corporate +94%, Security +59%, Data +56%. Down: Hardware -47%, Solutions & Field -31%, Software Engineering -30%, Research -29%, ML / AI Engineering -28% | The same split as Task 5: commercial and operational functions growing, technical ones not |

**Strategic gaps for OpenAI.** Below peers on Cloud (5% against 20%), Data Engineering (7% against 25%), GPU & HPC (6% against 27%) and Hardware (7% against 16%). It is above peers in Business & GTM (+5.5 points) and Security (+2.7). OpenAI asks for few named cloud providers (29 roles name the most-mentioned one), so the AWS, GCP and Azure gaps (13 to 16 points) mostly reflect that postings do not list platforms.

## 6. Key patterns

**Similarities.** Six skills are common to all four: Python, machine learning, LLMs, AI agents, observability and distributed systems. OpenAI and Anthropic are near twins in skill categories (cosine 0.97) and in the shape of their hiring mix.

**Differences.**
- **Anthropic** leans to research and safety: AI safety 11% (6.6x the others), reinforcement learning, evals, MCP. It has the highest ML and AI concept share (58%) and Security 17%.
- **Databricks** is a platform and sales business: Cloud 45%, Data Engineering 55%, Solutions & Field 39% of roles, all three clouds named in 38 to 44% of roles.
- **NVIDIA** is silicon and systems: GPU & HPC 70%, Hardware 45%, C++ and CUDA. Sales is only 4% of its roles.

**Velocity.** On the unbiased flows OpenAI is the only company growing its open stock and it has the highest new-role rate; Anthropic has the biggest net shrink (about -17 roles a week). Anthropic's adjusted posting-date growth (-34.5%) is low confidence: 9% of its open roles close each week, so the survival correction is large.

**White space.** Databases, ML Frameworks and Web & APIs are at or below 10% of roles at all four companies, mostly because postings rarely name them. Go-to-market is the only skill whose share is higher in recent postings at all four (x1.3 to x3.9, strongest at NVIDIA from a low base). No role category grows at all four.

## 7. Limitations

- **Mentioned is not required.** Shares count any mention of a skill (Task 4), so thin categories may be under-reported rather than absent.
- **Small cells.** The OpenAI cloud mix rests on 29 roles at most; role-growth percentages on a base of one or two roles a week swing widely. Read sign and rank.
- **NVIDIA flows are provisional.** One 12-day interval (4 to 16 Nov). Its posting-date growth also carries the bulk-repost handling described in Task 5.
- **Seniority is title-based.** "Mid" means no level word. Anthropic and OpenAI rarely write "Senior", so senior-level shares across companies are not comparable and are not interpreted.
- **Per-posting shares.** NVIDIA (181 open postings in duplicate groups) and Databricks (151) post the same role in several cities, which slightly inflates their shares against OpenAI (53) and Anthropic (23).
- **Rule-based role categories** (Task 4); about 9% of OpenAI's roles are "Other".
- **Gap thresholds are judgement.** The 2x, 0.5x, 5% and 10% cut-offs are fixed round numbers, so the lists change at the margin if they move.
- **Four companies only.** "Peers" means the other three of the set, not the market.
