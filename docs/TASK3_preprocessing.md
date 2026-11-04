# Task 3: NLP Preprocessing & Method Selection

**Project:** Competitor Demand Prediction Using Job Postings (CadetX)
**Author:** Abdul-Haque Mohammed (individual track)
**Date:** 4 November 2026

## 1. Summary

`src/preprocess.py` turns the raw descriptions from Task 2 into clean, comparable text for all four companies. The main finding: **24-49% of every description is boilerplate** (legal text, benefits, "about us"), and the amount differs by company. Left in, it would create fake skill signals and make some companies look far richer in skills than others. After cleaning, the four companies sit at a similar length and quality level, which is what the brief asks for so comparisons are fair.

Walkthrough with outputs: `notebooks/03_preprocessing.ipynb`.

## 2. Workflow

| Step | What | Why |
|---|---|---|
| 1. Normalise | Unicode NFKC, straight quotes, remove zero-width characters, URLs and `[..._REMOVED]` tokens, collapse all whitespace | The three sources arrive in different shapes (Ashby plain text with line breaks, Greenhouse and Workday HTML). This puts them in one shape |
| 2. Boilerplate, frequency pass | Remove any sentence found in **10% or more** of that company's postings (digits replaced first, so dates don't make copies look different) | Data-driven, works the same for every company, and adapts if a company changes its template |
| 3. Boilerplate, phrase pass | Remove sentences with phrases that only appear in boilerplate ("equal opportunity", "background check", "rolling basis") | Catches reworded versions that each fall under 10% (NVIDIA rewords its blurb) |
| 4. Language flag | `is_english`: mostly basic-Latin letters **and** under 2% common French/German/Spanish words | Non-English text would produce nonsense "skills" in Task 4 |
| 5. NLP text | Lowercase, tokenise (keeps `c++`, `node.js`, `ci/cd`, `gpt-4` whole), remove stopwords, lemmatise (`models` → `model`) | Input for TF-IDF and similarity in Tasks 6 and 8 |
| 6. Seniority | `seniority_level` from the job title (intern, junior, mid, senior, staff, principal, lead, manager, director, executive) | Recommended field in the brief; needed for role comparisons |
| 7. Duplicates | `description_hash` and `duplicate_count` for postings with identical cleaned text | The same role is often posted once per city |

**Two text outputs, because later tasks need different things:**
- `cleaned_description`: case and symbols kept. For Task 4 skill matching, where "AWS", "Go" and "C++" must match exactly.
- `nlp_text`: lowercased, tokenised, stopwords removed, lemmatised. For TF-IDF and similarity.

**Libraries:** pandas, scikit-learn (stopword list), simplemma (lemmatiser, no model download needed), Python's `re`.

## 3. Choosing the 10% threshold

I checked which sentences repeat across each company's postings. Everything at or above 10% was boilerplate or a section header. Real role content starts at around 8% (e.g. Databricks' shared architect duties, which genuinely belong to a role family). Across all four companies, only **one technical sentence** was above 10%: NVIDIA's blurb that its "GPU acts as the brains of computers". That one should go, otherwise "GPU" appears in 20% of NVIDIA roles purely from the company blurb.

## 4. Result: comparable quality

| Company | Postings | Median chars before | Median chars after | Text removed | Median tokens | Non-English |
|---|---|---|---|---|---|---|
| Anthropic | 682 | 8,001 | 4,065 | 49% | 359 | 12 |
| Databricks | 926 | 5,368 | 3,194 | 41% | 283 | 2 |
| NVIDIA | 2,755 | 3,742 | 2,831 | 24% | 253 | 0 |
| OpenAI | 818 | 6,546 | 3,986 | 39% | 348 | 0 |

Before cleaning, Anthropic's descriptions were more than twice NVIDIA's length. After cleaning the gap is much smaller, and no posting ended up empty. Full table: `docs/preprocessing_stats.csv`.

**Checks that boilerplate is gone without losing content:**

| Text | Raw | Clean |
|---|---|---|
| "GPT-3" in Anthropic postings (from company blurb) | 100% | 0% |
| "Background checks" in OpenAI postings | 100% | 0% |
| "most desirable employers" in NVIDIA postings | 57% | 0% |
| "Spark" in Databricks postings (real skill) | 32% | 32% |
| "Python" in OpenAI postings (real skill) | 27% | 27% |

## 5. Problems found and fixed

| Problem | Fix |
|---|---|
| The lemmatiser wrecked short tech words: **AI → "be"**, **ML → "millileter"**, **AWS → "aw"** | Lemmatise only words of 5+ letters; 4-letter words only lose a plural "s" (`gpus` → `gpu`); 3 letters or fewer left alone |
| "Product Manager", "Account Manager" counted as management level | Excluded job-type titles from `manager` |
| 12 Anthropic Paris roles have an English title but a French description, so a script-only language check missed them | Added the foreign-word check |
| Short boilerplate ("Come work with us!") was too short to be counted | Lowered the minimum sentence length to 10 characters |
| Requisition codes (`SLSQ327R309`) treated as words | Tokens with 4+ digits removed |

## 6. Outputs

| File | Contents | In GitHub? |
|---|---|---|
| `data/interim/jobs_clean.csv` | All postings with the new columns | No (still copyrighted text) |
| `data/sample/jobs_clean_sample.csv` | 20 rows per company, text cut to 300 characters | Yes |
| `docs/preprocessing_stats.csv` | Quality metrics per company | Yes |
| `notebooks/03_preprocessing.ipynb` | Step-by-step walkthrough | Yes |

Preprocessing now runs automatically after every snapshot (`scripts/run_snapshot.sh`).

## 7. Limitations

- **The 10% threshold is recalculated every run.** If a company posts very few roles of one type, a sentence shared by that whole team could cross 10% and be removed. Checked on the current data (no technical content removed apart from NVIDIA's blurb), but worth re-checking as the data grows.
- **Rule-based seniority.** About 30-50% of titles contain no level word and default to `mid`. Some companies (e.g. Anthropic) rarely use "Senior" at all, so seniority comparisons between companies need care.
- **Duplicates are flagged, not removed.** Counting them as one role or several is a Task 5 decision.
- **Lemmatising is skipped for words under 5 letters,** so a few short plurals (e.g. "logs") stay as they are.
