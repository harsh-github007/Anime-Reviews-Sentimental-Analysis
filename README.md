# Sentiment in Anime Reviews: Checked Against the Reviewers' Own Verdicts

Can an automatic sentiment tool tell whether an anime review is positive? Every review on MyAnimeList carries the reviewer's own verdict: **Recommended**, **Mixed Feelings** or **Not Recommended**. This project downloads the reviews of the ten best-scored anime airing on MyAnimeList each month, uses those verdicts as ground truth, and measures how well common sentiment methods agree with them.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/harsh-github007/Anime-Reviews-Sentimental-Analysis/blob/main/notebooks/run_analysis.ipynb)

> **Results:** [`results/results.md`](results/results.md), refreshed on the 1st of every month.

## Interactive frontend

![Anime sentiment research frontend](assets/screenshot.png)

A cinematic cherry-blossom interface presents the saved Python analysis results, with:

- Reviewer verdict distributions and the gap between word polarity and recommendation.
- Searchable anime titles, a minimum-review filter, and accessible title detail dialogs.
- Model comparisons for balanced accuracy, negative-verdict recall, and ROC AUC, with default and training-fold-tuned thresholds.
- An explicit snapshot date, sample-size caveats, methodology, and links to the saved report and Colab notebook.
- Responsive layouts and reduced-motion support.

The frontend uses `results/metrics.json` and `results/anime.json` directly. It does not train models, run live inference, or collect review text. The existing Python pipeline and monthly workflow remain the source of the analysis. The current saved snapshot has 183 reviews across 9 reviewed titles; the selected chart contains 10 titles, one without collected reviews.

Run the website from the repository root:

```bash
python -m http.server 8000
# Open http://localhost:8000
```

No JavaScript dependencies or build step are required. The new Pages workflow publishes only the frontend assets and aggregate results on changes to main, and after successful monthly analysis. Set the repository’s GitHub Pages source to **GitHub Actions** to enable publishing.

The hero illustration is AI-generated artwork inspired by the supplied design reference. It is decorative and does not depict any anime in the dataset.

## Why it's hard

Reviews are long, and they rarely stay on one side. A review that ends "not recommended" often praises the art, the soundtrack or the first few episodes before explaining what went wrong. Methods that count positive and negative words see all that praise and call the review positive. The reviewer's verdict shows what they actually concluded.

## Method

1. **Download** ([`scrape.py`](src/animesent/scrape.py)).
   - Takes the top 10 of MyAnimeList's "top airing" chart, the best-scored shows currently on air.
   - Keeps each one's newest 100 reviews (`--limit` changes this), including preliminary reviews written before the show finished.
   - Uses [Jikan](https://jikan.moe), a public read-only API over MyAnimeList data, and stays under its limits (fewer than one request a second). Jikan fetches from MyAnimeList live and often times out, so every request is retried with a growing wait.
   - When Jikan can't reach MyAnimeList, it reads MyAnimeList's own chart and review pages instead ([`mal_pages.py`](src/animesent/mal_pages.py)). These pages are open to general crawlers under MyAnimeList's robots.txt. Requests name the project in their user agent and are spaced 3 seconds apart, and the scraper stops if MyAnimeList refuses them.
2. **Load** ([`data.py`](src/animesent/data.py)).
   - Each review's tag is mapped to its verdict. Tags such as "Recommended Preliminary (3/12 eps)" are read by the phrase they contain.
   - Reviews with no verdict, empty text or duplicate text are dropped, and page furniture such as "Read more" is removed.
   - Usernames are replaced with a one-way hash.
3. **Score** every review with three off-the-shelf methods that need no training ([`methods.py`](src/animesent/methods.py)):
   - **TextBlob**, a widely used scorer that averages the polarity of English words.
   - **VADER**, a rule-based scorer built for short social media text.
   - **SiEBERT** (optional, needs a GPU), a RoBERTa-large model fine-tuned on reviews. Reviews longer than its 512-token window are judged on their opening and closing parts, where reviewers usually state their overall view.
4. **Train** a fourth method on the verdicts themselves: TF-IDF word and two-word features with logistic regression.
5. **Evaluate** ([`evaluate.py`](src/animesent/evaluate.py)):
   - **Main test:** Recommended vs Not Recommended. Mixed Feelings reviews are left out, since neither answer is right for them.
   - **Cross-validation is split by show.** Five folds, and each review is scored by a model that never saw any review of that show. Otherwise the trained model could learn show names instead of sentiment.
   - **Off-the-shelf methods are scored twice:** at the cut-off they are normally used with (TextBlob above 0, VADER at 0.05 or above, SiEBERT above 50%) and at a cut-off tuned on the training folds only.
   - **Metrics:** ROC AUC measures how well a score separates the two verdicts at any cut-off. Balanced accuracy averages the hit rate on each verdict, so a method that calls everything positive scores 50%.
   - **Confidence intervals** resample whole shows (a cluster bootstrap), because reviews of the same show are not independent.
   - **Three verdicts:** the trained model is also tested on all three tags.
6. **Latest reviews vs the site score:** for each show, the average 1–10 rating in its latest reviews next to the score MyAnimeList shows, and the gap between them.
7. **By show:** for shows with at least 20 reviews, the share of reviewers who recommend the show (with a Wilson interval), compared with what TextBlob and the trained model would report.

## Running it

**Automatically:** [`.github/workflows/monthly.yml`](.github/workflows/monthly.yml) downloads the reviews, runs the analysis and commits `results/` on the 1st of every month. It can also be started by hand from the *Actions* tab.

**Locally** (Python 3.10+):

```bash
pip install -e ".[test]"                              # add ,model for the transformer
python -m animesent scrape --top 10                   # writes data/reviews.csv (15–30 minutes)
python -m animesent --data data/reviews.csv --min-reviews 20
python -m pytest                                      # 28 tests on synthetic reviews, a fake API and sample pages
```

**In Colab:** click the badge above. It downloads this month's top 10 and runs the analysis, or analyses your own reviews file from Google Drive. Turn on a GPU to include SiEBERT.

Outputs go to `results/`: `results.md`, `metrics.json`, `by_show.csv`, `anime.json` (the chosen anime) and three charts. They hold aggregate numbers only, no review text or usernames.

## Data

Reviews from [MyAnimeList](https://myanimelist.net), downloaded through the Jikan API. Each row has the anime, date, username, verdict tag, the reviewer's 1–10 score, whether it is preliminary or marked as a spoiler, and the review text. The analysis also accepts any `.xlsx` or `.csv` with `title`, `tag` and `text` columns.

**The raw reviews are not in this repository.** They were written by MyAnimeList users, whose terms don't allow them to be republished, and they include usernames. Only derived results are published here.

```
src/animesent/scrape.py     download the top anime and their reviews
src/animesent/mal_pages.py  read MyAnimeList's pages when the API is down
src/animesent/data.py       loading, verdict labels, anonymisation
src/animesent/methods.py    TextBlob, VADER, SiEBERT
src/animesent/evaluate.py   cross-validation, metrics, per-show results
src/animesent/report.py     charts and results.md
notebooks/run_analysis.ipynb
tests/                      pytest suite on synthetic reviews
```

## Forum discussion pipeline

Collect a separate AniList discussion dataset, capped at **5,000 unique comments per anime**:

```bash
python -m animesent forum --limit 5000
```

Uses the titles in `results/anime.json`, maps MAL IDs to AniList IDs, paginates associated threads and comments, and includes nested replies. Requires `curl` and the existing Python dependencies. Checkpoints in `data/forum/` let you resume the command. Aggregate predictions go to `results/forum.json`, which powers the new Discussions section. Actual counts may be below the cap. Per-title errors are reported, and partial data is retained. Raw comment text stays in local checkpoints; the frontend only displays aggregates.

VADER sentiment predictions use ±0.05 cut-offs. These comments have no verified recommendation labels and are excluded from review-model accuracy evaluation. Thread associations can include broader discussions, and VADER is primarily an English-language model.

[Run the forum collection in Colab](https://colab.research.google.com/github/harsh-github007/Anime-Reviews-Sentimental-Analysis/blob/design/anime-sentiment-atlas/notebooks/run_forum.ipynb). CPU is sufficient. The notebook supports Google Drive checkpoints and downloads aggregate results.

### Broader forum coverage

The forum command now defaults to `--sources both`. Set `MAL_CLIENT_ID` privately or enter it in the Colab notebook's masked prompt. Register an app at https://myanimelist.net/apiconfig; only the Client ID is needed, not the Client Secret. Jikan discovers anime-linked MAL topics; the official MAL API paginates their posts. If either service is unavailable, checkpoints and existing AniList results survive, and per-source status reports the limitation. The combined cap remains 5,000, with AniList sampled first. Posts are deduplicated by ID within each source; cross-platform copies are not detected.

`--min-comments 100` flags small samples without replacing your chosen titles. Zero-result titles display “No discussions found in collected sources.” Changing the target title list is explicit through `--titles`; no titles are silently substituted.

Without `MAL_CLIENT_ID`, the collector reads public MAL forum pages directly, with a three-second pause and explicit errors for blocked or changed markup. This requires no account setup. Public discovery uses topics shown on the anime forum listing; it is not a guarantee of every historical thread.
