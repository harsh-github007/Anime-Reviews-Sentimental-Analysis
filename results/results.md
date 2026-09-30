# Results

446 reviews of 5 shows, each tagged by its author as Recommended (312), Mixed Feelings (42), Not Recommended (92).
Dropped before analysis: 0 with no verdict tag, 0 empty, 0 duplicates.

## The anime

The 5 highest-ranked anime on MyAnimeList's top airing chart on 2026-09-30 with at least 20 reviews, and up to 200 of each one's reviews. Skipped for having too few reviews: Steel Ball Run: JoJo no Kimyou na Bouken (2), Chiikawa (8), Seihantai na Kimi to Boku 2nd Season (18), Shiguang Dailiren III (2), Xian Ni (13), Tian Guan Cifu Short Films (0), Doupo Cangqiong: Nian Fan (4), Tunshi Xingkong 4th Season (4), Mushen Ji (6), Guangyin Zhi Wai 2 (0), Yuanshen: Donghua Duanpian (2), Fanren Xiu Xian Zhuan: Mulan Zhi Zhan (0), Douluo Dalu II: Jueshi Tangmen (3), Wanmei Shijie (14), Benghuai: Xing Qiong Tiedao - Donghua Duanpian (0), Crayon Shin-chan (16), Doraemon (2005) (3), Clevatess II: Majuu no Ou to Itsuwari no Yuusha Denshou (6), Cang Yuan Tu 3 (0), Zhe Tian (8), Honzuki no Gekokujou: Shisho ni Naru Tame ni wa Shudan wo Erandeiraremasen - Ryoushu no Youjo (10), Meitantei Precure! (4), Gensou Mangekyou: The Memories of Phantasm (12), Koupen-chan (2), Wushen Zhuzai (11), Yasei no Last Boss ga Arawareta! 2nd Season (0), Nige Jouzu no Wakagimi 2nd Season (1), Yamato yo, Towa ni: Rebel 3199 (0), Yi Nian Yong Heng: Wanjie Ji (0), Chibi Maruko-chan (1995) (2), Lian Qi Shi Wan Nian (4), Pokemon (2023) (16), Nitian Xie Shen: Nian Fan (1), Tensei Kizoku, Kantei Skill de Nariagaru 3rd Season (0), Hifuu Katsudou Kiroku: The Sealed Esoteric History (3), Re:Zero kara Hajimeru Break Time 4th Season (0), Tempal: Item no Chikara (0), Touhou Niji Sousaku Doujin Anime: Musou Kakyou (10), Ni Tian Zhizun (4), Girigiri Warukunai Watame (3), Wu Shang Shen Di 2nd Season (2), GANSO! BanG Dream Chan (0), Oneechan Gokko (1), Wan Jie Du Zun 3rd Season (0), Da Zhuzai: Nian Fan 2 (2).

| Chart rank | Anime | MAL score | Reviews |
| ---: | --- | ---: | ---: |
| 1 | Re:Zero kara Hajimeru Isekai Seikatsu 4th Season | 9.11 | 83 |
| 3 | Bleach: Sennen Kessen-hen - Kashin-tan | 9.03 | 31 |
| 4 | One Piece | 8.72 | 200 |
| 13 | Meitantei Conan | 8.18 | 102 |
| 14 | Holo no Graffiti | 8.13 | 30 |

## What TextBlob says

TextBlob calls 91.7% of reviews positive. The reviewers themselves recommend 70.0% of the shows they review, and TextBlob scores 70% of **Not Recommended** reviews as positive.

![TextBlob polarity by verdict](figures/textblob_by_verdict.png)

## How well each method matches the verdict

Recommended vs Not Recommended: 404 reviews (312 vs 92). Five-fold cross-validation split by show, so every review is scored by a model that never saw that show. Balanced accuracy averages the hit rate on each verdict, so always answering "Recommended" scores 50%.

| Method | ROC AUC (95% CI) | Balanced accuracy, usual cut-off | Balanced accuracy, tuned cut-off | Not Recommended caught |
| --- | ---: | ---: | ---: | ---: |
| TextBlob | 0.89 (0.81–0.91) | 64% | 82% | 30% |
| VADER | 0.79 (0.69–0.82) | 71% | 68% | 50% |
| Trained on verdicts | 0.89 (0.86–0.96) | 74% | 77% | 51% |

Best at separating the verdicts: **Trained on verdicts**.

![Methods](figures/methods.png)

## Three verdicts

Trained on all three tags, the model reaches a macro F1 of 0.49 and balanced accuracy of 50%. Rows are the reviewer's tag, columns the model's guess:

| | Recommended | Mixed Feelings | Not Recommended |
| --- | ---: | ---: | ---: |
| **Recommended** | 301 | 1 | 10 |
| **Mixed Feelings** | 32 | 0 | 10 |
| **Not Recommended** | 43 | 0 | 49 |

## By show

Shows with at least 20 reviews (5).

![Shows](figures/titles.png)

| Show | Reviews | Recommended (95% CI) | Not Recommended | TextBlob positive |
| --- | ---: | ---: | ---: | ---: |
| Meitantei Conan | 102 | 88% (81%–93%) | 4% | 99% |
| Bleach: Sennen Kessen-hen - Kashin-tan | 31 | 71% (53%–84%) | 23% | 94% |
| Re:Zero kara Hajimeru Isekai Seikatsu 4th Season | 83 | 66% (56%–76%) | 23% | 88% |
| Holo no Graffiti | 30 | 63% (46%–78%) | 27% | 100% |
| One Piece | 200 | 63% (56%–69%) | 27% | 88% |

## What the trained model listens to

Words and phrases with the largest weights toward each verdict:

- **Recommended:** conan, detective, detective conan, best, the best, amazing, 10 10, peak, cour, its, masterpiece, anime and, well, one of, mystery
- **Not Recommended:** same, the same, bad, the worst, waste, worst, pacing, boring, any, minutes, worse, they, over, horrible, plot

## Caveats

- Reviews of the top airing chart on MyAnimeList, downloaded 2026-09-30. Reviewers who write reviews are not all viewers, so these rates describe reviews, not audiences.
- A tag is a single summary of a long, often mixed review; some disagreement with any method is expected.
- Scores come from English text only; reviews in other languages were left as they are.
