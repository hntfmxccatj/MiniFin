"""账单解析核心模块

剥离自 parse_bills.py 的解析逻辑，可被后端 API 和命令行脚本共同使用。
"""
import hashlib
import json
import logging
import os
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "wallet.db"
TABLE_NAME = "bills"

log = logging.getLogger("parser")


def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def safe_float(value) -> float:
    """安全地将字符串转为 float，去除 ¥ 符号、千分位逗号"""
    if isinstance(value, (int, float)):
        return float(value)
    if pd.isna(value):
        return 0.0
    s = str(value).strip().replace("¥", "").replace(",", "").replace("+", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def safe_str(value) -> str:
    """将值转为 str，NaN 返回空字符串"""
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def normalize_trade_time(raw: str) -> str:
    """将交易时间统一为 YYYY-MM-DD HH:MM:SS"""
    raw = raw.strip()
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
    ]:
        try:
            return pd.to_datetime(raw, format=fmt).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            continue
    try:
        return pd.to_datetime(raw).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        log.warning(f"  无法解析交易时间: {raw!r}")
        return raw


def generate_id(trade_time: str, amount: float, counterparty: str) -> str:
    """生成统一主键: MD5(trade_time + str(amount) + counterparty)"""
    raw = f"{trade_time}{amount:.6f}{counterparty}"
    return md5(raw)


# ══════════════════════════════════════════════════════════════════════
#  文件类型识别
# ══════════════════════════════════════════════════════════════════════

def _peek_file_head(filepath: str) -> str:
    """读取文件前 60 行用于类型识别，尝试常见编码"""
    for enc in ["gbk", "gb18030", "utf-8", "utf-8-sig"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return "".join(f.readline() for _ in range(60))
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return ""


def is_wechat_csv(filepath: str) -> bool:
    fname = os.path.basename(filepath).lower()
    if "微信" in fname or "wechat" in fname:
        return True
    head = _peek_file_head(filepath)
    return "微信支付账单" in head or "微信" in head


def is_alipay_csv(filepath: str) -> bool:
    fname = os.path.basename(filepath).lower()
    if "支付宝" in fname or "alipay" in fname:
        return True
    head = _peek_file_head(filepath)
    return "支付宝账户" in head or "支付宝" in head


def find_bill_files(path: str) -> dict:
    """
    输入路径可以是文件也可以是文件夹。
    返回 {"wechat": [file1, ...], "alipay": [...], "unknown": [...]}
    """
    result = {"wechat": [], "alipay": [], "unknown": []}

    if os.path.isfile(path):
        if is_wechat_csv(path):
            result["wechat"].append(path)
        elif is_alipay_csv(path):
            result["alipay"].append(path)
        else:
            result["unknown"].append(path)
        return result

    if not os.path.isdir(path):
        return result

    csv_files = sorted(
        [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(".csv")]
    )
    for fp in csv_files:
        if is_wechat_csv(fp):
            result["wechat"].append(fp)
        elif is_alipay_csv(fp):
            result["alipay"].append(fp)
        else:
            result["unknown"].append(fp)

    return result


# ══════════════════════════════════════════════════════════════════════
#  微信账单解析
# ══════════════════════════════════════════════════════════════════════

WECHAT_INTERNAL_TRANSFER_TYPES = {
    "零钱提现", "转入零钱通", "零钱充值", "转账-退回到零钱",
}
WECHAT_INTERNAL_TRANSFER_KEYWORDS = ["零钱通"]


def find_wechat_header_line(filepath: str) -> tuple:
    """返回 (skip_rows, encoding)"""
    encodings_to_try = ["utf-8", "utf-8-sig", "gbk", "gb18030"]
    header_keywords = "交易时间"

    for enc in encodings_to_try:
        try:
            with open(filepath, "r", encoding=enc) as f:
                for idx, line in enumerate(f):
                    if line.startswith(header_keywords):
                        return idx, enc
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    raise ValueError(f"无法在文件 {filepath} 中找到微信账单表头行")


def parse_wechat(filepath: str, self_name: str = "") -> pd.DataFrame:
    """解析微信支付账单 CSV，返回 DataFrame"""
    log.info(f"解析微信账单: {filepath}")

    skip_rows, encoding = find_wechat_header_line(filepath)
    df = pd.read_csv(filepath, encoding=encoding, skiprows=skip_rows, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    log.info(f"  读取 {len(df)} 行原始记录，列: {list(df.columns)}")

    # 过滤资产内部划转
    if "交易类型" in df.columns:
        mask_tt = df["交易类型"].apply(lambda x: safe_str(x) in WECHAT_INTERNAL_TRANSFER_TYPES)
        df = df[~mask_tt]
    if "交易对方" in df.columns:
        mask_cp = df["交易对方"].apply(
            lambda x: any(kw in safe_str(x) for kw in WECHAT_INTERNAL_TRANSFER_KEYWORDS)
        )
        if self_name:
            mask_self = df["交易对方"].apply(lambda x: self_name in safe_str(x))
            mask_cp = mask_cp | mask_self
        df = df[~mask_cp]

    records = []
    skip_count = 0
    for _, row in df.iterrows():
        if row.isna().all():
            continue

        raw_id = safe_str(row.get("交易单号", ""))
        trade_time_str = safe_str(row.get("交易时间", ""))
        counterparty = safe_str(row.get("交易对方", ""))
        product = safe_str(row.get("商品", ""))
        payment_method = safe_str(row.get("支付方式", ""))
        amount_raw = safe_str(row.get("金额(元)", ""))
        trade_type = safe_str(row.get("交易类型", ""))
        income_expense = safe_str(row.get("收/支", ""))

        if not trade_time_str:
            skip_count += 1
            continue

        trade_time = normalize_trade_time(trade_time_str)
        amount = safe_float(amount_raw)

        is_refund = "退款" in trade_type or "退款" in product
        if income_expense == "支出":
            bill_type = "EXPENSE"
            amount = -abs(amount)
        elif income_expense == "收入":
            if is_refund:
                bill_type = "REFUND"
                amount = abs(amount)
            else:
                bill_type = "INCOME"
                amount = abs(amount)
        else:
            bill_type = "EXPENSE"
            amount = -abs(amount)

        if is_refund and amount < 0:
            amount = abs(amount)

        bill_id = generate_id(trade_time, amount, counterparty)
        raw_data = json.dumps(row.to_dict(), ensure_ascii=False, default=str)

        records.append({
            "id": bill_id,
            "source": "WECHAT",
            "raw_id": raw_id,
            "trade_time": trade_time,
            "amount": amount,
            "type": bill_type,
            "major_category": "",
            "sub_category": "",
            "counterparty": counterparty,
            "product": product,
            "payment_method": payment_method,
            "raw_data": raw_data,
        })

    log.info(f"  解析完成: {len(records)} 条有效记录")
    return pd.DataFrame(records)


# ══════════════════════════════════════════════════════════════════════
#  支付宝账单解析
# ══════════════════════════════════════════════════════════════════════

ALIPAY_INTERNAL_STATUS = {"资金转移", "信用还款", "还款成功"}


def find_alipay_header_line(filepath: str) -> tuple:
    """返回 (skip_rows, encoding)"""
    encodings_to_try = ["gbk", "gb18030", "utf-8", "utf-8-sig"]
    header_keyword = "交易时间"

    for enc in encodings_to_try:
        try:
            with open(filepath, "r", encoding=enc) as f:
                for idx, line in enumerate(f):
                    if line.startswith(header_keyword):
                        return idx, enc
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    raise ValueError(f"无法在文件 {filepath} 中找到支付宝账单表头行")


def parse_alipay(filepath: str) -> pd.DataFrame:
    """解析支付宝账单 CSV，返回 DataFrame"""
    log.info(f"解析支付宝账单: {filepath}")

    skip_rows, encoding = find_alipay_header_line(filepath)
    df = pd.read_csv(filepath, encoding=encoding, skiprows=skip_rows, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    log.info(f"  读取 {len(df)} 行原始记录，列: {list(df.columns)}")

    if "交易状态" in df.columns:
        mask_status = df["交易状态"].apply(lambda x: any(kw in safe_str(x) for kw in ALIPAY_INTERNAL_STATUS))
        df = df[~mask_status]

    if "收/支" in df.columns and "交易状态" in df.columns:
        is_refund_row = df["交易状态"].apply(lambda x: "退款" in safe_str(x))
        mask_no_account = df["收/支"].apply(lambda x: safe_str(x) == "不计收支")
        df = df[~(mask_no_account & ~is_refund_row)]

    if "交易时间" in df.columns:
        valid_idx = df["交易时间"].apply(lambda x: bool(safe_str(x)))
        try:
            last_valid = valid_idx[valid_idx].index[-1]
            df = df.loc[:last_valid]
        except IndexError:
            pass

    records = []
    skip_count = 0
    for _, row in df.iterrows():
        if row.isna().all():
            continue

        raw_id = safe_str(row.get("交易订单号", row.get("交易号", "")))
        trade_time_str = safe_str(row.get("交易时间", ""))
        counterparty = safe_str(row.get("交易对方", ""))
        product = safe_str(row.get("商品说明", row.get("商品名称", row.get("商品", ""))))
        amount_str = safe_str(row.get("金额", ""))
        trade_status = safe_str(row.get("交易状态", ""))
        income_expense = safe_str(row.get("收/支", ""))
        trade_category = safe_str(row.get("交易分类", ""))
        payment_method = safe_str(row.get("收/付款方式", row.get("支付方式", "")))

        if not trade_time_str:
            skip_count += 1
            continue

        trade_time = normalize_trade_time(trade_time_str)
        amount = safe_float(amount_str)

        is_refund = (
            "退款成功" in trade_status
            or "相关消费已退款" in trade_status
            or ("交易关闭" == trade_status and trade_category == "退款")
            or trade_category == "退款"
        )

        if is_refund:
            bill_type = "REFUND"
            amount = abs(amount)
        elif income_expense == "支出":
            bill_type = "EXPENSE"
            amount = -abs(amount)
        elif income_expense == "收入":
            bill_type = "INCOME"
            amount = abs(amount)
        else:
            bill_type = "EXPENSE"
            amount = -abs(amount)

        bill_id = generate_id(trade_time, amount, counterparty)
        raw_data = json.dumps(row.to_dict(), ensure_ascii=False, default=str)

        records.append({
            "id": bill_id,
            "source": "ALIPAY",
            "raw_id": raw_id,
            "trade_time": trade_time,
            "amount": amount,
            "type": bill_type,
            "major_category": "",
            "sub_category": "",
            "counterparty": counterparty,
            "product": product,
            "payment_method": payment_method,
            "raw_data": raw_data,
        })

    log.info(f"  解析完成: {len(records)} 条有效记录")
    return pd.DataFrame(records)


# ══════════════════════════════════════════════════════════════════════
#  解析入口
# ══════════════════════════════════════════════════════════════════════

def parse_files(path: str, self_name: str = "") -> pd.DataFrame:
    """解析一个文件或一个目录下的所有微信/支付宝 CSV，返回合并后的 DataFrame"""
    found = find_bill_files(path)
    dfs = []

    for fp in found["wechat"]:
        dfs.append(parse_wechat(fp, self_name=self_name))
    for fp in found["alipay"]:
        dfs.append(parse_alipay(fp))

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)


# ══════════════════════════════════════════════════════════════════════
#  数据库写入
# ══════════════════════════════════════════════════════════════════════

def ensure_table(conn: sqlite3.Connection):
    """确保 bills 表存在，不存在则创建"""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id              TEXT PRIMARY KEY,
            source          TEXT,
            raw_id          TEXT,
            trade_time      TEXT,
            amount          REAL,
            type            TEXT,
            major_category  TEXT,
            sub_category    TEXT,
            counterparty    TEXT,
            product         TEXT,
            payment_method  TEXT,
            raw_data        TEXT
        )
    """)
    conn.commit()


def insert_to_db(df: pd.DataFrame, conn: sqlite3.Connection) -> dict:
    """将 DataFrame 写入 SQLite，使用 INSERT OR IGNORE 基于 id 去重"""
    if df.empty:
        return {"total": 0, "inserted": 0, "skipped_duplicate": 0}

    columns = [
        "id", "source", "raw_id", "trade_time", "amount", "type",
        "major_category", "sub_category", "counterparty", "product",
        "payment_method", "raw_data",
    ]
    df = df[columns]

    total = len(df)
    cursor = conn.cursor()
    inserted = 0
    skipped = 0

    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT OR IGNORE INTO {TABLE_NAME} ({', '.join(columns)}) VALUES ({placeholders})"

    for _, row in df.iterrows():
        values = [row[col] for col in columns]
        try:
            cursor.execute(sql, values)
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except sqlite3.Error as e:
            log.warning(f"  写入失败: {e} | {row.to_dict()}")

    conn.commit()
    return {"total": total, "inserted": inserted, "skipped_duplicate": skipped}
