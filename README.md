# Sentiment in Anime Reviews: Checked Against the Reviewers' Own Verdicts

Can an automatic sentiment tool tell whether an anime review is positive? Every review on MyAnimeList carries the reviewer's own verdict: **Recommended**, **Mixed Feelings** or **Not Recommended**. This project uses those verdicts as ground truth for about 32,000 scraped reviews and measures how well common sentiment methods agree with them.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/harsh-github007/Anime-Reviews-Sentimental-Analysis/blob/main/notebooks/run_analysis.ipynb)

> **Results:** see [`results/results.md`](results/results.md) once the analysis has been run on the data.

## Why it's hard

Reviews are long, and they rarely stay on one side. A review that ends "not recommended" often praises the art, the soundtrack or the first few episodes before explaining what went wrong. Methods that count positive and negative words see all that praise and call the review positive. The reviewer's verdict shows what they actually concluded.

## Method

1. **Load** ([`data.py`](src/animesent/data.py)).
   - Each review's tag is mapped to its verdict. Tags such as "Recommended Preliminary (3/12 eps)" are read by the phrase they contain.
   - Reviews with no verdict, empty text or duplicate text are dropped, and page furniture such as "Read more" is removed.
   - Usernames are replaced with a one-way hash.
2. **Score** every review with three off-the-shelf methods that need no training ([`methods.py`](src/animesent/methods.py)):
   - **TextBlob**, a widely used scorer that averages the polarity of English words.
   - **VADER**, a rule-based scorer built for short social media text.
   - **SiEBERT** (optional, needs a GPU), a RoBERTa-large model fine-tuned on reviews. Reviews longer than its 512-token window are judged on their opening and closing parts, where reviewers usually state their overall view.
3. **Train** a fourth method on the verdicts themselves: TF-IDF word and two-word features with logistic regression.
4. **Evaluate** ([`evaluate.py`](src/animesent/evaluate.py)):
   - **Main test:** Recommended vs Not Recommended. Mixed Feelings reviews are left out, since neither answer is right for them.
   - **Cross-validation is split by show.** Five folds, and each review is scored by a model that never saw any review of that show. Otherwise the trained model could learn show names instead of sentiment.
   - **Off-the-shelf methods are scored twice:** at the cut-off they are normally used with (TextBlob above 0, VADER at 0.05 or above, SiEBERT above 50%) and at a cut-off tuned on the training folds only.
   - **Metrics:** ROC AUC measures how well a score separates the two verdicts at any cut-off. Balanced accuracy averages the hit rate on each verdict, so a method that calls everything positive scores 50%.
   - **Confidence intervals** resample whole shows (a cluster bootstrap), because reviews of the same show are not independent.
   - **Three verdicts:** the trained model is also tested on all three tags.
5. **By show:** for shows with at least 40 reviews, the share of reviewers who recommend the show (with a Wilson interval), compared with what TextBlob and the trained model would report.

## Running it

**In Colab (recommended):** click the badge above. The notebook reads `Anime Reviews.xlsx` from your Google Drive, or asks you to upload it, and runs everything. Turn on a GPU to include SiEBERT.

**Locally** (Python 3.10+):

```bash
pip install -e ".[test]"               # add ,model for the transformer
python -m animesent --data "Anime Reviews.xlsx"
python -m pytest                        # 17 tests on synthetic reviews
```

Outputs go to `results/`: `results.md`, `metrics.json`, `by_show.csv` and three charts. They hold aggregate numbers only, no review text or usernames.

## Data

About 32,000 reviews scraped from [MyAnimeList](https://myanimelist.net) with Octoparse in February 2023. Each row has the show title, date, username, verdict tag and review text.

**The raw reviews are not in this repository.** They were written by MyAnimeList users, whose terms don't allow them to be republished, and they include usernames. Only derived results are published here.

```
src/animesent/data.py       loading, verdict labels, anonymisation
src/animesent/methods.py    TextBlob, VADER, SiEBERT
src/animesent/evaluate.py   cross-validation, metrics, per-show results
src/animesent/report.py     charts and results.md
notebooks/run_analysis.ipynb
tests/                      pytest suite on synthetic reviews
```
