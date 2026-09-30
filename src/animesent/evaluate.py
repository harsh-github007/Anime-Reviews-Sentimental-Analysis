"""Check each sentiment method against the reviewers' own verdicts.

Main task: tell a "Recommended" review from a "Not Recommended" one ("Mixed Feelings"
reviews are left out, since neither answer is right for them). A three-way test is
reported for the trained model.

Fairness rules:
- Folds are split by show (StratifiedGroupKFold on title), so a model is always tested
  on shows it never saw. Otherwise it could learn show names instead of sentiment.
- Off-the-shelf methods are scored twice: at the cut-off they are normally used with,
  and at a cut-off tuned on the training folds only.
- Confidence intervals resample whole shows (a cluster bootstrap), because reviews of
  the same show are not independent.
"""

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline

from .data import LABELS

SEED = 0


def folds(y, groups, k=5):
    return list(StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=SEED).split(np.zeros(len(y)), y, groups))


def summarise(y, pred):
    """Binary metrics where 1 = Recommended."""
    y, pred = np.asarray(y), np.asarray(pred)
    return {
        "balanced_accuracy": balanced_accuracy_score(y, pred),
        "macro_f1": f1_score(y, pred, average="macro"),
        "caught_negative": float(((pred == 0) & (y == 0)).sum() / max((y == 0).sum(), 1)),  # recall on Not Recommended
        "caught_positive": float(((pred == 1) & (y == 1)).sum() / max((y == 1).sum(), 1)),
        "called_positive": float(pred.mean()),
    }


def best_cut(score, y):
    """The cut-off that maximises balanced accuracy on training data."""
    qs = np.unique(np.quantile(score, np.linspace(0.01, 0.99, 197)))
    return max(qs, key=lambda c: balanced_accuracy_score(y, score > c))


def tuned_predictions(score, y, splits):
    pred = np.zeros(len(y), dtype=int)
    for tr, te in splits:
        pred[te] = score[te] > best_cut(score[tr], y[tr])
    return pred


def text_model():
    return make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_df=0.9, sublinear_tf=True, max_features=200_000, strip_accents="unicode"),
        LogisticRegression(C=4.0, class_weight="balanced", max_iter=3000),
    )


def trained_oof(texts, y, splits):
    """Out-of-fold predictions: each review is scored by a model that never saw its show."""
    texts = np.asarray(texts, dtype=object)
    classes = np.unique(y)
    proba = np.zeros((len(y), len(classes)))
    for tr, te in splits:
        m = text_model().fit(texts[tr], y[tr])
        proba[te] = m.predict_proba(texts[te])
    return classes, proba


def cluster_ci(y, values, groups, stat, reps=300, seed=SEED):
    """95% interval for stat(y, values) by resampling whole groups (shows)."""
    y, values, groups = np.asarray(y), np.asarray(values), np.asarray(groups)
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    index = {g: np.flatnonzero(groups == g) for g in uniq}
    out = []
    for _ in range(reps):
        pick = np.concatenate([index[g] for g in rng.choice(uniq, len(uniq))])
        if len(np.unique(y[pick])) < 2:
            continue
        out.append(stat(y[pick], values[pick]))
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))) if out else (np.nan, np.nan)


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (min(c - h, p), max(c + h, p))  # guard against rounding at 0% and 100%


def top_words(texts, y, n=15):
    """Words and phrases the trained model leans on most, fitted on all binary reviews."""
    m = text_model().fit(texts, y)
    vec, lr = m.named_steps["tfidfvectorizer"], m.named_steps["logisticregression"]
    names, coef = vec.get_feature_names_out(), lr.coef_[0]
    order = np.argsort(coef)
    return {"Recommended": [names[i] for i in order[::-1][:n]], "Not Recommended": [names[i] for i in order[:n]]}


def evaluate(df, scores, min_reviews=40, k=5):
    """df: output of data.load. scores: {method name: array aligned with df}.

    Returns a JSON-ready dict of results plus two tables for charts.
    """
    res = {"counts": df["label"].value_counts().reindex(LABELS, fill_value=0).astype(int).to_dict(),
           "reviews": int(len(df)), "titles": int(df["title"].nunique()),
           "median_words": {l: float(df.loc[df["label"] == l, "words"].median()) for l in LABELS if (df["label"] == l).any()}}

    # ------------------------------------------------ the original project's headline, re-checked
    tb = scores["TextBlob"]
    res["original"] = {
        "textblob_positive_share": float((tb > 0).mean()),
        "textblob_negative_share": float((tb < 0).mean()),
        "textblob_neutral_share": float((tb == 0).mean()),
        "actual_recommended_share": float((df["label"] == "Recommended").mean()),
        "not_recommended_called_positive": float((tb[df["label"].values == "Not Recommended"] > 0).mean())
        if (df["label"] == "Not Recommended").any() else None,
    }

    # ------------------------------------------------ binary task
    b = df["label"].isin(["Recommended", "Not Recommended"]).values
    bdf = df[b].reset_index(drop=True)
    y = (bdf["label"] == "Recommended").astype(int).values
    groups = bdf["title"].values
    splits = folds(y, groups, k)
    res["binary"] = {"n": int(len(y)), "recommended": int(y.sum()), "not_recommended": int((1 - y).sum())}

    methods, oof_scores = {}, {}
    for name, s in scores.items():
        s = np.asarray(s)[b]
        oof_scores[name] = s
        default = {"TextBlob": 0.0, "VADER": 0.05}.get(name, 0.5)
        auc = roc_auc_score(y, s)
        methods[name] = {
            "auc": auc, "auc_ci": cluster_ci(y, s, groups, roc_auc_score),
            "default_cut": default, "at_default": summarise(y, (s > default).astype(int)),
            "at_tuned": summarise(y, tuned_predictions(s, y, splits)),
        }

    classes, proba = trained_oof(bdf["text"].values, y, splits)
    p_rec = proba[:, list(classes).index(1)]
    oof_scores["Trained on verdicts"] = p_rec
    pred = (p_rec > 0.5).astype(int)
    methods["Trained on verdicts"] = {
        "auc": roc_auc_score(y, p_rec), "auc_ci": cluster_ci(y, p_rec, groups, roc_auc_score),
        "default_cut": 0.5, "at_default": summarise(y, pred), "at_tuned": summarise(y, tuned_predictions(p_rec, y, splits)),
    }
    for name, m in methods.items():
        pred_t = (oof_scores[name] > m["default_cut"]).astype(int)
        m["balanced_accuracy_ci"] = cluster_ci(y, pred_t, groups, balanced_accuracy_score)
    res["methods"] = methods
    res["best_method"] = max(methods, key=lambda n: methods[n]["auc"])

    # ------------------------------------------------ three-way task, trained model only
    y3 = df["label"].values
    s3 = folds(y3, df["title"].values, k)
    c3, p3 = trained_oof(df["text"].values, y3, s3)
    pred3 = c3[p3.argmax(1)]
    res["three_way"] = {
        "macro_f1": f1_score(y3, pred3, average="macro"),
        "balanced_accuracy": balanced_accuracy_score(y3, pred3),
        "labels": LABELS,
        "confusion": confusion_matrix(y3, pred3, labels=LABELS).tolist(),
    }

    # ------------------------------------------------ by show
    rows = []
    titles = df["title"].values
    for title, g in df.groupby("title"):
        if len(g) < min_reviews:
            continue
        n = len(g)
        rec = int((g["label"] == "Recommended").sum())
        neg = int((g["label"] == "Not Recommended").sum())
        lo, hi = wilson(rec, n)
        here = titles == title
        rows.append({"title": title, "reviews": n, "recommended": rec / n, "rec_low": lo, "rec_high": hi,
                     "not_recommended": neg / n, "textblob_positive": float((tb[here] > 0).mean()),
                     "model_recommended": float((pred3[here] == "Recommended").mean())})
    by_title = pd.DataFrame(rows).sort_values("recommended", ascending=False).reset_index(drop=True)
    if len(by_title) >= 3:
        res["by_title"] = {
            "titles": int(len(by_title)), "min_reviews": min_reviews,
            "rank_corr_textblob": float(by_title["recommended"].corr(by_title["textblob_positive"], method="spearman")),
            "rank_corr_model": float(by_title["recommended"].corr(by_title["model_recommended"], method="spearman")),
        }

    res["top_words"] = top_words(bdf["text"].values, y)
    dist = pd.DataFrame({"label": df["label"].values, **{f"score_{k}": np.asarray(v) for k, v in scores.items()}})
    return res, by_title, dist
