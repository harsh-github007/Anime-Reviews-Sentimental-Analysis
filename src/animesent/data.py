"""Load the scraped MyAnimeList reviews and attach the reviewer's own verdict as the label.

MyAnimeList asks every reviewer to tag their review "Recommended", "Mixed Feelings" or
"Not Recommended". That tag is the ground truth: it is the reviewer's own summary of
their review, so any automatic sentiment method can be checked against it.
"""

import hashlib
import re
from pathlib import Path

import pandas as pd

LABELS = ["Recommended", "Mixed Feelings", "Not Recommended"]

# Column names as the scraper exported them, and the names used here.
RENAME = {
    "s.no": "row", "title": "title", "date": "date", "date of comment": "date",
    "user": "user", "user name": "user", "tag": "tag", "text": "text",
}


def verdict(tag):
    """Map a scraped tag cell to one of LABELS, or None if it carries no verdict.

    The cell can hold more than the verdict (for example "Recommended Preliminary
    (3/12 eps)"), so this looks for the phrases rather than matching exactly.
    "Not Recommended" is checked first because it contains "Recommended".
    """
    if not isinstance(tag, str):
        return None
    t = tag.lower()
    if "not recommended" in t:
        return "Not Recommended"
    if "mixed" in t:
        return "Mixed Feelings"
    if "recommended" in t:
        return "Recommended"
    return None


def preliminary(tag):
    """MyAnimeList marks reviews written before the reviewer finished the show."""
    return isinstance(tag, str) and "preliminary" in tag.lower()


def clean_text(text):
    """Collapse whitespace and drop the page furniture the scraper can pick up."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"\b(read more|show less|helpful|reviewer's rating:?\s*\d+)\b", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def anonymise(user):
    """Replace a username with a short one-way hash, so reviewers can't be identified."""
    return hashlib.sha256(str(user).encode("utf-8")).hexdigest()[:12]


def load(path):
    """Read the scraped file (xlsx or csv) into one clean table with a `label` column.

    Returns (df, info) where info counts what was dropped and why.
    """
    path = Path(path)
    raw = pd.read_excel(path) if path.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(path)
    df = raw.rename(columns={c: RENAME.get(str(c).strip().lower(), str(c).strip().lower()) for c in raw.columns})
    missing = {"title", "tag", "text"} - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} has no {', '.join(sorted(missing))} column. Columns found: {', '.join(map(str, raw.columns))}")

    info = {"rows": len(df)}
    df["text"] = df["text"].map(clean_text)
    df["label"] = df["tag"].map(verdict)
    df["preliminary"] = df["tag"].map(preliminary)
    info["unknown_tag"] = int(df["label"].isna().sum())
    info["unknown_tag_examples"] = df.loc[df["label"].isna(), "tag"].dropna().astype(str).unique()[:5].tolist()
    info["empty_text"] = int((df["text"].str.len() == 0).sum())
    df = df[df["label"].notna() & (df["text"].str.len() > 0)]
    before = len(df)
    df = df.drop_duplicates(subset=["title", "text"])
    info["duplicates"] = before - len(df)
    if "user" in df.columns:
        df["user"] = df["user"].map(anonymise)
    df["words"] = df["text"].str.split().str.len()
    df = df.reset_index(drop=True)
    info["kept"] = len(df)
    return df, info
