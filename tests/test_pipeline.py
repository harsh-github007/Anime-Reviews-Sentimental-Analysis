import json

import numpy as np
import pandas as pd
import pytest

from animesent import methods
from animesent.cli import main
from animesent.data import anonymise, clean_text, load, verdict
from animesent.evaluate import best_cut, evaluate, summarise, wilson
from animesent.report import report

GOOD = ["masterpiece", "loved", "stunning animation", "brilliant writing", "emotional ending", "rewatch it"]
BAD = ["boring", "waste of time", "dropped it", "terrible pacing", "lazy writing", "cheap fanservice"]
# Negative reviews still praise parts of a show, which is what fools word-counting scorers.
PRAISE = ["the art is beautiful", "great voice acting", "the first episode was good", "nice soundtrack"]


def make_reviews(n_titles=24, per_title=60, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for t in range(n_titles):
        p_rec = 0.35 + 0.6 * t / (n_titles - 1)  # shows range from mostly panned to mostly loved
        for i in range(per_title):
            u = rng.random()
            tag = "Recommended" if u < p_rec else ("Mixed Feelings" if u < p_rec + (1 - p_rec) / 2 else "Not Recommended")
            if tag == "Recommended":
                words = list(rng.choice(GOOD, 3)) + list(rng.choice(PRAISE, 1))
            elif tag == "Not Recommended":
                words = list(rng.choice(BAD, 3)) + list(rng.choice(PRAISE, 2))
            else:
                words = list(rng.choice(GOOD, 2)) + list(rng.choice(BAD, 2))
            rng.shuffle(words)
            rows.append({"S.no": len(rows) + 1, "Title": f"Show {t:02d}", "Date": "Feb 8, 2023", "User": f"user{i}",
                         "Tag": tag + (" Preliminary (3/12 eps)" if i % 17 == 0 else ""),
                         "text": f"Review {i} of show {t}. " + ". ".join(words) + "."})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ data

@pytest.mark.parametrize("tag,expected", [
    ("Recommended", "Recommended"),
    ("Not Recommended", "Not Recommended"),
    ("Mixed Feelings", "Mixed Feelings"),
    ("Recommended Preliminary (3/12 eps)", "Recommended"),
    ("not recommended  Spoiler", "Not Recommended"),
    ("Funny", None),
    (None, None),
])
def test_verdict(tag, expected):
    assert verdict(tag) == expected


def test_clean_text_removes_page_furniture():
    assert clean_text("Great show!\n\n  Read more   Reviewer's Rating: 9 ") == "Great show!"


def test_load_normalises_labels_anonymises_and_dedupes(tmp_path):
    df = make_reviews(n_titles=3, per_title=10)
    df = pd.concat([df, df.iloc[[0]], pd.DataFrame([{"Title": "X", "Tag": "Funny", "text": "hi"}])])
    df = df.rename(columns={"User": "User name"})
    path = tmp_path / "reviews.xlsx"
    df.to_excel(path, index=False)
    out, info = load(path)
    assert set(out["label"]) <= {"Recommended", "Mixed Feelings", "Not Recommended"}
    assert info["duplicates"] == 1 and info["unknown_tag"] == 1 and info["kept"] == 30
    assert out["user"].str.fullmatch(r"[0-9a-f]{12}").all()
    assert out["preliminary"].sum() == 3
    assert anonymise("user1") == anonymise("user1") != anonymise("user2")


def test_load_names_a_missing_column(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"Title": ["a"], "text": ["b"]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="tag"):
        load(path)


# ------------------------------------------------------------------ evaluation

def test_summarise_and_cut():
    m = summarise([1, 1, 0, 0], [1, 0, 0, 0])
    assert m["balanced_accuracy"] == 0.75 and m["caught_negative"] == 1.0 and m["called_positive"] == 0.25
    assert 0.1 <= best_cut(np.array([0.1, 0.2, 0.8, 0.9]), np.array([0, 0, 1, 1])) < 0.8


def test_wilson_interval():
    lo, hi = wilson(50, 100)
    assert lo < 0.5 < hi and hi - lo < 0.21


@pytest.fixture(scope="module")
def evaluated(tmp_path_factory):
    path = tmp_path_factory.mktemp("d") / "reviews.csv"
    make_reviews().to_csv(path, index=False)
    df, info = load(path)
    scores = {name: fn(df["text"].tolist()) for name, (fn, _) in methods.OFF_THE_SHELF.items()}
    res, by_title, dist = evaluate(df, scores, min_reviews=40)
    return df, info, res, by_title, dist


def test_textblob_is_fooled_and_training_fixes_it(evaluated):
    _, _, res, _, _ = evaluated
    # praise inside negative reviews makes TextBlob call many of them positive
    assert res["original"]["not_recommended_called_positive"] > 0.3
    trained = res["methods"]["Trained on verdicts"]
    assert trained["auc"] > 0.95
    assert trained["auc"] > res["methods"]["TextBlob"]["auc"]
    assert res["best_method"] == "Trained on verdicts"
    lo, hi = trained["auc_ci"]
    assert lo <= trained["auc"] <= hi
    assert res["three_way"]["macro_f1"] > 0.6


def test_by_show_tracks_the_true_ranking(evaluated):
    _, _, res, by_title, _ = evaluated
    assert len(by_title) == 24
    assert res["by_title"]["rank_corr_model"] > 0.7
    assert (by_title["rec_low"] <= by_title["recommended"]).all() and (by_title["recommended"] <= by_title["rec_high"]).all()


def test_report_contains_no_review_text_or_users(evaluated, tmp_path):
    df, info, res, by_title, dist = evaluated
    report(res, info, by_title, dist, tmp_path)
    for f in ("results.md", "metrics.json", "by_show.csv", "figures/methods.png", "figures/textblob_by_verdict.png", "figures/titles.png"):
        assert (tmp_path / f).exists(), f
    written = (tmp_path / "results.md").read_text() + (tmp_path / "metrics.json").read_text() + (tmp_path / "by_show.csv").read_text()
    assert "Review 3 of show" not in written
    assert not any(u in written for u in df["user"].unique()[:20])
    json.loads((tmp_path / "metrics.json").read_text())


def test_cli_end_to_end(tmp_path, capsys):
    path = tmp_path / "reviews.csv"
    make_reviews(n_titles=12, per_title=50, seed=1).to_csv(path, index=False)
    main(["--data", str(path), "--out", str(tmp_path / "out"), "--min-reviews", "30"])
    assert "Best method" in capsys.readouterr().out
    assert (tmp_path / "out" / "results.md").exists()


def test_cli_stops_without_verdicts(tmp_path):
    path = tmp_path / "reviews.csv"
    pd.DataFrame({"Title": ["a"] * 30, "Tag": ["Recommended"] * 30, "text": [f"t{i}" for i in range(30)]}).to_csv(path, index=False)
    with pytest.raises(SystemExit, match="verdicts"):
        main(["--data", str(path), "--out", str(tmp_path / "o")])
