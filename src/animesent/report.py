"""Charts and results/results.md. Only aggregate numbers are written: no review text or usernames."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e4df"
COLOUR = {"Recommended": "#2a78d6", "Mixed Feelings": "#8b8a85", "Not Recommended": "#eb6834"}
BLUE, ORANGE = "#2a78d6", "#eb6834"


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.set_axisbelow(True)


def pct(x, d=0):
    return "–" if x is None or x != x else f"{100 * x:.{d}f}%"


def chart_methods(res, path):
    names = list(res["methods"])
    auc = [res["methods"][n]["auc"] for n in names]
    lo = [res["methods"][n]["auc_ci"][0] for n in names]
    hi = [res["methods"][n]["auc_ci"][1] for n in names]
    ba = [res["methods"][n]["at_default"]["balanced_accuracy"] for n in names]
    y = np.arange(len(names))[::-1]

    fig, axes = plt.subplots(1, 2, figsize=(10, 0.7 * len(names) + 1.6), sharey=True)
    for ax, vals, ends, title in ((axes[0], auc, hi, "Separates the two verdicts (ROC AUC)"),
                                  (axes[1], ba, ba, "Balanced accuracy at its usual cut-off")):
        ax.barh(y, vals, height=0.5, color=BLUE)
        ax.axvline(0.5, color=MUTED, lw=1, ls="--")
        ax.set_xlim(0.4, 1.08)
        ax.set_xticks([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.grid(axis="x", color=GRID, lw=0.8)
        for yi, v, e in zip(y, vals, ends):
            ax.text(max(v, e) + 0.012, yi, f"{v:.2f}", va="center", fontsize=9, color=INK)
        _style(ax)
    axes[0].errorbar(auc, y, xerr=[np.subtract(auc, lo), np.subtract(hi, auc)], fmt="none", ecolor=INK, lw=1, capsize=3)
    axes[0].set_yticks(y, names)
    axes[0].text(0.5, -0.9, "0.5 = coin toss", fontsize=8, color=MUTED, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_textblob(dist, path):
    labels = [l for l in COLOUR if (dist["label"] == l).any()]
    fig, axes = plt.subplots(len(labels), 1, figsize=(8, 1.5 * len(labels) + 0.8), sharex=True)
    axes = np.atleast_1d(axes)
    bins = np.linspace(-0.6, 0.6, 49)
    for ax, lab in zip(axes, labels):
        s = dist.loc[dist["label"] == lab, "score_TextBlob"].clip(-0.6, 0.6)
        ax.hist(s, bins=bins, color=COLOUR[lab], edgecolor="white", linewidth=0.5)
        ax.axvline(0, color=INK, lw=1)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        share = (s > 0).mean()
        ax.text(0.01, 0.8, f"{lab}  ·  {pct(share)} scored positive", transform=ax.transAxes, fontsize=9, color=INK)
        _style(ax)
    axes[-1].set_xlabel("TextBlob polarity (right of the line counts as positive)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_titles(by_title, path, n=15):
    t = by_title.sort_values("reviews", ascending=False).head(n).sort_values("recommended")
    y = np.arange(len(t))
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(t) + 1.4))
    ax.errorbar(t["recommended"], y, xerr=[t["recommended"] - t["rec_low"], t["rec_high"] - t["recommended"]],
                fmt="o", color=BLUE, ms=6, lw=1.2, capsize=0, label="Reviewers who recommend it (95% interval)")
    ax.scatter(t["textblob_positive"], y, marker="|", s=120, color=ORANGE, lw=2, label="Reviews TextBlob calls positive", zorder=3)
    ax.set_yticks(y, [s if len(s) <= 40 else s[:38] + "…" for s in t["title"]])
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.legend(loc="lower left", fontsize=8, frameon=False, bbox_to_anchor=(0, 1.0), ncol=2)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_markdown(res, info, by_title, out):
    o, m, b = res["original"], res["methods"], res["binary"]
    best = res["best_method"]
    lines = [
        "# Results", "",
        f"{res['reviews']:,} reviews of {res['titles']:,} shows, each tagged by its author as "
        + ", ".join(f"{k} ({v:,})" for k, v in res["counts"].items()) + ".",
        f"Dropped before analysis: {info.get('unknown_tag', 0):,} with no verdict tag, {info.get('empty_text', 0):,} empty, "
        f"{info.get('duplicates', 0):,} duplicates.", "",
        "## What TextBlob says", "",
        f"TextBlob calls {pct(o['textblob_positive_share'], 1)} of reviews positive. "
        f"The reviewers themselves recommend {pct(o['actual_recommended_share'], 1)} of the shows they review, "
        f"and TextBlob scores {pct(o['not_recommended_called_positive'])} of **Not Recommended** reviews as positive.", "",
        "![TextBlob polarity by verdict](figures/textblob_by_verdict.png)", "",
        "## How well each method matches the verdict", "",
        f"Recommended vs Not Recommended: {b['n']:,} reviews ({b['recommended']:,} vs {b['not_recommended']:,}). "
        "Five-fold cross-validation split by show, so every review is scored by a model that never saw that show. "
        "Balanced accuracy averages the hit rate on each verdict, so always answering \"Recommended\" scores 50%.", "",
        "| Method | ROC AUC (95% CI) | Balanced accuracy, usual cut-off | Balanced accuracy, tuned cut-off | Not Recommended caught |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, r in m.items():
        lines.append(f"| {name} | {r['auc']:.2f} ({r['auc_ci'][0]:.2f}–{r['auc_ci'][1]:.2f}) | {pct(r['at_default']['balanced_accuracy'])} | "
                     f"{pct(r['at_tuned']['balanced_accuracy'])} | {pct(r['at_default']['caught_negative'])} |")
    lines += ["", f"Best at separating the verdicts: **{best}**.", "", "![Methods](figures/methods.png)", ""]

    t3 = res["three_way"]
    lines += ["## Three verdicts", "",
              f"Trained on all three tags, the model reaches a macro F1 of {t3['macro_f1']:.2f} and balanced accuracy of {pct(t3['balanced_accuracy'])}. "
              "Rows are the reviewer's tag, columns the model's guess:", "",
              "| | " + " | ".join(t3["labels"]) + " |", "| --- |" + " ---: |" * len(t3["labels"])]
    for lab, row in zip(t3["labels"], t3["confusion"]):
        lines.append(f"| **{lab}** | " + " | ".join(f"{v:,}" for v in row) + " |")

    if "by_title" in res:
        bt = res["by_title"]
        lines += ["", "## By show", "",
                  f"Shows with at least {bt['min_reviews']} reviews ({bt['titles']}). Rank correlation with the share of reviewers who recommend the show: "
                  f"TextBlob {bt['rank_corr_textblob']:.2f}, trained model {bt['rank_corr_model']:.2f}.", "",
                  "![Shows](figures/titles.png)", "",
                  "| Show | Reviews | Recommended (95% CI) | Not Recommended | TextBlob positive |", "| --- | ---: | ---: | ---: | ---: |"]
        for _, r in by_title.iterrows():
            lines.append(f"| {r['title']} | {r['reviews']:,} | {pct(r['recommended'])} ({pct(r['rec_low'])}–{pct(r['rec_high'])}) | "
                         f"{pct(r['not_recommended'])} | {pct(r['textblob_positive'])} |")

    tw = res["top_words"]
    lines += ["", "## What the trained model listens to", "",
              "Words and phrases with the largest weights toward each verdict:", "",
              f"- **Recommended:** {', '.join(tw['Recommended'])}",
              f"- **Not Recommended:** {', '.join(tw['Not Recommended'])}", "",
              "## Caveats", "",
              "- One scrape of MyAnimeList in early 2023. Reviewers who write reviews are not all viewers, so these rates describe reviews, not audiences.",
              "- A tag is a single summary of a long, often mixed review; some disagreement with any method is expected.",
              "- Scores come from English text only; reviews in other languages were left as they are.", ""]
    (out / "results.md").write_text("\n".join(lines))


def report(res, info, by_title, dist, out="results"):
    out = Path(out)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    chart_methods(res, out / "figures" / "methods.png")
    chart_textblob(dist, out / "figures" / "textblob_by_verdict.png")
    if len(by_title) >= 3:
        chart_titles(by_title, out / "figures" / "titles.png")
    by_title.to_csv(out / "by_show.csv", index=False)
    (out / "metrics.json").write_text(json.dumps({"data": info, **res}, indent=2, default=float))
    write_markdown(res, info, by_title, out)
