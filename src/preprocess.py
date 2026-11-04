"""
Task 3: NLP preprocessing.

Reads  data/interim/jobs_master.csv  (from build_dataset.py)
Writes data/interim/jobs_clean.csv          (full cleaned text, git-ignored: still copyrighted)
       data/sample/jobs_clean_sample.csv    (20 rows per company, text cut to 300 chars, committed)
       docs/preprocessing_stats.csv         (quality metrics per company, committed)

Two text columns come out, for different jobs:
  cleaned_description  case kept, boilerplate removed  -> Task 4 skill matching ("AWS", "Go", "C++")
  nlp_text             lowercased, tokenised, stopwords removed, lemmatised -> TF-IDF / similarity (Tasks 6, 8)

Run:   python src/preprocess.py
"""
import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd
import simplemma
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

ROOT = Path(__file__).resolve().parents[1]
INTERIM, SAMPLE, DOCS = ROOT / "data/interim", ROOT / "data/sample", ROOT / "docs"

# A sentence that appears in at least this share of one company's postings is
# boilerplate (legal text, "about us", benefits, pay-range wording). Chosen by
# inspection: everything at or above 10% was boilerplate; real role content
# (e.g. Databricks templated architect duties) starts around 8%. See docs/TASK3.
BOILERPLATE_SHARE = 0.10
MIN_SENTENCE_CHARS = 10

# Short tech terms that look like stopwords or would be mangled. Never removed.
KEEP = {"go", "r", "c", "it", "ai", "ml", "ui", "ux", "ar", "vr", "qa", "bi", "os"}
CONTRACTIONS = {"ll", "ve", "re", "don", "doesn", "isn", "aren", "ca", "won", "didn", "wouldn", "shouldn"}
STOPWORDS = (set(ENGLISH_STOP_WORDS) | CONTRACTIONS) - KEEP

# Words that are common in French/German/Spanish/Portuguese but not English.
# Used to spot non-English postings written in the Latin alphabet.
FOREIGN = {"les", "des", "dans", "pour", "avec", "une", "nous", "vous", "est", "sur",
           "und", "der", "die", "mit", "für", "wir", "sie", "ist", "oder",
           "los", "las", "para", "con", "una", "del", "por", "nuestro",
           "com", "uma", "não", "são"}

URL = re.compile(r"https?://\S+|www\.\S+")
REDACTED = re.compile(r"\[(?:EMAIL|PHONE|NAME)_REMOVED\]")
SENTENCE = re.compile(r"(?<=[.!?])\s+")
# keeps c++, c#, node.js, ci/cd, gpt-4, k8s, .net as single tokens
TOKEN = re.compile(r"\.?[a-z][a-z0-9+#]*(?:[./\-][a-z0-9+#]+)*")


# ---------------------------------------------------------------- step 1: normalise

def normalise(text):
    """Same shape for every source: unicode normalised, URLs and redaction
    tokens gone, all whitespace (incl. Ashby's line breaks) collapsed to one space."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[​-‍﻿]", "", text)          # zero-width characters
    text = URL.sub(" ", text)
    text = REDACTED.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- step 2: boilerplate

def sentence_key(s):
    """Lowercase and replace digits so 'until November 3' and 'until November 17' match."""
    return re.sub(r"\d+", "#", s.lower())


def find_boilerplate(texts):
    """Sentences repeated across at least BOILERPLATE_SHARE of one company's postings."""
    counts = Counter()
    for t in texts:
        counts.update({sentence_key(s) for s in SENTENCE.split(t) if len(s) >= MIN_SENTENCE_CHARS})
    cutoff = BOILERPLATE_SHARE * len(texts)
    return {k for k, v in counts.items() if v >= cutoff}


# Second pass: phrases that only ever appear in hiring/legal boilerplate. Catches
# reworded variants that each fall under the 10% frequency cut-off (NVIDIA rewords
# its "about us" text across postings).
BOILER_PHRASES = re.compile(
    r"equal (employment )?opportunit|most desirable employers|come work with us|"
    r"rolling basis|reasonable accommodation|without regard to (race|age)|"
    r"nvidiabenefits|eligible for equity and benefits|we want to hear from you|"
    r"privacy (policy|notice)|background check|e-verify|pay transparency|"
    r"applications for this job will be accepted", re.I)


def strip_boilerplate(text, boiler):
    kept = [s for s in SENTENCE.split(text)
            if sentence_key(s) not in boiler and not BOILER_PHRASES.search(s)]
    return " ".join(kept).strip()


# ---------------------------------------------------------------- step 3: language

def is_english(text):
    """Two checks: mostly basic-Latin letters (catches Japanese etc.), and few
    common foreign words (catches French/German/Spanish, which use Latin letters)."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters or sum(ch.isascii() for ch in letters) / len(letters) < 0.9:
        return False
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    return sum(w in FOREIGN for w in words) / max(len(words), 1) < 0.02


# ---------------------------------------------------------------- step 4: tokens

NOT_PLURAL = {"plus", "thus", "news", "does", "bias", "chaos", "ios", "macos", "kudos", "devops", "aws"}


def lemma(t):
    """Lemmatise safely. The lemmatiser wrecks short tech words (ai -> be,
    ml -> millileter, aws -> aw), so: 5+ letters use the lemmatiser, 4 letters
    only lose a plural s (gpus -> gpu), 3 or fewer stay as they are."""
    if not t.isalpha() or len(t) <= 3:        # c++, node.js, gpt-4, ai, ml, aws
        return t
    if len(t) == 4:
        return t[:-1] if t.endswith("s") and not t.endswith(("ss", "is")) and t not in NOT_PLURAL else t
    return simplemma.lemmatize(t, lang="en").lower()


def to_nlp_text(text):
    out = []
    for t in TOKEN.findall(text.lower()):
        t = t.strip(".-/")
        if (not t or t in STOPWORDS or (len(t) == 1 and t not in KEEP)
                or sum(ch.isdigit() for ch in t) >= 4):   # requisition codes like slsq327r309
            continue
        t = lemma(t)
        if t not in STOPWORDS:                # lemma can become one (being -> be)
            out.append(t)
    return " ".join(out)


# ---------------------------------------------------------------- step 5: seniority

SENIORITY = [  # first match wins, so the most specific titles come first
    ("intern",    r"\bintern(ship)?\b|\bco-?op\b|\bstudent\b"),
    ("executive", r"\b(chief|vp|vice president|head of|svp|evp|cto|ceo|cfo)\b"),
    ("director",  r"\bdirector\b"),
    # "Product Manager", "Account Manager" etc. are job types, not management level
    ("manager",   r"(?<!product )(?<!program )(?<!project )(?<!account )(?<!partner )(?<!success )"
                  r"(?<!solutions )(?<!territory )(?<!marketing )(?<!community )\bmanager\b|\bmgr\b|"
                  r"\bengineering manager\b|\bmanager,"),
    ("principal", r"\bprincipal\b|\bdistinguished\b|\bfellow\b"),
    ("staff",     r"\bstaff\b"),
    ("lead",      r"\blead\b"),
    ("senior",    r"\bsenior\b|\bsr\.?\b|\bsnr\b|\biii\b|\biv\b"),
    ("junior",    r"\bjunior\b|\bjr\.?\b|\bassociate\b|\bentry\b|\bnew grad|\bgraduate\b|\bi\b"),
]

def seniority(title):
    t = str(title).lower()
    for level, pattern in SENIORITY:
        if re.search(pattern, t):
            return level
    return "mid"   # no level word in the title


# ---------------------------------------------------------------- main

def main():
    df = pd.read_csv(INTERIM / "jobs_master.csv")
    df["_norm"] = df["job_description"].map(normalise)

    parts, boiler_sizes = [], {}
    for company, g in df.groupby("company_name"):
        boiler = find_boilerplate(g["_norm"])
        boiler_sizes[company] = len(boiler)
        g = g.copy()
        g["cleaned_description"] = g["_norm"].map(lambda t: strip_boilerplate(t, boiler))
        parts.append(g)
    df = pd.concat(parts).sort_index()

    df["is_english"] = df["cleaned_description"].map(is_english)
    df["nlp_text"] = df["cleaned_description"].map(to_nlp_text)
    df["seniority_level"] = df["job_title"].map(seniority)
    df["job_title_clean"] = df["job_title"].map(normalise)

    # identical cleaned text = same job posted under several requisitions/locations.
    # Flagged, not dropped: Task 5 decides whether to count each requisition or not.
    df["description_hash"] = df["cleaned_description"].map(
        lambda t: hashlib.md5(t.encode()).hexdigest()[:12])
    df["duplicate_count"] = df.groupby(["company_name", "description_hash"])["job_id"].transform("size")

    df["chars_raw"] = df["_norm"].str.len()
    df["chars_clean"] = df["cleaned_description"].str.len()
    df["tokens"] = df["nlp_text"].str.split().str.len()
    df = df.drop(columns="_norm")

    df.to_csv(INTERIM / "jobs_clean.csv", index=False)

    sample = df.groupby("company_name").head(20).copy()
    for col in ["job_description", "cleaned_description", "nlp_text"]:
        sample[col] = sample[col].str[:300] + "..."
    SAMPLE.mkdir(parents=True, exist_ok=True)
    sample.to_csv(SAMPLE / "jobs_clean_sample.csv", index=False)

    # quality metrics: the evidence that all four companies end up at the same level
    stats = df.groupby("company_name").agg(
        postings=("job_id", "size"),
        boilerplate_sentences_found=("company_name", lambda s: boiler_sizes[s.iloc[0]]),
        median_chars_before=("chars_raw", "median"),
        median_chars_after=("chars_clean", "median"),
        median_tokens=("tokens", "median"),
        non_english=("is_english", lambda s: int((~s).sum())),
        empty_after_cleaning=("chars_clean", lambda s: int((s < 200).sum())),
        in_duplicate_groups=("duplicate_count", lambda s: int((s > 1).sum())),
    )
    stats["pct_text_removed"] = (100 * (1 - stats.median_chars_after / stats.median_chars_before)).round(1)
    stats.to_csv(DOCS / "preprocessing_stats.csv")
    print(stats.to_string())
    print("\nSeniority:\n", pd.crosstab(df.company_name, df.seniority_level).to_string())


if __name__ == "__main__":
    main()
