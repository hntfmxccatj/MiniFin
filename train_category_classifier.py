"""
Train a text classifier to predict Major / Sub category from counterparty + product.

Usage:
    python train_category_classifier.py

Outputs (under ./models/):
    - tfidf_vectorizer.pkl
    - major_classifier.pkl
    - major_label_encoder.pkl
    - sub_classifier.pkl
    - sub_label_encoder.pkl
    - metrics.json

Later, in FastAPI you can load these artifacts and call:
    major_clf.predict(tfidf.transform([text]))
"""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# ──────────────────────────────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
DATA_PATH = ROOT / "Training Data.csv"
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)

TEST_SIZE = 0.2
RANDOM_STATE = 42


def clean_text(text: Any) -> str:
    """Light cleaning for Chinese/English mixed transaction text."""
    if pd.isna(text) or not str(text).strip() or str(text).strip() == "/":
        return ""
    s = str(text).strip()
    # collapse whitespace, keep CJK / ASCII / digits / basic punctuation
    s = re.sub(r"\s+", " ", s)
    return s


def build_feature(row: pd.Series) -> str:
    """Combine counterparty + product as the model input."""
    cp = clean_text(row.get("counterparty", ""))
    prod = clean_text(row.get("product", ""))
    # give counterparty slightly more weight by repeating it
    parts = []
    if cp:
        parts.append(cp)
    if prod and prod != cp:
        parts.append(prod)
    return " ".join(parts)


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows from {path}")
    print("Columns:", df.columns.tolist())

    # normalize column names (strip spaces / lower-case friendly)
    df = df.rename(
        columns={
            "Category Group": "major",
            "Category": "sub",
        }
    )

    required = {"counterparty", "product", "major", "sub"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # build feature column
    df["text"] = df.apply(build_feature, axis=1)

    # drop rows where text is empty or labels are empty
    df = df[df["text"].str.len() > 0].copy()
    df = df.dropna(subset=["major", "sub"])

    print(f"After cleaning: {len(df)} rows")
    return df


def print_label_distribution(df: pd.DataFrame):
    print("\nMajor category distribution:")
    print(df["major"].value_counts())
    print("\nSub category distribution (top 20):")
    print(df["sub"].value_counts().head(20))


def train_text_classifier(
    df: pd.DataFrame,
    label_col: str,
    model_name: str,
) -> dict[str, Any]:
    """Train a TF-IDF + LogisticRegression classifier for one label."""
    X = df["text"].tolist()
    y = df[label_col].tolist()

    # Encode labels
    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    # Split stratified
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_enc,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y_enc,
    )

    # Character-level TF-IDF works well for short Chinese/English mixed text
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        max_features=8000,
        min_df=2,
        max_df=0.95,
    )
    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)

    # LogisticRegression is fast, calibrated, and works well with TF-IDF
    clf = LogisticRegression(
        max_iter=1000,
        C=1.0,
        class_weight="balanced",
        n_jobs=-1,
    )
    clf.fit(X_train_tfidf, y_train)

    y_pred = clf.predict(X_test_tfidf)

    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    weighted_f1 = f1_score(y_test, y_pred, average="weighted")

    print(f"\n=== {model_name} ===")
    print(f"Classes: {len(le.classes_)}")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Macro F1:  {macro_f1:.4f}")
    print(f"Weighted F1: {weighted_f1:.4f}")
    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            y_pred,
            target_names=le.classes_,
            zero_division=0,
        )
    )

    return {
        "vectorizer": vectorizer,
        "classifier": clf,
        "label_encoder": le,
        "metrics": {
            "accuracy": round(acc, 4),
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
            "num_classes": len(le.classes_),
            "num_samples": len(X),
        },
    }


def save_artifact(name: str, obj: Any):
    path = MODEL_DIR / f"{name}.pkl"
    joblib.dump(obj, path)
    print(f"Saved {path}")


def main():
    df = load_data(DATA_PATH)
    print_label_distribution(df)

    # ── Major (Category Group) ──
    major_result = train_text_classifier(df, label_col="major", model_name="Major Category")
    save_artifact("major_classifier", major_result["classifier"])
    save_artifact("major_label_encoder", major_result["label_encoder"])

    # ── Sub (Category) ──
    # Strategy: independent classifier. It works well when the label set is small.
    # For even better accuracy, a hierarchical model can be added later:
    #   1. predict major
    #   2. route to a sub-classifier trained only on that major's data.
    sub_result = train_text_classifier(df, label_col="sub", model_name="Sub Category")
    save_artifact("sub_classifier", sub_result["classifier"])
    save_artifact("sub_label_encoder", sub_result["label_encoder"])

    # One shared TF-IDF for both (keeps API simple). If you later want
    # separate vectorizers, just split this into two.
    save_artifact("tfidf_vectorizer", major_result["vectorizer"])

    # Save metrics
    metrics = {
        "major": major_result["metrics"],
        "sub": sub_result["metrics"],
    }
    metrics_path = MODEL_DIR / "metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"Saved {metrics_path}")

    print("\nTraining complete. Artifacts saved under ./models/")


if __name__ == "__main__":
    main()
