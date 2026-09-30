"""Sentiment methods compared in this project.

Each off-the-shelf method returns one number per review where higher means more
positive. They need no training, which is exactly why they need checking.

- TextBlob: the original project's method. Averages the polarity of known English words.
- VADER: a rule-based scorer built for short social media text.
- Transformer (optional, needs a GPU to be quick): SiEBERT, a RoBERTa-large model
  fine-tuned on reviews from many domains. Returns the probability of "positive".

The trained method, TF-IDF with logistic regression, is fitted on the reviewers'
own verdicts inside cross-validation (see evaluate.py).
"""

import numpy as np

TRANSFORMER_MODEL = "siebert/sentiment-roberta-large-english"


def textblob(texts):
    from textblob import TextBlob
    return np.array([TextBlob(t).sentiment.polarity for t in texts])


def vader(texts):
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    sia = SentimentIntensityAnalyzer()
    return np.array([sia.polarity_scores(t)["compound"] for t in texts])


def transformer(texts, model=TRANSFORMER_MODEL, batch_size=16, progress=True):
    """P(positive) from a pretrained sentiment model.

    Reviews longer than the model's 512-token window are judged on their first
    and last parts, where reviewers usually state their overall view.
    """
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model)
    net = AutoModelForSequenceClassification.from_pretrained(model).to(device).eval()
    pos = next(i for i, name in net.config.id2label.items() if name.upper().startswith("POS"))

    def head_tail(t, keep=510):
        ids = tok(t, add_special_tokens=False, truncation=False)["input_ids"]
        if len(ids) <= keep:
            return t
        return tok.decode(ids[:128]) + " ... " + tok.decode(ids[-(keep - 128):])

    out = []
    texts = list(texts)
    for i in range(0, len(texts), batch_size):
        chunk = [head_tail(t) for t in texts[i:i + batch_size]]
        enc = tok(chunk, truncation=True, max_length=512, padding=True, return_tensors="pt").to(device)
        with torch.no_grad():
            p = torch.softmax(net(**enc).logits, dim=-1)[:, pos]
        out.extend(p.cpu().numpy().tolist())
        if progress and (i // batch_size) % 50 == 0:
            print(f"  transformer: {i + len(chunk):,} / {len(texts):,}", flush=True)
    return np.array(out)


# Off-the-shelf methods, with the cut-off each one is normally used with.
OFF_THE_SHELF = {
    "TextBlob": (textblob, 0.0),
    "VADER": (vader, 0.05),
}
