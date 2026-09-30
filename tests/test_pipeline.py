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


# ------------------------------------------------------------------ scraper (fake Jikan)

import io
import urllib.error

from animesent import scrape as sc


def fake_jikan(per_anime=45, fail_first=False):
    calls = {"n": 0}
    rng = np.random.default_rng(3)

    def get_json(url, **_):
        calls["n"] += 1
        if "/top/anime" in url:
            return {"data": [{"mal_id": 100 + i, "title": f"Show {i}", "title_english": None if i % 2 else f"Show {i} (EN)",
                              "score": 8.0 + i / 10, "members": 1000 * i, "season": "summer", "year": 2026} for i in range(12)]}
        anime_id = int(url.split("/anime/")[1].split("/")[0])
        page = int(url.split("page=")[1].split("&")[0])
        start, end = (page - 1) * 20, min(page * 20, per_anime)
        data = [{"mal_id": anime_id * 1000 + k, "date": "2026-09-01T10:00:00+00:00", "review": f"Review {k} of {anime_id}. " + ("loved it" if k % 3 else "boring"),
                 "score": int(rng.integers(1, 11)), "tags": ["Recommended"] if k % 3 else ["Not Recommended"],
                 "is_preliminary": k % 10 == 0, "is_spoiler": False, "episodes_watched": 12,
                 "reactions": {"overall": k}, "user": {"username": f"u{k}"}} for k in range(start, end)]
        return {"data": data, "pagination": {"has_next_page": end < per_anime, "last_visible_page": 3}}
    return get_json, calls


def test_scrape_takes_the_top_n_and_pages_through_reviews(tmp_path):
    get_json, calls = fake_jikan(per_anime=45)
    rows, info = sc.scrape(top=10, out=tmp_path / "reviews.csv", get_json=get_json, pause=0, sleep=lambda s: None)
    assert len(info["anime"]) == 10 and len(rows) == 10 * 45
    assert calls["n"] == 1 + 1 + 10 * 3  # the chart, one probe of the review endpoint, three pages per anime
    assert info["anime"][0]["title"] == "Show 0 (EN)" and info["anime"][1]["title"] == "Show 1"
    assert (tmp_path / "scrape_info.json").exists()
    df, load_info = load(tmp_path / "reviews.csv")  # the analysis reads the scraper's file as it is
    assert load_info["kept"] == 450 and set(df["label"]) == {"Recommended", "Not Recommended"}
    assert df["preliminary"].sum() == 10 * 5  # reviews 0, 10, 20, 30, 40 of each anime


def test_scrape_respects_the_page_cap(tmp_path):
    get_json, _ = fake_jikan(per_anime=100)
    rows, _ = sc.scrape(top=2, max_pages=2, out=tmp_path / "r.csv", get_json=get_json, pause=0, sleep=lambda s: None)
    assert len(rows) == 2 * 40


def test_get_retries_jikan_timeouts():
    calls = []

    def opener(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 504, "Gateway Timeout", {}, None)
        return io.BytesIO(b'{"data": []}')

    assert sc.get("https://api.jikan.moe/v4/x", opener=opener, sleep=lambda s: None) == {"data": []}
    assert len(calls) == 3


def test_get_does_not_retry_missing_pages():
    calls = []

    def opener(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        sc.get("https://api.jikan.moe/v4/x", opener=opener, sleep=lambda s: None)
    assert len(calls) == 1


def test_cli_scrape_subcommand(tmp_path, monkeypatch):
    get_json, _ = fake_jikan(per_anime=20)
    monkeypatch.setattr(sc, "get", get_json)
    monkeypatch.setattr(sc, "PAUSE", 0)
    monkeypatch.setattr(sc.time, "sleep", lambda s: None)
    main(["scrape", "--top", "3", "--out", str(tmp_path / "r.csv")])
    assert len(pd.read_csv(tmp_path / "r.csv")) == 60


# ------------------------------------------------------------------ MyAnimeList pages (fallback when Jikan is down)

from animesent import mal_pages

TOP_HTML = """<html><head><title>Top Airing Anime - MyAnimeList.net</title></head><body><table>
""" + "".join(f"""<tr class="ranking-list"><td class="rank">{i + 1}</td><td class="title">
<a class="hoverinfo_trigger" href="https://myanimelist.net/anime/{500 + i}/Show_{i}"><img></a>
<div class="detail"><h3 class="anime_ranking_h3"><a href="https://myanimelist.net/anime/{500 + i}/Show_{i}">Show {i}</a></h3>
<div class="information di-ib mt4">TV (12 eps)<br>Jul 2026 -<br>{(i + 1) * 1000:,} members</div></div></td>
<td class="score ac fs14"><div class="js-top-ranking-score-col di-ib al"><span class="text on score-label score-8">{9 - i / 10:.2f}</span></div></td></tr>""" for i in range(12)) + "</table></body></html>"


def review_html(n, verdicts=("recommended", "not-recommended", "mixed-feelings"), prelim_every=5):
    labels = {"recommended": "Recommended", "not-recommended": "Not Recommended", "mixed-feelings": "Mixed Feelings"}
    items = []
    for k in range(n):
        v = verdicts[k % len(verdicts)]
        prelim = f'<div class="tag preliminary">Preliminary<span>(3/12 eps)</span></div>' if k % prelim_every == 0 else ""
        items.append(f"""<div class="review-element js-review-element"><div class="thumbbody"><div class="body">
<div class="username"><a href="https://myanimelist.net/profile/user{k}">user{k}</a></div>
<div class="update_at">Sep {k % 28 + 1}, 2026</div>
<div class="tags"><div class="tag {v}">{labels[v]}</div>{prelim}</div>
<div class="text">Review number {k}. It was {"great" if v == "recommended" else "dull"}.<span class="js-visible">...</span>
<span class="js-hidden">More words here.</span> <a class="js-toggle-review-button">Read more</a></div>
<div class="rating mt20 mb20 js-hidden">Reviewer's Rating: <span class="num">{k % 10 + 1}</span></div>
</div></div></div>""")
    return "<html><head><title>Reviews - MyAnimeList.net</title></head><body>" + "".join(items) + "</body></html>"


def test_parse_top_chart():
    top = mal_pages.parse_top(TOP_HTML, 10)
    assert len(top) == 10 and top[0]["anime_id"] == 500 and top[0]["title"] == "Show 0"
    assert top[0]["score"] == 9.0 and top[2]["members"] == 3000 and top[9]["top_rank"] == 10


def test_parse_reviews_page():
    got = mal_pages.parse_reviews(review_html(6))
    assert len(got) == 6
    first = got[0]
    assert first["user"] == "user0" and first["date"] == "2026-09-01"
    assert first["tags"][0] == "Recommended" and first["preliminary"] and first["episodes_watched"] == 3
    assert first["score"] == 1 and "More words here." in first["text"] and "Read more" not in first["text"]
    assert [g["tags"][0] for g in got[:3]] == ["Recommended", "Not Recommended", "Mixed Feelings"]


def test_page_shape_reports_counts_not_content():
    shape = mal_pages.page_shape(review_html(3))
    assert "div.review-element=3" in shape and "Review number" not in shape


def test_scrape_falls_back_to_myanimelist_when_jikan_is_down(tmp_path):
    def jikan_down(url, **_):
        raise urllib.error.HTTPError(url, 504, "Gateway Time-out", {}, None)

    pages = {"n": 0}

    def fetch_html(url):
        pages["n"] += 1
        if "topanime.php" in url:
            return TOP_HTML
        page = int(url.split("p=")[1])
        return review_html(20 if page == 1 else 7)  # a full first page, then a short last page

    rows, info = sc.scrape(top=3, out=tmp_path / "r.csv", get_json=jikan_down, pause=0, sleep=lambda s: None, fetch_html=fetch_html)
    assert len(rows) == 3 * 27 and "MyAnimeList review pages" in info["source"]
    df, load_info = load(tmp_path / "r.csv")
    assert set(df["label"]) == {"Recommended", "Not Recommended", "Mixed Feelings"}


def test_scrape_stops_if_myanimelist_refuses(tmp_path):
    def jikan_down(url, **_):
        raise urllib.error.HTTPError(url, 504, "Gateway Time-out", {}, None)

    def refused(url):
        if "topanime.php" in url:
            return TOP_HTML
        raise mal_pages.Blocked("MyAnimeList refused the request (403)")

    with pytest.raises(mal_pages.Blocked):
        sc.scrape(top=2, out=tmp_path / "r.csv", get_json=jikan_down, pause=0, sleep=lambda s: None, fetch_html=refused)


def test_scrape_skips_shows_with_too_few_reviews(tmp_path):
    def get_json(url, **_):
        if "/top/anime" in url:
            return {"data": [{"mal_id": 100 + i, "title": f"Show {i}", "score": 9 - i / 10} for i in range(8)]}
        anime_id = int(url.split("/anime/")[1].split("/")[0])
        n = 3 if anime_id % 2 else 25  # odd ids have only 3 reviews
        page = int(url.split("page=")[1].split("&")[0])
        start, end = (page - 1) * 20, min(page * 20, n)
        data = [{"review": f"r{k}", "tags": ["Recommended"], "user": {"username": f"u{k}"}} for k in range(start, end)]
        return {"data": data, "pagination": {"has_next_page": end < n}}

    rows, info = sc.scrape(top=3, out=tmp_path / "r.csv", get_json=get_json, pause=0, sleep=lambda s: None, min_reviews=20)
    assert [a["title"] for a in info["anime"]] == ["Show 0", "Show 2", "Show 4"]
    assert [a["top_rank"] for a in info["anime"]] == [1, 3, 5]  # chart positions are kept
    assert [s["title"] for s in info["skipped"]] == ["Show 1", "Show 3"]
    assert len(rows) == 3 * 25
