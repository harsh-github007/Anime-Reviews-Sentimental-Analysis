"""Download this month's top anime and their reviews from MyAnimeList, through the Jikan API.

    python -m animesent scrape --top 10 --out data/reviews.csv

Jikan (https://jikan.moe) is a public, read-only API over MyAnimeList data. It asks
clients to stay under 3 requests a second and 60 a minute, and it fetches from
MyAnimeList live, so slow responses and 504s are normal: every request is retried
with a growing wait.

Writes:
  data/reviews.csv        one row per review: title, date, user, tag, text and more
  data/scrape_info.json   which anime were chosen and how many reviews each gave
"""

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.jikan.moe/v4"
PAUSE = 1.2          # seconds between requests: 50 a minute, inside Jikan's limit
PER_PAGE = 20        # Jikan returns reviews 20 at a time
FIELDS = ["anime_id", "top_rank", "title", "date", "user", "tag", "score", "preliminary", "spoiler",
          "episodes_watched", "helpful", "text"]


def get(url, tries=6, opener=urllib.request.urlopen, sleep=time.sleep):
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
                wait = 5 * (attempt + 1) if e.code != 429 else 20 * (attempt + 1)
                print(f"  {e.code} on {url.split('/v4')[-1]}; retrying in {wait}s", file=sys.stderr)
                sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            if last:
                raise
            wait = 5 * (attempt + 1)
            print(f"  {type(e).__name__} on {url.split('/v4')[-1]}; retrying in {wait}s", file=sys.stderr)
            sleep(wait)
    raise RuntimeError(f"gave up on {url}")


def top_anime(n=10, filter_="airing", get_json=None):
    """The n highest-scored anime on MyAnimeList's chart (by default, those airing now)."""
    get_json = get_json or get
    items = get_json(f"{API}/top/anime?filter={filter_}&limit={n}")["data"][:n]
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
        r = get_json(f"{API}/anime/{anime['anime_id']}/reviews?page={page}&preliminary=true&spoilers=true")
        rows += [to_row(anime, x) for x in r.get("data", [])]
        if not r.get("pagination", {}).get("has_next_page"):
            break
    return rows


def scrape(top=10, filter_="airing", max_pages=25, out="data/reviews.csv", get_json=None, pause=None, sleep=None):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    chosen = top_anime(top, filter_, get_json)
    print(f"Top {len(chosen)} ({filter_}) on MyAnimeList:")
    rows = []
    for a in chosen:
        got = reviews(a, max_pages, get_json, pause, sleep)
        a["reviews"] = len(got)
        rows += got
        print(f"  {a['top_rank']:>2}. {a['title'][:55]:<55} score {a['score']}  {len(got):>4} reviews")
    if not rows:
        raise RuntimeError("no reviews were returned for any of the chosen anime")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    info = {"scraped": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "MyAnimeList via the Jikan API",
            "chart": f"top {filter_}", "reviews": len(rows), "anime": chosen}
    (out.parent / "scrape_info.json").write_text(json.dumps(info, indent=2))
    print(f"Saved {len(rows):,} reviews to {out}")
    return rows, info


def main(argv=None):
    p = argparse.ArgumentParser(prog="animesent scrape", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--top", type=int, default=10, help="how many anime to take from the chart (default 10)")
    p.add_argument("--filter", default="airing", choices=["airing", "upcoming", "bypopularity", "favorite"],
                   help="which MyAnimeList chart: airing = the top-scored shows airing now (default)")
    p.add_argument("--max-pages", type=int, default=25, help="review pages per anime, 20 reviews each (default 25)")
    p.add_argument("--out", default="data/reviews.csv")
    a = p.parse_args(argv)
    try:
        scrape(a.top, a.filter, a.max_pages, a.out)
    except (urllib.error.URLError, RuntimeError, KeyError) as err:
        sys.exit(f"Stopped: {err}")
