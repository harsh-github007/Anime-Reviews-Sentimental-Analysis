# Results

261 reviews of 9 shows, each tagged by its author as Recommended (175), Mixed Feelings (33), Not Recommended (53).
Dropped before analysis: 0 with no verdict tag, 0 empty, 0 duplicates.

## The anime

The top 10 anime on MyAnimeList's top airing chart on 2026-09-30, and each one's newest 100 reviews.

| Chart rank | Anime | MAL score | Reviews |
| ---: | --- | ---: | ---: |
| 1 | Re:Zero kara Hajimeru Isekai Seikatsu 4th Season | 9.11 | 83 |
| 2 | Steel Ball Run: JoJo no Kimyou na Bouken | 9.07 | 2 |
| 3 | Bleach: Sennen Kessen-hen - Kashin-tan | 9.03 | 31 |
| 4 | One Piece | 8.72 | 100 |
| 5 | Chiikawa | 8.62 | 8 |
| 6 | Seihantai na Kimi to Boku 2nd Season | 8.51 | 18 |
| 7 | Shiguang Dailiren III | 8.51 | 2 |
| 8 | Xian Ni | 8.49 | 13 |
| 9 | Tian Guan Cifu Short Films | 8.47 | 0 |
| 10 | Doupo Cangqiong: Nian Fan | 8.39 | 4 |

## Latest reviews vs the MyAnimeList score

The score MyAnimeList shows is the average of every user's rating. Each review also carries its author's 1–10 rating, so the latest reviews can be checked against it.

Across the 9 shows with rated reviews, the latest reviews average **0.79 points below** the site score, and are **0.99 points away** on average. 3 of 9 land within half a point.

| Chart rank | Anime | MAL score | Latest reviews | Their average rating | Gap | Recommended | Reviews dated |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Re:Zero kara Hajimeru Isekai Seikatsu 4th Season | 9.11 | 83 | 7.81 | -1.30 | 66% | 2026-04-22 to 2026-09-25 |
| 2 | Steel Ball Run: JoJo no Kimyou na Bouken | 9.07 | 2 | 10.00 | +0.93 | 100% | 2026-09-28 to 2026-09-28 |
| 3 | Bleach: Sennen Kessen-hen - Kashin-tan | 9.03 | 31 | 7.71 | -1.32 | 71% | 2026-08-12 to 2026-09-23 |
| 4 | One Piece | 8.72 | 100 | 7.62 | -1.10 | 60% | 2025-04-02 to 2026-09-12 |
| 5 | Chiikawa | 8.62 | 8 | 8.38 | -0.24 | 100% | 2023-10-29 to 2026-09-19 |
| 6 | Seihantai na Kimi to Boku 2nd Season | 8.51 | 18 | 8.44 | -0.07 | 89% | 2026-07-21 to 2026-09-29 |
| 7 | Shiguang Dailiren III | 8.51 | 2 | 6.50 | -2.01 | 50% | 2026-08-31 to 2026-09-27 |
| 8 | Xian Ni | 8.49 | 13 | 6.92 | -1.57 | 62% | 2024-06-15 to 2026-09-14 |
| 9 | Tian Guan Cifu Short Films | 8.47 | 0 | – | – | – | no reviews |
| 10 | Doupo Cangqiong: Nian Fan | 8.39 | 4 | 8.00 | -0.39 | 75% | 2023-08-03 to 2025-05-11 |

Reviews are a small, self-selected group: people who write a review often feel strongly, and a show's latest reviews reflect its latest episodes, while the site score covers everyone who rated it.

## What TextBlob says

TextBlob calls 90.8% of reviews positive. The reviewers themselves recommend 67.0% of the shows they review, and TextBlob scores 75% of **Not Recommended** reviews as positive.

![TextBlob polarity by verdict](figures/textblob_by_verdict.png)

## How well each method matches the verdict

Recommended vs Not Recommended: 228 reviews (175 vs 53). Five-fold cross-validation split by show, so every review is scored by a model that never saw that show. Balanced accuracy averages the hit rate on each verdict, so always answering "Recommended" scores 50%.

| Method | ROC AUC (95% CI) | Balanced accuracy, usual cut-off | Balanced accuracy, tuned cut-off | Not Recommended caught |
| --- | ---: | ---: | ---: | ---: |
| TextBlob | 0.87 (0.83–0.94) | 61% | 80% | 25% |
| VADER | 0.81 (0.72–0.89) | 71% | 69% | 51% |
| Trained on verdicts | 0.86 (0.77–0.93) | 69% | 76% | 40% |

Best at separating the verdicts: **TextBlob**.

![Methods](figures/methods.png)

## Three verdicts

Trained on all three tags, the model reaches a macro F1 of 0.47 and balanced accuracy of 47%. Rows are the reviewer's tag, columns the model's guess:

| | Recommended | Mixed Feelings | Not Recommended |
| --- | ---: | ---: | ---: |
| **Recommended** | 170 | 1 | 4 |
| **Mixed Feelings** | 26 | 1 | 6 |
| **Not Recommended** | 32 | 0 | 21 |

## By show

Shows with at least 20 reviews (3).

![Shows](figures/titles.png)

| Show | Reviews | Recommended (95% CI) | Not Recommended | TextBlob positive |
| --- | ---: | ---: | ---: | ---: |
| Bleach: Sennen Kessen-hen - Kashin-tan | 31 | 71% (53%–84%) | 23% | 94% |
| Re:Zero kara Hajimeru Isekai Seikatsu 4th Season | 83 | 66% (56%–76%) | 23% | 88% |
| One Piece | 100 | 60% (50%–69%) | 24% | 91% |

## What the trained model listens to

Words and phrases with the largest weights toward each verdict:

- **Recommended:** best, the best, 10 10, amazing, cour, you, peak, the animation, perfect, very, such, animation, love, especially, world
- **Not Recommended:** plot, same, the worst, worst, bad, the same, the plot, minutes, over, fight, out of, boring, no, barely, rather

## Caveats

- Reviews of the top airing chart on MyAnimeList, downloaded 2026-09-30. Reviewers who write reviews are not all viewers, so these rates describe reviews, not audiences.
- A tag is a single summary of a long, often mixed review; some disagreement with any method is expected.
- Scores come from English text only; reviews in other languages were left as they are.
