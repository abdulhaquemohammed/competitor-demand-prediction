# Task 4: Skill Extraction & Feature Engineering

**Project:** Competitor Demand Prediction Using Job Postings (CadetX)
**Author:** Abdul-Haque Mohammed (individual track)
**Date:** 4 November 2026

## 1. Summary

`src/extract_skills.py` finds skills in every English posting (5,167 of 5,182) using **one shared taxonomy** (`src/skill_taxonomy.py`) of **158 skills in 14 categories**, applied identically to all four companies. It also tags each role's category from its title, and builds the feature tables Tasks 5 to 8 need. Walkthrough with charts: `notebooks/04_skills.ipynb`.

## 2. Method

**Taxonomy.** I seeded it from the data: the most frequent tech-looking terms in the cleaned postings (acronyms, CamelCase, `C++`-style tokens), then grouped them into categories, including the brief's examples (Cloud, ML, DevOps). NVIDIA's postings needed hardware and networking categories that a generic list wouldn't have.

| Category | Examples |
|---|---|
| Programming Languages | Python, C++, Go, Rust, SQL |
| ML Frameworks | PyTorch, JAX, TensorFlow, Ray |
| ML & AI Concepts | LLMs, RAG, fine-tuning, AI agents, RLHF, evals |
| LLM & Inference Tools | vLLM, TensorRT, Triton, MCP, LangChain |
| Data Engineering & Analytics | Spark, Kafka, Airflow, Snowflake, ETL |
| Databases | PostgreSQL, Redis, MongoDB |
| Cloud | AWS, GCP, Azure |
| DevOps & Infrastructure | Kubernetes, Docker, Terraform, CI/CD, Linux |
| GPU & HPC | CUDA, GPU, NCCL, MPI, InfiniBand |
| Hardware & Semiconductor | ASIC, RTL, SystemVerilog, PCIe, FPGA |
| Networking | TCP/IP, RoCE, BGP |
| Security | IAM, cryptography, SOC 2 / FedRAMP |
| Web & APIs | React, Node.js, REST, gRPC |
| Business & GTM | Salesforce, MEDDPICC, go-to-market |

**Matching.** Each skill is a regex matched against `cleaned_description` from Task 3, so boilerplate can't create fake skills. Short or ambiguous words use exact-case and context rules. I chose regex over an ML model because every match can be explained, it needs no labelled training data, and identical rules for every company keep the comparison fair. Fine-tuning a model is the brief's optional extra task.

**Role category.** Keyword rules on the job title, checked in order so specific roles win ("Research Engineer" is Research, "Solutions Architect" is Solutions & Field). 13 categories plus Other.

## 3. Validation

I read samples of real matches for every ambiguous skill. False positives found and fixed:

| Skill | Wrong match | Fix |
|---|---|---|
| Product management | "roadmap" in almost every role (43% of Databricks) | Exact phrase only |
| AI safety / alignment | "cross-functional alignment" (27% of Anthropic) | AI/model/value alignment, Alignment team, AI safety |
| Excel | "excel at building relationships" | Not followed by at/in/as/when |
| Transformers | electrical transformers in NVIDIA power roles | Only in ML context (Hugging Face, transformer models) |
| Embedded systems | "embedded in the team" | Only embedded systems/software/firmware/Linux |
| Data (role) | NVIDIA "Data Center" roles | Excludes "data center" |

Checked and accurate: Go (vs go-to-market), R (vs R&D), C (only in C/C++ or language lists), Rust, Swift, Ray (not ray tracing), JAX, Triton, MPI, Git, Spark (Databricks writes "Spark™").

Postings with no skill found are mostly non-technical, as expected: Marketing 42%, Corporate 36%, Program & Ops 29%, but only 3-4% of Engineering and Research roles.

## 4. Feature tables (`data/processed/`, all committed: no description text)

| File | What | Used in |
|---|---|---|
| `job_skills.csv` | One row per posting: `extracted_skills`, `skill_categories`, `tech_stack_tags`, `role_category`, `seniority_level`, `n_skills` | Tasks 5-9 |
| `skill_matrix.csv` | One row per posting, one 0/1 column per skill (the brief's `skill_frequency_vector`) | Tasks 6, 8 |
| `skill_frequency.csv` | Per company and skill: postings, share, rank | Tasks 6, 9 |
| `category_share.csv` | Per company and category: share of postings | Task 6 |
| `skill_trends_monthly.csv` | Per company, month and skill: share of that month's postings (months with 20+ postings) | Task 5 |
| `emerging_skills.csv` | Recent (last 90 days) vs older share per skill, with `emerging_skill_flag` | Tasks 5, 9 |

`tech_stack_tags` is the skill list without concept and business skills, matching the brief's example (AWS, Python, Kubernetes).

## 5. First findings

| Company | Skill fingerprint (share of postings) |
|---|---|
| NVIDIA | GPU 58%, Python 43%, C++ 29%, deep learning 26%, HPC 25%. 70% need GPU/HPC skills, 44% hardware |
| Databricks | AWS 42%, Azure 41%, Python 40%, GCP 37%, Spark 32%. 56% need data engineering, 43% cloud |
| Anthropic | LLMs 37%, Python 30%, go-to-market 27%, ML 17%, AI agents 15%, AI safety 11% |
| OpenAI | Go-to-market 27%, Python 27%, distributed systems 16%, observability 16%, AI agents 15% |

Python is the only skill that's common at all four. **AI agents** is the most even (13-17% everywhere), which suggests a shared industry direction.

**Early emerging signals** (recent vs older postings): NVIDIA AI agents 8% → 18%, inference 9% → 15%, Kubernetes 8% → 13%. Databricks Salesforce 4% → 13%, Snowflake 2% → 13% (a competitor's product, likely migration or partner roles), MEDDPICC 4% → 8%, which points to a sales push.

## 6. Limitations

- **Survivorship bias** (Task 2) affects the emerging flags: older postings that already closed are missing. Treat them as early signals; they get more reliable as snapshots build up.
- **A dictionary only finds what's in it.** New tools not in the taxonomy are missed. Re-run the term-frequency check (notebook) every few weeks and add new terms.
- **Mentioned ≠ required.** "Nice to have" and "required" skills count the same.
- **Own-product bias.** NVIDIA's own products (CUDA, TensorRT, NeMo) naturally appear mostly in NVIDIA postings. Databricks naming "Databricks" is excluded as a self-mention.
- **Role categories are rule-based.** About 6% of titles stay "Other" (mostly regional heads and niche corporate roles).
