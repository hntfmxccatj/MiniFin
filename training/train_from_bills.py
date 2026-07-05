"""
从 wallet.db 中已手动分类的 bills 记录训练层级分类模型。

模型结构：
  1. Major 分类器：预测一级分类。
  2. Sub 分类器族：每个 Major 对应一个专门的 Sub 分类器，
     只在该 Major 的训练数据上训练，确保预测出的 Sub 必然属于该 Major。

特征：
  - counterparty + product + payment_method + source + 交易类型
  - char_wb TF-IDF，适合中英文混合短文本

用法：
    source venv/Scripts/activate
    python -m training.train_from_bills

输出：
    training/models/ 下的 pkl/json 工件
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# 兼容 Windows 终端 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.resolve()
PROJECT_ROOT = ROOT.parent
DB_PATH = PROJECT_ROOT / "wallet.db"
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)

TEST_SIZE = 0.2
RANDOM_STATE = 42
MIN_SUB_SAMPLES = 3  # 少于该样本数的 sub 会被合并到 "__other__"


def clean_text(text: Any) -> str:
    """清洗文本，去除无意义占位符和常见前缀。"""
    if pd.isna(text) or not str(text).strip() or str(text).strip() == "/":
        return ""
    s = str(text).strip()
    # 去掉 "收款方备注:" 等常见前缀
    s = re.sub(r"^收款方备注[:：]", "", s)
    s = re.sub(r"^付款方留言[:：]", "", s)
    # 合并空白
    s = re.sub(r"\s+", " ", s)
    return s


def build_feature(row: pd.Series) -> str:
    """组合多字段为模型输入文本。"""
    parts = [
        clean_text(row.get("counterparty", "")),
        clean_text(row.get("product", "")),
        clean_text(row.get("payment_method", "")),
    ]
    # 把交易类型作为强信号加入
    trade_type = clean_text(row.get("trade_type", ""))
    if trade_type:
        parts.append(trade_type)
    # source 作为离散标记
    source = clean_text(row.get("source", ""))
    if source:
        parts.append(f"src_{source}")

    # 给交易对方更高权重
    cp = clean_text(row.get("counterparty", ""))
    if cp:
        parts.insert(0, cp)

    return " ".join(p for p in parts if p)


def load_category_map(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """从 categories 表读取权威的 major -> set(sub) 映射。"""
    valid_map = defaultdict(set)
    for r in conn.execute("SELECT major_category, sub_category FROM categories"):
        major = r["major_category"].strip()
        sub = r["sub_category"].strip()
        if major and sub:
            valid_map[major].add(sub)
    return valid_map


def load_labeled_bills() -> tuple[pd.DataFrame, dict[str, set[str]]]:
    """从 wallet.db 读取已标注的 bills 记录，并过滤为符合 categories 表映射的数据。"""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"数据库不存在: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        valid_map = load_category_map(conn)
        cur = conn.execute(
            "SELECT id, source, raw_id, trade_time, amount, type, "
            "major_category, sub_category, counterparty, product, payment_method, raw_data "
            "FROM bills "
            "WHERE major_category IS NOT NULL AND major_category != '' "
            "  AND sub_category IS NOT NULL AND sub_category != ''"
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    records = []
    dropped = []
    for r in rows:
        major = r["major_category"].strip()
        sub = r["sub_category"].strip()
        # 只保留符合 categories 表权威映射的数据
        if major not in valid_map or sub not in valid_map[major]:
            dropped.append({"id": r["id"], "major": major, "sub": sub})
            continue

        raw_data = json.loads(r["raw_data"]) if r["raw_data"] else {}
        trade_type = raw_data.get("交易类型", "")
        records.append({
            "id": r["id"],
            "source": r["source"],
            "trade_time": r["trade_time"],
            "amount": r["amount"],
            "type": r["type"],
            "major": major,
            "sub": sub,
            "counterparty": r["counterparty"],
            "product": r["product"],
            "payment_method": r["payment_method"],
            "trade_type": trade_type,
        })

    df = pd.DataFrame(records)
    df["text"] = df.apply(build_feature, axis=1)

    # 丢弃空特征
    df = df[df["text"].str.len() > 0].copy()

    print(f"从数据库加载 {len(rows)} 条已分类记录")
    if dropped:
        print(f"  其中 {len(dropped)} 条与 categories 表映射不一致，已过滤")
    print(f"  实际用于训练: {len(df)} 条")
    return df, valid_map


def reduce_rare_subs(df: pd.DataFrame, valid_map: dict[str, set[str]]) -> pd.DataFrame:
    """把每个 major 下样本过少的 sub 合并到该 major 下最常见的合法 sub。"""
    result = []
    for major, group in df.groupby("major"):
        sub_counts = group["sub"].value_counts()
        if sub_counts.empty:
            continue
        dominant_sub = sub_counts.index[0]
        keep = sub_counts[sub_counts >= MIN_SUB_SAMPLES].index.tolist()
        group = group.copy()
        group["sub"] = group["sub"].apply(
            lambda x: x if x in keep else dominant_sub
        )
        result.append(group)
    return pd.concat(result, ignore_index=True)


def split_stratified(df: pd.DataFrame, label_col: str, group_col: str | None = None):
    """分层划分训练/测试集，优先按 group_col + label_col 分层。"""
    if group_col:
        stratify = df[group_col].astype(str) + "_" + df[label_col].astype(str)
    else:
        stratify = df[label_col]

    # 如果某些组合只有 1 条，无法分层，改用 label_col
    if stratify.value_counts().min() < 2:
        stratify = df[label_col]

    try:
        return train_test_split(
            df,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
            stratify=stratify,
        )
    except ValueError:
        return train_test_split(
            df,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
            stratify=None,
        )


def train_classifier(
    df: pd.DataFrame,
    label_col: str,
    model_name: str,
    vectorizer: TfidfVectorizer | None = None,
) -> dict[str, Any]:
    """训练一个 TF-IDF + LogisticRegression 分类器。

    如果传入已 fit 的 vectorizer，则直接使用其 transform；
    否则在训练数据上 fit 新的 vectorizer。
    """
    X = df["text"].tolist()
    y = df[label_col].tolist()

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    df_train, df_test = split_stratified(df, label_col)
    X_train = df_train["text"].tolist()
    X_test = df_test["text"].tolist()
    y_train = le.transform(df_train[label_col])
    y_test = le.transform(df_test[label_col])

    if vectorizer is None:
        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            max_features=8000,
            min_df=1,
            max_df=1.0,
        )
        X_train_tfidf = vectorizer.fit_transform(X_train)
    else:
        X_train_tfidf = vectorizer.transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)

    clf = LogisticRegression(
        max_iter=2000,
        C=1.0,
        class_weight="balanced",
        solver="lbfgs",
    )
    clf.fit(X_train_tfidf, y_train)

    y_pred = clf.predict(X_test_tfidf)
    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
    weighted_f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    print(f"\n=== {model_name} ===")
    print(f"  训练样本: {len(X_train)} | 测试样本: {len(X_test)} | 类别数: {len(le.classes_)}")
    print(f"  Accuracy: {acc:.4f} | Macro F1: {macro_f1:.4f} | Weighted F1: {weighted_f1:.4f}")

    unique_labels = sorted(set(y_test) | set(y_pred))
    print(classification_report(
        y_test,
        y_pred,
        labels=unique_labels,
        target_names=[str(le.classes_[i]) for i in unique_labels],
        zero_division=0,
    ))

    return {
        "classifier": clf,
        "label_encoder": le,
        "vectorizer": vectorizer,
        "metrics": {
            "accuracy": round(acc, 4),
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
            "num_classes": len(le.classes_),
            "num_train": len(X_train),
            "num_test": len(X_test),
        },
    }


def main():
    df, valid_map = load_labeled_bills()
    if df.empty:
        print("没有已分类数据，无法训练。")
        return

    print("\nMajor 分布:")
    print(df["major"].value_counts())
    print("\nSub 分布（每个 Major TOP 5）:")
    for major, group in df.groupby("major"):
        print(f"  [{major}]")
        print(group["sub"].value_counts().head(5).to_string().replace("\n", "\n    "))

    df = reduce_rare_subs(df, valid_map)

    # ── 先 fit 一个全局 TF-IDF，保证 Major 与所有 Sub 分类器共享同一词汇空间 ──
    print("\nFitting shared TF-IDF vectorizer...")
    shared_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        max_features=8000,
        min_df=1,
        max_df=1.0,
    )
    shared_vectorizer.fit(df["text"].tolist())

    # ── Major 分类器 ──
    major_result = train_classifier(df, label_col="major", model_name="Major Category", vectorizer=shared_vectorizer)

    # ── 每个 Major 训练一个 Sub 分类器 ──
    sub_classifiers = {}
    sub_encoders = {}
    sub_metrics = {}

    for major in sorted(df["major"].unique()):
        sub_df = df[df["major"] == major].copy()
        # 去掉 __other__ 后如果只剩一个 sub，无需分类器
        unique_subs = sub_df["sub"].unique().tolist()
        if len(unique_subs) < 2:
            sub_classifiers[major] = None
            sub_encoders[major] = None
            sub_metrics[major] = {"skipped": True, "reason": "only_one_sub", "sub": unique_subs[0] if unique_subs else ""}
            print(f"\n=== Sub Category for [{major}] ===")
            print(f"  仅有一个 sub: {unique_subs[0] if unique_subs else 'N/A'}，跳过训练")
            continue

        result = train_classifier(sub_df, label_col="sub", model_name=f"Sub Category / {major}", vectorizer=shared_vectorizer)
        sub_classifiers[major] = result["classifier"]
        sub_encoders[major] = result["label_encoder"]
        sub_metrics[major] = result["metrics"]

    # ── 保存映射与 fallback ──
    # 以 categories 表为权威来源，而非训练数据
    major_sub_map = {major: sorted(subs) for major, subs in valid_map.items() if subs}
    fallback_sub = {}
    for major, group in df.groupby("major"):
        sub_counts = group["sub"].value_counts()
        fallback_sub[major] = sub_counts.index[0]
    # 对训练数据中未出现的 major，fallback 到其第一个合法 sub
    for major, subs in major_sub_map.items():
        if major not in fallback_sub and subs:
            fallback_sub[major] = subs[0]

    # ── 保存工件 ──
    joblib.dump(shared_vectorizer, MODEL_DIR / "tfidf_vectorizer.pkl")
    joblib.dump(major_result["classifier"], MODEL_DIR / "major_classifier.pkl")
    joblib.dump(major_result["label_encoder"], MODEL_DIR / "major_label_encoder.pkl")
    joblib.dump(sub_classifiers, MODEL_DIR / "sub_classifiers.pkl")
    joblib.dump(sub_encoders, MODEL_DIR / "sub_label_encoders.pkl")

    with open(MODEL_DIR / "major_sub_map.json", "w", encoding="utf-8") as f:
        json.dump(dict(major_sub_map), f, ensure_ascii=False, indent=2)
    with open(MODEL_DIR / "fallback_sub.json", "w", encoding="utf-8") as f:
        json.dump(fallback_sub, f, ensure_ascii=False, indent=2)

    metrics = {
        "major": major_result["metrics"],
        "sub_per_major": sub_metrics,
    }
    with open(MODEL_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print("\n训练完成，工件已保存到:", MODEL_DIR)


if __name__ == "__main__":
    main()
