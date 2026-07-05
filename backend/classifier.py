"""分类器推理模块

加载训练好的层级模型工件，对解析后的账单记录预测 Major / Sub 分类。

模型结构：
  1. Major 分类器 -> 预测一级分类
  2. Major 对应的 Sub 分类器 -> 预测二级分类（保证 Sub 一定属于该 Major）
  3. 若 Major 下无 Sub 分类器或预测失败，使用 fallback_sub
"""
import json
import logging
import os
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

log = logging.getLogger("classifier")

MODEL_DIR = Path(__file__).parent.parent / "training" / "models"

_ARTIFACTS: dict[str, Any] = {}
_ARTIFACTS_MTIME = 0.0


def _get_max_mtime() -> float:
    """返回模型工件目录中最新的文件修改时间。"""
    mtimes = []
    if MODEL_DIR.exists():
        for path in MODEL_DIR.iterdir():
            if path.is_file():
                mtimes.append(os.path.getmtime(path))
    return max(mtimes) if mtimes else 0.0


def _build_text(counterparty: Any, product: Any, payment_method: Any = "", source: Any = "", trade_type: Any = "") -> str:
    """与训练脚本保持一致的文本构建逻辑。"""
    def _clean(text):
        if pd.isna(text) or not str(text).strip() or str(text).strip() == "/":
            return ""
        return str(text).strip()

    cp = _clean(counterparty)
    prod = _clean(product)
    pm = _clean(payment_method)
    src = _clean(source)
    tt = _clean(trade_type)

    parts = [cp] if cp else []
    if prod and prod != cp:
        parts.append(prod)
    if pm:
        parts.append(pm)
    if tt:
        parts.append(tt)
    if src:
        parts.append(f"src_{src}")
    if cp and cp not in parts[1:]:
        parts.insert(0, cp)

    return " ".join(parts)


def _load_artifacts() -> dict[str, Any]:
    """加载所有模型工件；若磁盘文件已更新则自动刷新缓存。缺失时返回空字典。"""
    global _ARTIFACTS, _ARTIFACTS_MTIME

    current_mtime = _get_max_mtime()
    if _ARTIFACTS and current_mtime <= _ARTIFACTS_MTIME:
        return _ARTIFACTS

    required = {
        "tfidf_vectorizer": MODEL_DIR / "tfidf_vectorizer.pkl",
        "major_classifier": MODEL_DIR / "major_classifier.pkl",
        "major_label_encoder": MODEL_DIR / "major_label_encoder.pkl",
        "sub_classifiers": MODEL_DIR / "sub_classifiers.pkl",
        "sub_label_encoders": MODEL_DIR / "sub_label_encoders.pkl",
        "major_sub_map": MODEL_DIR / "major_sub_map.json",
        "fallback_sub": MODEL_DIR / "fallback_sub.json",
    }

    artifacts = {}
    for name, path in required.items():
        if not path.exists():
            log.warning(f"模型工件缺失: {path}")
            return {}
        try:
            if path.suffix == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    artifacts[name] = json.load(f)
            else:
                artifacts[name] = joblib.load(path)
        except Exception as e:
            log.warning(f"加载模型失败 {path}: {e}")
            return {}

    _ARTIFACTS = artifacts
    _ARTIFACTS_MTIME = current_mtime
    log.info(f"模型加载完成: {MODEL_DIR}")
    return artifacts


def predict_categories(records: list[dict]) -> list[tuple[str, str]]:
    """
    对记录列表预测 Major / Sub 分类。

    返回: [(major, sub), ...]
    如果模型未加载成功，返回全空字符串。
    """
    artifacts = _load_artifacts()
    if not artifacts:
        return [("", "")] * len(records)

    texts = []
    for r in records:
        raw_data = r.get("raw_data") or {}
        if isinstance(raw_data, str):
            import json as _json
            try:
                raw_data = _json.loads(raw_data)
            except Exception:
                raw_data = {}
        trade_type = raw_data.get("交易类型", "") if isinstance(raw_data, dict) else ""
        texts.append(_build_text(
            r.get("counterparty"),
            r.get("product"),
            r.get("payment_method"),
            r.get("source"),
            trade_type,
        ))

    tfidf = artifacts["tfidf_vectorizer"]
    X = tfidf.transform(texts)

    major_clf = artifacts["major_classifier"]
    major_le = artifacts["major_label_encoder"]
    major_pred = major_clf.predict(X)
    major_labels = major_le.inverse_transform(major_pred)

    sub_classifiers = artifacts["sub_classifiers"]
    sub_encoders = artifacts["sub_label_encoders"]
    fallback_sub = artifacts["fallback_sub"]
    major_sub_map = artifacts["major_sub_map"]

    results = []
    for i, major in enumerate(major_labels):
        major = str(major).strip()
        sub_clf = sub_classifiers.get(major)
        sub_le = sub_encoders.get(major)

        sub = fallback_sub.get(major, "")
        if sub_clf is not None and sub_le is not None:
            try:
                sub_pred = sub_clf.predict(X[i])
                candidate = str(sub_le.inverse_transform(sub_pred)[0]).strip()
                # 双重保险：预测的 sub 必须在 major 的合法 sub 列表中
                if candidate in major_sub_map.get(major, []):
                    sub = candidate
                else:
                    log.debug(f"预测 sub {candidate} 不在 {major} 的合法列表中，使用 fallback")
            except Exception as e:
                log.warning(f"Sub 预测失败 ({major}): {e}")

        results.append((major, sub))

    return results
