# Results

185 reviews of 9 shows, each tagged by its author as Recommended (124), Mixed Feelings (25), Not Recommended (36).
Dropped before analysis: 0 with no verdict tag, 0 empty, 0 duplicates.

## The anime

The top 10 anime on MyAnimeList's top airing chart on 2026-10-01, and each one's newest 100 reviews.

| Chart rank | Anime | MAL score | Reviews |
| ---: | --- | ---: | ---: |
| 1 | Steel Ball Run: JoJo no Kimyou na Bouken | 9.06 | 3 |
| 2 | Bleach: Sennen Kessen-hen - Kashin-tan | 9.02 | 31 |
| 3 | One Piece | 8.72 | 100 |
| 4 | Chiikawa | 8.63 | 8 |
| 5 | Seihantai na Kimi to Boku 2nd Season | 8.51 | 18 |
| 6 | Shiguang Dailiren III | 8.51 | 4 |
| 7 | Xian Ni | 8.49 | 13 |
| 8 | Tian Guan Cifu Short Films | 8.47 | 0 |
| 9 | Doupo Cangqiong: Nian Fan | 8.39 | 4 |
| 10 | Tunshi Xingkong 4th Season | 8.33 | 4 |

## Latest reviews vs the MyAnimeList score

The score MyAnimeList shows is the average of every user's rating. Each review also carries its author's 1–10 rating, so the latest reviews can be checked against it.

Across the 9 shows with rated reviews, the latest reviews average **0.69 points below** the site score, and are **0.82 points away** on average. 4 of 9 land within half a point.

| Chart rank | Anime | MAL score | Latest reviews | Their average rating | Gap | Recommended | Reviews dated |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Steel Ball Run: JoJo no Kimyou na Bouken | 9.06 | 3 | 9.67 | +0.61 | 100% | 2026-09-28 to 2026-09-30 |
| 2 | Bleach: Sennen Kessen-hen - Kashin-tan | 9.02 | 31 | 7.71 | -1.31 | 71% | 2026-08-12 to 2026-09-23 |
| 3 | One Piece | 8.72 | 100 | 7.62 | -1.10 | 60% | 2025-04-02 to 2026-09-12 |
| 4 | Chiikawa | 8.63 | 8 | 8.38 | -0.26 | 100% | 2023-10-29 to 2026-09-19 |
| 5 | Seihantai na Kimi to Boku 2nd Season | 8.51 | 18 | 8.44 | -0.07 | 89% | 2026-07-21 to 2026-09-29 |
| 6 | Shiguang Dailiren III | 8.51 | 4 | 6.75 | -1.76 | 50% | 2026-08-31 to 2026-10-01 |
| 7 | Xian Ni | 8.49 | 13 | 6.92 | -1.57 | 62% | 2024-06-15 to 2026-09-14 |
| 8 | Tian Guan Cifu Short Films | 8.47 | 0 | – | – | – | no reviews |
| 9 | Doupo Cangqiong: Nian Fan | 8.39 | 4 | 8.00 | -0.39 | 75% | 2023-08-03 to 2025-05-11 |
| 10 | Tunshi Xingkong 4th Season | 8.33 | 4 | 8.00 | -0.33 | 50% | 2024-04-06 to 2026-04-12 |

Reviews are a small, self-selected group: people who write a review often feel strongly, and a show's latest reviews reflect its latest episodes, while the site score covers everyone who rated it.

## What TextBlob says

TextBlob calls 91.9% of reviews positive. The reviewers themselves recommend 67.0% of the shows they review, and TextBlob scores 78% of **Not Recommended** reviews as positive.

![TextBlob polarity by verdict](figures/textblob_by_verdict.png)

## How well each method matches the verdict

Recommended vs Not Recommended: 160 reviews (124 vs 36). Five-fold cross-validation split by show, so every review is scored by a model that never saw that show. Balanced accuracy averages the hit rate on each verdict, so always answering "Recommended" scores 50%.

| Method | ROC AUC (95% CI) | Balanced accuracy, usual cut-off | Balanced accuracy, tuned cut-off | Not Recommended caught |
| --- | ---: | ---: | ---: | ---: |
| TextBlob | 0.85 (0.83–1.00) | 59% | 78% | 22% |
| VADER | 0.84 (0.76–0.99) | 70% | 73% | 44% |
| Trained on verdicts | 0.79 (0.70–0.99) | 67% | 69% | 36% |

Best at separating the verdicts: **TextBlob**.

![Methods](figures/methods.png)

## Three verdicts

Trained on all three tags, the model reaches a macro F1 of 0.45 and balanced accuracy of 46%. Rows are the reviewer's tag, columns the model's guess:

| | Recommended | Mixed Feelings | Not Recommended |
| --- | ---: | ---: | ---: |
| **Recommended** | 122 | 0 | 2 |
| **Mixed Feelings** | 22 | 0 | 3 |
| **Not Recommended** | 22 | 0 | 14 |

## What the trained model listens to

Words and phrases with the largest weights toward each verdict:

- **Recommended:** best, the best, 10 10, cour, romance, donghua, feel, world, chiikawa, journey, we, very, such, watch, to say
- **Not Recommended:** fight, out of, plot, same, minutes, the worst, worst, over, someone, 20, then, the same, bad, boring, to make

## Caveats

- Reviews of the top airing chart on MyAnimeList, downloaded 2026-10-01. Reviewers who write reviews are not all viewers, so these rates describe reviews, not audiences.
- A tag is a single summary of a long, often mixed review; some disagreement with any method is expected.
- Scores come from English text only; reviews in other languages were left as they are.
