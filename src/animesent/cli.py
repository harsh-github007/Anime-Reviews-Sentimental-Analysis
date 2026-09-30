"""python -m animesent --data "Anime Reviews.xlsx" [--transformer]

Loads the reviews, scores them with each method, checks every method against the
reviewers' own verdicts, and writes results/ (charts, tables, results.md).
"""

import argparse
import sys
import time

from . import methods
from .data import load
from .evaluate import evaluate
from .report import report


def main(argv=None):
    p = argparse.ArgumentParser(prog="animesent", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", required=True, help="the scraped reviews, .xlsx or .csv")
    p.add_argument("--out", default="results")
    p.add_argument("--transformer", action="store_true", help="also score with SiEBERT (needs transformers + torch; use a GPU)")
    p.add_argument("--min-reviews", type=int, default=40, help="shows with fewer reviews are left out of the by-show table")
    a = p.parse_args(argv)

    try:
        df, info = load(a.data)
    except (OSError, ValueError) as err:
        sys.exit(f"Stopped: {err}")
    print(f"Loaded {info['kept']:,} reviews ({info['unknown_tag']:,} without a verdict tag, {info['duplicates']:,} duplicates dropped).")
    if info["unknown_tag"]:
        print(f"  Tags not recognised, e.g.: {info['unknown_tag_examples']}")
    if df["label"].nunique() < 3 or (df["label"] == "Not Recommended").sum() < 20:
        sys.exit("Stopped: the Tag column doesn't hold enough Recommended / Mixed Feelings / Not Recommended verdicts to test against.")

    scores = {}
    for name, (fn, _) in methods.OFF_THE_SHELF.items():
        t = time.time()
        scores[name] = fn(df["text"].tolist())
        print(f"Scored with {name} in {time.time() - t:.0f}s")
    if a.transformer:
        t = time.time()
        scores["SiEBERT (transformer)"] = methods.transformer(df["text"].tolist())
        print(f"Scored with SiEBERT in {time.time() - t:.0f}s")

    print("Evaluating (cross-validation by show)…")
    res, by_title, dist = evaluate(df, scores, min_reviews=a.min_reviews)
    report(res, info, by_title, dist, a.out)
    print(f"Best method: {res['best_method']}. See {a.out}/results.md")


if __name__ == "__main__":
    main()
