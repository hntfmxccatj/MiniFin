"""分类器推理模块

加载训练好的模型工件，对解析后的账单记录预测 Major / Sub 分类。
"""
import json
import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

log = logging.getLogger("classifier")


def _normalize_major(label: str) -> str:
    """将模型预测出的 Major 名称对齐到数据库标准格式（下划线替换为空格）。"""
    return str(label).replace("_", " ").strip()


def _normalize_sub(label: str) -> str:
    """将模型预测出的 Sub 名称对齐到数据库标准格式：去掉前导 emoji/符号。"""
    s = str(label).strip()
    # 去掉开头连续的非字母、非数字、非中文字符
    while s and not (s[0].isalnum() or "\u4e00" <= s[0] <= "\u9fff"):
        s = s[1:]
    # 修正训练数据中的常见拼写错误
    s = s.replace("Subcription", "Subscription")
    return s.strip()


# 模型工件目录：training/models/（相对于 backend/ 的上级目录）
MODEL_DIR = Path(__file__).parent.parent / "training" / "models"

# 缓存，避免每次请求都重新加载
_ARTIFACTS: dict[str, Any] = {}


def _load_artifacts() -> dict[str, Any]:
    """一次性加载所有模型工件。缺失时返回空字典，上层降级处理。"""
    global _ARTIFACTS
    if _ARTIFACTS:
        return _ARTIFACTS

    required = {
        "tfidf_vectorizer": MODEL_DIR / "tfidf_vectorizer.pkl",
        "major_classifier": MODEL_DIR / "major_classifier.pkl",
        "major_label_encoder": MODEL_DIR / "major_label_encoder.pkl",
        "sub_classifier": MODEL_DIR / "sub_classifier.pkl",
        "sub_label_encoder": MODEL_DIR / "sub_label_encoder.pkl",
    }

    artifacts = {}
    for name, path in required.items():
        if not path.exists():
            log.warning(f"模型工件缺失: {path}")
            return {}
        try:
            artifacts[name] = joblib.load(path)
        except Exception as e:
            log.warning(f"加载模型失败 {path}: {e}")
            return {}

    _ARTIFACTS = artifacts
    log.info(f"模型加载完成: {MODEL_DIR}")
    return artifacts


def _build_text(counterparty: Any, product: Any) -> str:
    cp = "" if pd.isna(counterparty) else str(counterparty).strip()
    prod = "" if pd.isna(product) else str(product).strip()
    parts = []
    if cp:
        parts.append(cp)
    if prod and prod != cp:
        parts.append(prod)
    return " ".join(parts)


def predict_categories(records: list[dict]) -> list[tuple[str, str]]:
    """
    对记录列表预测 Major / Sub 分类。

    返回: [(major, sub), ...]
    如果模型未加载成功，返回全空字符串。
    """
    artifacts = _load_artifacts()
    if not artifacts:
        return [("", "")] * len(records)

    texts = [_build_text(r.get("counterparty"), r.get("product")) for r in records]
    df = pd.DataFrame({"text": texts})
    df = df[df["text"].str.len() > 0]

    # 如果所有 text 为空，直接返回空
    if df.empty:
        return [("", "")] * len(records)

    tfidf = artifacts["tfidf_vectorizer"]
    X = tfidf.transform(df["text"])

    major_clf = artifacts["major_classifier"]
    major_le = artifacts["major_label_encoder"]
    major_pred = major_clf.predict(X)
    major_labels = [_normalize_major(label) for label in major_le.inverse_transform(major_pred)]

    sub_clf = artifacts["sub_classifier"]
    sub_le = artifacts["sub_label_encoder"]
    sub_pred = sub_clf.predict(X)
    sub_labels = [_normalize_sub(label) for label in sub_le.inverse_transform(sub_pred)]


    # 按原始顺序回填
    result = []
    idx = 0
    for text in texts:
        if text.strip():
            result.append((major_labels[idx], sub_labels[idx]))
            idx += 1
        else:
            result.append(("", ""))
    return result
