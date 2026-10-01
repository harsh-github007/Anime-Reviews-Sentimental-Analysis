"""Resumable AniList forum sampling; maximum 5,000 unique comments per anime."""
import argparse
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

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--titles", default="results/anime.json")
    parser.add_argument("--data", default="data/forum")
    parser.add_argument("--out", default="results/forum.json")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 5000: parser.error("--limit must be between 1 and 5000")
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()
    folder = Path(args.data); folder.mkdir(parents=True, exist_ok=True)
    titles = json.loads(Path(args.titles).read_text())["anime"]
    summary = {"source":"AniList forum discussions", "limit_per_anime":args.limit,"model":"VADER", "labels":"Predicted sentiment; no human ground-truth labels", "anime":[]}
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
        counts = {"Positive":0,"Neutral":0,"Negative":0}
        for comment in state["comments"][:args.limit]:
            score = analyzer.polarity_scores(comment["text"])["compound"]
            counts["Positive" if score >= .05 else "Negative" if score <= -.05 else "Neutral"] += 1
        summary["anime"].append({"title":title["title"],"anime_id":title["anime_id"],"comments":sum(counts.values()),"counts":counts,"complete":state.get("complete",False),"error":state.get("error")})
        summary["updated"] = datetime.now(timezone.utc).isoformat()
        Path(args.out).parent.mkdir(parents=True,exist_ok=True)
        Path(args.out).write_text(json.dumps(summary,indent=2,ensure_ascii=False))
        print(f"{title['title']}: {sum(counts.values())} comments",flush=True)

if __name__ == "__main__": main()
