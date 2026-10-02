# Forum collection and access

The saved aggregates can be explored without collecting new comments. Collection support does not establish permission to scrape.

AniList's [API terms](https://anilist.gitbook.io/anilist-apiv2-docs/docs/guide/terms-of-use) prohibit mass collection and note leniency for purely educational work. That wording is not an unconditional grant for this project's 5,000-per-title collection. MyAnimeList's [terms](https://myanimelist.net/about/terms_of_use) could not be retrieved for verification during this update. Confirm permission and applicable limits before starting either collector; do not treat public accessibility, throttling or an API key as permission.

## Forum discussion pipeline

[Analyse saved Drive comments in Colab](https://colab.research.google.com/github/harsh-github007/Anime-Reviews-Sentimental-Analysis/blob/main/notebooks/analyze_drive_comments.ipynb) — uses your existing JSON checkpoints; no new collection required.

Collect a separate AniList and MyAnimeList discussion dataset, capped at **5,000 unique comments per anime**:

```bash
python -m animesent forum --limit 5000
```

Uses the titles in `results/anime.json`, maps MAL IDs to AniList IDs, paginates associated threads and comments, and includes nested replies. Requires `curl` and the existing Python dependencies. Checkpoints in `data/forum/` let you resume the command. Aggregate predictions go to `results/forum.json`, which powers the new Discussions section. Actual counts may be below the cap. Per-title errors are reported, and partial data is retained. Raw comment text stays in local checkpoints; the frontend only displays aggregates.

VADER sentiment predictions use ±0.05 cut-offs. These comments have no verified recommendation labels and are excluded from review-model accuracy evaluation. Thread associations can include broader discussions, and VADER is primarily an English-language model.

[Run the forum collection in Colab](https://colab.research.google.com/github/harsh-github007/Anime-Reviews-Sentimental-Analysis/blob/main/notebooks/run_forum.ipynb). CPU is sufficient. The notebook supports Google Drive checkpoints and downloads aggregate results.

### Broader forum coverage

The forum command now defaults to `--sources both`. No API key is required for public-page collection. Optionally set `MAL_CLIENT_ID` privately to use the official MAL API; Jikan then discovers anime-linked topics. If either service is unavailable, checkpoints and existing AniList results survive, and per-source status reports the limitation. The combined cap remains 5,000, with AniList sampled first. Posts are deduplicated by ID within each source; cross-platform copies are not detected.

`--min-comments 100` flags small samples without replacing your chosen titles. Zero-result titles display “No discussions found in collected sources.” Changing the target title list is explicit through `--titles`; no titles are silently substituted.

Without `MAL_CLIENT_ID`, the collector reads public MAL forum pages directly, with a three-second pause and explicit errors for blocked or changed markup. This requires no account setup. Public discovery uses topics shown on the anime forum listing; it is not a guarantee of every historical thread.
