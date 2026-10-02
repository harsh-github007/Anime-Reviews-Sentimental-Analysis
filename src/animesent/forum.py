"""Resumable AniList forum sampling; maximum 5,000 unique comments per anime."""
import argparse
import os
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from html import unescape
import re

API = "https://graphql.anilist.co"

def query(document, variables):
    for attempt in range(6):
        response = subprocess.run(["curl", "--silent", "--show-error", "--max-time", "60", API,
            "-H", "Content-Type: application/json", "--data-binary", json.dumps({"query": document, "variables": variables})], capture_output=True, text=True)
        try:
            payload = json.loads(response.stdout)
            if response.returncode == 0 and payload.get("data") and not payload.get("errors"):
                time.sleep(2.2)
                return payload["data"]
            error = payload.get("errors", payload)
        except ValueError:
            error = response.stderr or response.stdout[:200]
        time.sleep(min(60, 4 * 2 ** attempt))
    raise RuntimeError(f"AniList request failed: {error}")

def flatten(comments):
    for comment in comments or []:
        yield comment
        yield from flatten(comment.get("childComments"))

def collect(media_id, limit, state, request=query):
    rows = {r["id"]: r for r in state.get("comments", [])}
    page = state.get("thread_page", 1)
    while len(rows) < limit and page <= 100:
        data = request("query($id:Int,$page:Int){Page(page:$page,perPage:50){pageInfo{hasNextPage} threads(mediaCategoryId:$id,sort:ID_DESC){id title siteUrl}}}", {"id":media_id,"page":page})["Page"]
        for thread in data["threads"]:
            cp = 1
            while len(rows) < limit and cp <= 100:
                batch = request("query($id:Int,$page:Int){Page(page:$page,perPage:50){pageInfo{hasNextPage} threadComments(threadId:$id,sort:ID){id comment createdAt childComments}}}", {"id":thread["id"],"page":cp})["Page"]
                for c in flatten(batch["threadComments"]):
                    text = unescape(re.sub(r"<[^>]+>", " ", c.get("comment") or "")).strip()
                    if text and c["id"] not in rows and len(rows) < limit:
                        rows[c["id"]] = {"id":c["id"],"text":text,"createdAt":c.get("createdAt"),"thread_id":thread["id"],"thread_title":thread["title"],"url":thread["siteUrl"]}
                state["comments"] = list(rows.values())
                yield state
                if not batch["pageInfo"]["hasNextPage"]: break
                cp += 1
            if len(rows) >= limit: break
        if not data["pageInfo"]["hasNextPage"]:
            state["complete"] = True
            yield state
            break
        page += 1
        state["thread_page"] = page
    if len(rows) >= limit:
        state["complete"] = True
        yield state

def collect_mal(anime_id, limit, state, client_id, request=None):
    """Discover anime-linked MAL topics with Jikan; read posts via MAL API."""
    if request is None:
        import requests
        def request(url, authenticated=False):
            headers = {"X-MAL-CLIENT-ID": client_id} if authenticated else {}
            for attempt in range(5):
                response = requests.get(url, headers=headers, timeout=60)
                if response.status_code in (401, 403):
                    raise RuntimeError(f"MAL access refused ({response.status_code}); check Client ID")
                if response.status_code == 429 or response.status_code >= 500:
                    time.sleep(5 * 2 ** attempt); continue
                response.raise_for_status()
                time.sleep(3)
                return response.json()
            raise RuntimeError("Forum service unavailable after retries")
    rows = {r["id"]:r for r in state.get("comments", [])}
    if "topics" not in state:
        state["topics"] = request(f"https://api.jikan.moe/v4/anime/{anime_id}/forum")["data"]
    for topic in state["topics"]:
        if len(rows) >= limit: break
        tid = topic["mal_id"]
        if tid in state.get("finished_topics", []): continue
        offset = 0
        while len(rows) < limit:
            batch = request(f"https://api.myanimelist.net/v2/forum/topic/{tid}?limit=100&offset={offset}", True)
            data = batch["data"]
            if isinstance(data, list): data = data[0] if data else {"posts":[]}
            posts = data["posts"]
            for post in posts:
                text = unescape(re.sub(r"<[^>]+>|\[/?[^\]]+\]", " ", post.get("body", ""))).strip()
                if text and post["id"] not in rows and len(rows) < limit:
                    rows[post["id"]] = {"id":post["id"], "text":text,"source":"MyAnimeList", "thread_id":tid, "url":f"https://myanimelist.net/forum/?topicid={tid}","createdAt":post.get("created_at")}
            state["comments"] = list(rows.values())
            yield state
            if not batch.get("paging", {}).get("next"):
                state.setdefault("finished_topics", []).append(tid)
                break
            if not posts: raise RuntimeError("MAL returned an empty page with further pagination")
            offset += len(posts)
    state["complete"] = True
    yield state


def public_html(url):
    response = subprocess.run(["curl", "--silent", "--show-error", "--max-time", "60", "-A", "anime-review-sentiment/2.0 (research project)", "-w", "\n%{http_code}", url], capture_output=True, text=True)
    body, _, code = response.stdout.rpartition("\n")
    if response.returncode or code != "200":
        raise RuntimeError(f"MAL public page unavailable (HTTP {code}); collection stopped")
    time.sleep(3)
    return body

def collect_mal_public(anime_id, limit, state, fetch=public_html):
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse, parse_qs
    rows = {r["id"]:r for r in state.get("comments", [])}
    if "topics" not in state:
        soup = BeautifulSoup(fetch(f"https://myanimelist.net/anime/{anime_id}/_/forum"), "html.parser")
        topics = {}
        for a in soup.select('td[class^="forum_boardrow"] a[href*="topicid="]'):
            href = a.get("href", "")
            if "goto=" in href: continue
            query = parse_qs(urlparse(href).query)
            if "topicid" in query:
                tid = int(query["topicid"][0]); topics[tid] = {"mal_id":tid}
        if not topics and not soup.select('td[class^="forum_boardrow"]'):
            text = soup.get_text(" ",strip=True).lower()
            if not any(marker in text for marker in ("no topics", "no forum", "no discussion", "no posts")):
                raise RuntimeError("MAL forum listing could not be recognised; not treated as zero comments")
        state["topics"] = list(topics.values())
    for topic in state["topics"]:
        tid = topic["mal_id"]
        if len(rows) >= limit: break
        if tid in state.get("finished_topics", []): continue
        url = f"https://myanimelist.net/forum/?topicid={tid}"
        seen_pages = set()
        while url and len(rows) < limit:
            if url in seen_pages: raise RuntimeError("Repeated MAL pagination URL")
            seen_pages.add(url)
            soup = BeautifulSoup(fetch(url), "html.parser")
            posts = soup.select('.forum-topic-message[id^="msg"]')
            if not posts: raise RuntimeError("MAL post markup unavailable; not treated as an empty topic")
            for post in posts:
                body = post.select_one('table.body')
                if body is None: raise RuntimeError("MAL post body markup changed")
                for quote in body.select('blockquote, .quote'): quote.decompose()
                text = body.get_text(" ", strip=True)
                pid = int(post["id"][3:])
                if text and pid not in rows and len(rows) < limit:
                    rows[pid] = {"id":pid,"text":text,"source":"MyAnimeList", "thread_id":tid,"url":url}
            state["comments"] = list(rows.values())
            yield state
            next_link = soup.select_one('a[rel="next"]')
            if next_link is None:
                next_link = next((a for a in soup.select('a[href*="show="]') if a.get_text(strip=True) in ("Next", "Next »", "Next →", "»")), None)
            url = urljoin("https://myanimelist.net",next_link["href"]) if next_link else None
            if url and urlparse(url).hostname != "myanimelist.net": raise RuntimeError("Unexpected pagination host")
        if len(rows) < limit: state.setdefault("finished_topics",[]).append(tid)
    state["complete"] = True
    yield state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--sources", choices=["anilist", "both"], default="both")
    parser.add_argument("--min-comments", type=int, default=100, help="flag smaller samples; never silently replace titles")
    parser.add_argument("--titles", default="results/anime.json")
    parser.add_argument("--data", default="data/forum")
    parser.add_argument("--out", default="results/forum.json")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 5000: parser.error("--limit must be between 1 and 5000")
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()
    folder = Path(args.data); folder.mkdir(parents=True, exist_ok=True)
    titles = json.loads(Path(args.titles).read_text())["anime"]
    summary = {"source":"Forum discussions (see per-title source coverage)", "limit_per_anime":args.limit,"model":"VADER", "labels":"Predicted sentiment; no human ground-truth labels", "anime":[]}
    for title in titles:
        file = folder / f"{title['anime_id']}.json"
        state = json.loads(file.read_text()) if file.exists() else {"comments":[]}
        try:
            if not state.get("media_id"):
                media = query("query($id:Int){Media(idMal:$id,type:ANIME){id title{romaji}}}", {"id":title["anime_id"]})["Media"]
                state["media_id"] = media["id"]
            if not state.get("complete") or len(state["comments"]) < args.limit and state.get("limit",0) < args.limit:
                state["complete"] = False
                for state in collect(state["media_id"], args.limit, state):
                    state["limit"] = args.limit
                    file.write_text(json.dumps(state, ensure_ascii=False))
            state.pop("error", None)
        except Exception as error:
            state["error"] = str(error)
        file.write_text(json.dumps(state, ensure_ascii=False))
        mal_file = folder / f"{title['anime_id']}-mal.json"
        mal_state = json.loads(mal_file.read_text()) if mal_file.exists() else {"comments":[]}
        remaining = args.limit - len(state["comments"][:args.limit])
        mal_status = "not requested"
        if args.sources == "both" and remaining > 0:
            client_id = os.environ.get("MAL_CLIENT_ID", "")
            try:
                if not mal_state.get("complete") or mal_state.get("limit", 0) < remaining:
                    collector = collect_mal(title["anime_id"], remaining, mal_state, client_id) if client_id else collect_mal_public(title["anime_id"], remaining, mal_state)
                    for mal_state in collector:
                        mal_state["limit"] = remaining
                        mal_file.write_text(json.dumps(mal_state, ensure_ascii=False))
                mal_state.pop("error", None)
                mal_status = "complete"
            except Exception as error:
                mal_state["error"] = str(error)
                mal_status = str(error)
            mal_file.write_text(json.dumps(mal_state, ensure_ascii=False))
        elif remaining == 0:
            mal_status = "combined cap reached"
        combined = state["comments"][:args.limit] + mal_state["comments"][:remaining]
        source_counts = {"AniList":len(state["comments"][:args.limit]),"MyAnimeList":len(mal_state["comments"][:remaining])}
        counts = {"Positive":0,"Neutral":0,"Negative":0}
        for comment in combined:
            score = analyzer.polarity_scores(comment["text"])["compound"]
            counts["Positive" if score >= .05 else "Negative" if score <= -.05 else "Neutral"] += 1
        summary["anime"].append({"title":title["title"],"anime_id":title["anime_id"],"comments":sum(counts.values()),"counts":counts,"complete":state.get("complete",False) and (args.sources == "anilist" or mal_status in ("complete", "combined cap reached")),"error":state.get("error") or mal_state.get("error"),"source_counts":source_counts,"source_status":{"AniList":"complete" if state.get("complete") else "incomplete","MyAnimeList":mal_status},"sample_status":"no discussions found" if not combined else "small sample" if len(combined) < args.min_comments else "sufficient sample"})
        summary["updated"] = datetime.now(timezone.utc).isoformat()
        Path(args.out).parent.mkdir(parents=True,exist_ok=True)
        Path(args.out).write_text(json.dumps(summary,indent=2,ensure_ascii=False))
        print(f"{title['title']}: {sum(counts.values())} comments",flush=True)

if __name__ == "__main__": main()
