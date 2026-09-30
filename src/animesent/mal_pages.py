"""Read MyAnimeList's public pages directly, for when the Jikan API can't reach MyAnimeList.

Used for two pages, both allowed for general crawlers by MyAnimeList's robots.txt:
  https://myanimelist.net/topanime.php?type=airing           the top airing chart
  https://myanimelist.net/anime/{id}/_/reviews?p={page}      an anime's reviews, 20 a page

Requests identify this project in their User-Agent and are spaced several seconds apart.
If MyAnimeList refuses the request (403), the scraper stops rather than trying to get around it.
"""

import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

from bs4 import BeautifulSoup

BASE = "https://myanimelist.net"
PAUSE = 3.0  # seconds between page requests
USER_AGENT = "anime-review-sentiment/2.0 (research project; +https://github.com/harsh-github007/Anime-Reviews-Sentimental-Analysis)"


class Blocked(RuntimeError):
    """MyAnimeList refused the request."""


def get_html(url, tries=5, opener=urllib.request.urlopen, sleep=time.sleep):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html", "Accept-Language": "en"})
    for attempt in range(tries):
        last = attempt == tries - 1
        try:
            with opener(req, timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise Blocked(f"MyAnimeList refused the request (403) for {url}") from e
            if e.code == 404:
                raise
            if e.code in (429, 500, 502, 503, 504) and not last:
                wait = 30 * (attempt + 1) if e.code == 429 else 10 * (attempt + 1)
                print(f"  {e.code} from MyAnimeList; retrying in {wait}s", file=sys.stderr, flush=True)
                sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if last:
                raise
            print(f"  {type(e).__name__} from MyAnimeList; retrying in {10 * (attempt + 1)}s", file=sys.stderr, flush=True)
            sleep(10 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}")


def top_url(filter_="airing"):
    return f"{BASE}/topanime.php" + ("" if filter_ in ("", None, "all") else f"?type={filter_}")


def reviews_url(anime_id, page):
    return f"{BASE}/anime/{anime_id}/_/reviews?sort=suggested&preliminary=on&spoiler=on&p={page}"


def _num(text):
    m = re.search(r"\d[\d,]*\.?\d*", text or "")
    return None if not m else float(m.group().replace(",", ""))


def parse_top(html, n=10):
    """The chart rows: rank order, MAL id, title, score, members."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for row in soup.select("tr.ranking-list"):
        link = row.select_one("h3 a[href*='/anime/']") or row.select_one("a[href*='/anime/']")
        if not link:
            continue
        m = re.search(r"/anime/(\d+)", link["href"])
        score = row.select_one("td.score .score-label") or row.select_one("td.score")
        info = row.select_one(".information")
        members = re.search(r"([\d,]+)\s+members", info.get_text(" ") if info else "")
        title = link.get_text(" ", strip=True)
        out.append({"anime_id": int(m.group(1)), "top_rank": len(out) + 1, "title": title, "mal_title": title,
                    "score": _num(score.get_text()) if score else None,
                    "members": int(members.group(1).replace(",", "")) if members else None, "season": None})
        if len(out) == n:
            break
    return out


def _date(text):
    text = (text or "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%b %d, %Y %I:%M %p"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return text


def parse_reviews(html):
    """Each review on the page as a dict: user, date, tags, score, preliminary, spoiler, episodes, text."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for el in soup.select("div.review-element"):
        user = el.select_one(".username a") or el.select_one("a[href*='/profile/']")
        date = el.select_one(".update_at")
        tag_els = el.select(".tags .tag")
        tags, classes = [], set()
        for t in tag_els:
            classes.update(c.lower() for c in t.get("class", []))
            label = next((s for s in t.stripped_strings), "")
            if label:
                tags.append(label)
        if not any(re.search(r"recommended|mixed", t, re.I) for t in tags):
            # fall back to the tag's CSS class when its text is missing
            for cls, label in (("not-recommended", "Not Recommended"), ("mixed-feelings", "Mixed Feelings"), ("recommended", "Recommended")):
                if cls in classes:
                    tags.insert(0, label)
                    break
        text_el = el.select_one(".text")
        if text_el:
            for junk in text_el.select("a, button, .js-toggle-review-button, .btn-toggle-review"):
                if re.fullmatch(r"\s*(read more|show less|\.\.\.)\s*", junk.get_text(" "), re.I):
                    junk.decompose()
        text = text_el.get_text(" ", strip=True) if text_el else ""
        rating_el = el.select_one(".rating .num") or el.select_one(".rating")
        score = _num(rating_el.get_text()) if rating_el else None
        if score is None:
            m = re.search(r"Reviewer.s Rating:\s*(\d+)", el.get_text(" "))
            score = float(m.group(1)) if m else None
        all_tags = " ".join(t.get_text(" ", strip=True) for t in tag_els)
        eps = re.search(r"\((\d+)\s*/\s*\d+\s*eps?\)", all_tags, re.I)
        out.append({
            "user": user.get_text(strip=True) if user else "",
            "date": _date(date.get_text(" ", strip=True) if date else ""),
            "tags": tags,
            "score": int(score) if score is not None else None,
            "preliminary": "preliminary" in classes or bool(re.search(r"preliminary", all_tags, re.I)),
            "spoiler": "spoiler" in classes or bool(re.search(r"spoiler", all_tags, re.I)),
            "episodes_watched": int(eps.group(1)) if eps else None,
            "text": text,
        })
    return out


def page_shape(html):
    """Counts of the elements the parser looks for, to diagnose a layout change without saving any content."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True)[:80] if soup.title else ""
    counts = {sel: len(soup.select(sel)) for sel in ("div.review-element", ".tags .tag", ".text", ".rating", ".update_at",
                                                     ".username", "tr.ranking-list")}
    challenge = bool(re.search(r"cf-chl|challenge-platform|Just a moment", html))
    return f"title='{title}' challenge={challenge} " + " ".join(f"{k}={v}" for k, v in counts.items())
