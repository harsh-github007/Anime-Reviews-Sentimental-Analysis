"""Download this month's top anime and their reviews from MyAnimeList.

    python -m animesent scrape --top 10 --out data/reviews.csv

Two sources, tried in this order (--source auto):
  1. Jikan (https://jikan.moe), a public read-only API over MyAnimeList data. It asks
     clients to stay under 3 requests a second and 60 a minute. It fetches from
     MyAnimeList live, so slow responses and 504s are normal and are retried.
  2. MyAnimeList's own public pages (see mal_pages.py), when Jikan can't serve the
     chart or the reviews.

Writes:
  data/reviews.csv        one row per review: title, date, user, tag, text and more
  data/scrape_info.json   which anime were chosen and how many reviews each gave
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

from . import mal_pages

API = "https://api.jikan.moe/v4"
PAUSE = 1.2          # seconds between requests: 50 a minute, inside Jikan's limit
PER_PAGE = 20        # Jikan returns reviews 20 at a time
FIELDS = ["anime_id", "top_rank", "title", "date", "user", "tag", "score", "preliminary", "spoiler",
          "episodes_watched", "helpful", "text"]


def notice(level, msg):
    """Print a message; on GitHub Actions also raise it as an annotation, which shows on the run page."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level}::{msg}", flush=True)
    else:
        print(f"  {msg}", file=sys.stderr, flush=True)


def get(url, tries=8, opener=urllib.request.urlopen, sleep=time.sleep):
    """GET a Jikan endpoint as JSON, retrying rate limits, server errors and dropped connections."""
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "anime-review-sentiment"})
    for attempt in range(tries):
        last = attempt == tries - 1
        try:
            with opener(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if e.code in (429, 500, 502, 503, 504) and not last:
                wait = min(10 * (attempt + 1), 60) if e.code != 429 else 30 * (attempt + 1)
                print(f"  {e.code} on {url.split('/v4')[-1]}; retrying in {wait}s", file=sys.stderr, flush=True)
                sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            if last:
                raise
            wait = min(10 * (attempt + 1), 60)
            print(f"  {type(e).__name__} ({e}) on {url.split('/v4')[-1]}; retrying in {wait}s", file=sys.stderr, flush=True)
            sleep(wait)
    raise RuntimeError(f"gave up on {url}")


def top_anime(n=10, filter_="airing", get_json=None):
    """The n highest-scored anime on MyAnimeList's chart (by default, those airing now)."""
    get_json = get_json or get
    items = get_json(f"{API}/top/anime?filter={filter_}&limit={min(n, 25)}")["data"][:n]
    return [{"anime_id": a["mal_id"], "top_rank": i + 1, "title": a.get("title_english") or a["title"],
             "mal_title": a["title"], "score": a.get("score"), "members": a.get("members"),
             "season": " ".join(str(x) for x in (a.get("season"), a.get("year")) if x) or None}
            for i, a in enumerate(items)]


def to_row(anime, r):
    tags = r.get("tags") or []
    tag = " ".join(tags)
    if r.get("is_preliminary") and "preliminary" not in tag.lower():
        tag += " Preliminary"
    reactions = r.get("reactions") or {}
    return {
        "anime_id": anime["anime_id"], "top_rank": anime["top_rank"], "title": anime["title"],
        "date": (r.get("date") or "")[:10], "user": (r.get("user") or {}).get("username", ""),
        "tag": tag.strip(), "score": r.get("score"), "preliminary": bool(r.get("is_preliminary")),
        "spoiler": bool(r.get("is_spoiler")), "episodes_watched": r.get("episodes_watched"),
        "helpful": reactions.get("overall"), "text": r.get("review") or "",
    }


def reviews(anime, max_pages=25, get_json=None, pause=None, sleep=None):
    """All reviews of one anime, including preliminary ones and ones marked as spoilers, up to max_pages."""
    get_json, sleep = get_json or get, sleep or time.sleep
    pause = PAUSE if pause is None else pause
    rows = []
    for page in range(1, max_pages + 1):
        sleep(pause)
        try:
            r = get_json(f"{API}/anime/{anime['anime_id']}/reviews?page={page}&preliminary=true&spoilers=true")
        except Exception as e:  # noqa: BLE001 - keep the pages already fetched and move on
            notice("warning", f"{anime['title']}: stopped at review page {page} ({type(e).__name__}: {e}); kept {len(rows)} reviews")
            break
        rows += [to_row(anime, x) for x in r.get("data", [])]
        if not r.get("pagination", {}).get("has_next_page"):
            break
    return rows


def mal_row(anime, rv):
    tags = list(rv["tags"])
    if rv["preliminary"] and not any("preliminary" in t.lower() for t in tags):
        tags.append("Preliminary")
    return {"anime_id": anime["anime_id"], "top_rank": anime["top_rank"], "title": anime["title"],
            "date": rv["date"], "user": rv["user"], "tag": " ".join(tags), "score": rv["score"],
            "preliminary": rv["preliminary"], "spoiler": rv["spoiler"], "episodes_watched": rv["episodes_watched"],
            "helpful": None, "text": rv["text"]}


def reviews_mal(anime, max_pages=25, fetch_html=None, pause=None, sleep=None):
    """An anime's reviews read from MyAnimeList's review pages (20 a page)."""
    fetch_html, sleep = fetch_html or mal_pages.get_html, sleep or time.sleep
    pause = mal_pages.PAUSE if pause is None else pause
    rows = []
    for page in range(1, max_pages + 1):
        sleep(pause)
        try:
            html = fetch_html(mal_pages.reviews_url(anime["anime_id"], page))
        except mal_pages.Blocked:
            raise
        except Exception as e:  # noqa: BLE001 - keep what was fetched
            notice("warning", f"{anime['title']}: MyAnimeList page {page} failed ({type(e).__name__}: {e}); kept {len(rows)} reviews")
            break
        found = mal_pages.parse_reviews(html)
        if page == 1 and not found:
            notice("warning", f"{anime['title']}: no reviews recognised on MyAnimeList's page. {mal_pages.page_shape(html)}")
        rows += [mal_row(anime, rv) for rv in found]
        if len(found) < 20:
            break
    return rows


CANDIDATES = 50  # how far down the chart to look for shows with enough reviews (one chart page)


def scrape(top=10, filter_="airing", max_pages=5, out="data/reviews.csv", get_json=None, pause=None, sleep=None,
           source="auto", fetch_html=None, min_reviews=0):
    """The `top` highest-ranked anime on the chart that have at least `min_reviews` reviews, and their reviews.

    New and niche shows can sit high on the chart with only a handful of reviews, which is
    too few to say anything about, so the scraper walks down the chart past them.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fetch_html = fetch_html or mal_pages.get_html
    quick = get_json or partial(get, tries=3)   # probe Jikan without waiting minutes on an outage

    chosen, used = None, []
    if source in ("auto", "jikan"):
        try:
            chosen = top_anime(CANDIDATES, filter_, quick)
            used.append("Jikan chart")
        except Exception as e:  # noqa: BLE001
            if source == "jikan":
                raise
            notice("warning", f"Jikan couldn't serve the chart ({type(e).__name__}: {e}); reading MyAnimeList's chart page instead")
    if chosen is None:
        chosen = mal_pages.parse_top(fetch_html(mal_pages.top_url(filter_)), CANDIDATES)
        used.append("MyAnimeList chart page")
        if not chosen:
            raise RuntimeError("no anime recognised on MyAnimeList's chart page. " + mal_pages.page_shape(fetch_html(mal_pages.top_url(filter_))))
    print(f"Looking down MyAnimeList's {filter_} chart for {top} shows with at least {min_reviews} reviews:")

    use_mal = source == "mal"
    if source == "auto":
        try:  # one quick probe decides whether Jikan's review pages are working today
            quick(f"{API}/anime/{chosen[0]['anime_id']}/reviews?page=1&preliminary=true&spoilers=true")
        except Exception as e:  # noqa: BLE001
            notice("warning", f"Jikan couldn't serve reviews ({type(e).__name__}: {e}); reading MyAnimeList's review pages instead")
            use_mal = True
    used.append("MyAnimeList review pages" if use_mal else "Jikan reviews")

    rows, kept, skipped = [], [], []
    for a in chosen:
        got = reviews_mal(a, max_pages, fetch_html, pause, sleep) if use_mal else reviews(a, max_pages, get_json, pause, sleep)
        a["reviews"] = len(got)
        keep = len(got) >= min_reviews
        note = "" if keep else "  (too few, skipped)"
        print(f"  {a['top_rank']:>2}. {a['title'][:55]:<55} score {a['score']}  {len(got):>4} reviews{note}", flush=True)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            notice("notice", f"chart #{a['top_rank']} {a['title']} (MAL {a['score']}): {len(got)} reviews" + ("" if keep else ", skipped"))
        if not keep:
            skipped.append({"top_rank": a["top_rank"], "title": a["title"], "reviews": len(got)})
            continue
        kept.append(a)
        rows += got
        if len(kept) == top:
            break
    if not rows:
        raise RuntimeError(f"none of the top {len(chosen)} anime had {min_reviews} or more reviews")
    if len(kept) < top:
        notice("warning", f"only {len(kept)} of the top {len(chosen)} anime had {min_reviews} or more reviews")
    chosen = kept
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    info = {"scraped": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "MyAnimeList (" + ", ".join(used) + ")",
            "chart": f"top {filter_}", "min_reviews": min_reviews, "max_reviews_per_anime": max_pages * PER_PAGE,
            "reviews": len(rows), "anime": chosen, "skipped": skipped}
    (out.parent / "scrape_info.json").write_text(json.dumps(info, indent=2))
    print(f"Saved {len(rows):,} reviews to {out}")
    return rows, info


def main(argv=None):
    p = argparse.ArgumentParser(prog="animesent scrape", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--top", type=int, default=10, help="how many anime to take from the chart (default 10)")
    p.add_argument("--filter", default="airing", choices=["airing", "upcoming", "bypopularity", "favorite"],
                   help="which MyAnimeList chart: airing = the top-scored shows airing now (default)")
    p.add_argument("--max-pages", type=int, default=5, help="review pages per anime, newest first, 20 reviews each (default 5, so the latest 100)")
    p.add_argument("--min-reviews", type=int, default=0, help="skip shows with fewer reviews than this (default 0: keep the top 10 as they are)")
    p.add_argument("--out", default="data/reviews.csv")
    p.add_argument("--source", default="auto", choices=["auto", "jikan", "mal"],
                   help="auto = Jikan, falling back to MyAnimeList's own pages when Jikan can't reach it (default)")
    a = p.parse_args(argv)
    try:
        scrape(a.top, a.filter, a.max_pages, a.out, source=a.source, min_reviews=a.min_reviews)
    except Exception as err:  # noqa: BLE001 - report any failure in one readable line
        notice("error", f"Scrape stopped: {type(err).__name__}: {err}")
        sys.exit(1)
