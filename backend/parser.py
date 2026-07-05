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
#  支出-退款配对去除
# ══════════════════════════════════════════════════════════════════════

import re
from datetime import datetime


def _normalize_product_for_pairing(product: str) -> str:
    """去除商品名中的退款前缀，用于配对比较。"""
    p = safe_str(product)
    for prefix in ["退款-", "退款"]:
        if p.startswith(prefix):
            p = p[len(prefix):]
    return p.strip()


def _extract_order_number(product: str) -> str | None:
    """从商品名中提取 15 位以上的订单号。"""
    m = re.search(r"\d{15,}", safe_str(product))
    return m.group(0) if m else None


def _records_form_refund_pair(expense: pd.Series, refund: pd.Series, max_days: int = 7) -> bool:
    """判断一笔 EXPENSE 和一笔 REFUND 是否为同一订单的成对记录。"""
    if expense.get("source") != refund.get("source"):
        return False
    if abs(safe_float(expense.get("amount", 0))) != abs(safe_float(refund.get("amount", 0))):
        return False

    exp_time = safe_str(expense.get("trade_time", ""))
    ref_time = safe_str(refund.get("trade_time", ""))
    if not exp_time or not ref_time:
        return False
    try:
        exp_dt = datetime.strptime(exp_time, "%Y-%m-%d %H:%M:%S")
        ref_dt = datetime.strptime(ref_time, "%Y-%m-%d %H:%M:%S")
        if abs((ref_dt - exp_dt).total_seconds()) > max_days * 24 * 3600:
            return False
    except Exception:
        return False

    exp_cp = safe_str(expense.get("counterparty", ""))
    ref_cp = safe_str(refund.get("counterparty", ""))
    cp_match = ref_cp == exp_cp or ref_cp in ("/", "")
    if not cp_match:
        return False

    exp_product = _normalize_product_for_pairing(expense.get("product", ""))
    ref_product = _normalize_product_for_pairing(refund.get("product", ""))
    exp_order = _extract_order_number(exp_product)
    ref_order = _extract_order_number(ref_product)

    product_match = (
        exp_product == ref_product
        or (exp_order and ref_order and exp_order == ref_order)
        or (exp_order and exp_order in safe_str(refund.get("product", "")))
        or (ref_order and ref_order in safe_str(expense.get("product", "")))
    )
    return product_match


def remove_refund_pairs(df: pd.DataFrame, max_days: int = 7) -> pd.DataFrame:
    """
    从解析后的账单中去除成对的支出+退款记录。
    用户不需要保留已全额退款的交易痕迹。
    """
    if df.empty:
        return df

    df = df.reset_index(drop=True)
    expenses = df[df["type"] == "EXPENSE"].copy()
    refunds = df[df["type"] == "REFUND"].copy()
    if expenses.empty or refunds.empty:
        return df

    drop_indices = set()
    used_refund_indices = set()

    for exp_idx, exp in expenses.iterrows():
        for ref_idx, ref in refunds.iterrows():
            if ref_idx in used_refund_indices:
                continue
            if _records_form_refund_pair(exp, ref, max_days=max_days):
                drop_indices.add(exp_idx)
                drop_indices.add(ref_idx)
                used_refund_indices.add(ref_idx)
                break

    if drop_indices:
        log.info(f"  去除 {len(drop_indices) // 2} 对支出+退款记录")
        df = df.drop(index=list(drop_indices)).reset_index(drop=True)
    return df


# ══════════════════════════════════════════════════════════════════════
#  文件类型识别
# ══════════════════════════════════════════════════════════════════════

def _peek_file_head(filepath: str) -> str:
    """读取文本文件前 60 行用于类型识别，尝试常见编码"""
    for enc in ["gbk", "gb18030", "utf-8", "utf-8-sig"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return "".join(f.readline() for _ in range(60))
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return ""


def _peek_excel_head(filepath: str, nrows: int = 20) -> str:
    """读取 Excel 文件前 nrows 行并拼接成字符串，用于类型识别"""
    try:
        df = pd.read_excel(filepath, header=None, nrows=nrows, dtype=str)
        return "\n".join(
            " ".join(safe_str(cell) for cell in row)
            for _, row in df.iterrows()
        )
    except Exception:
        return ""


def _is_excel(filepath: str) -> bool:
    return filepath.lower().endswith(".xlsx")


def is_wechat_csv(filepath: str) -> bool:
    fname = os.path.basename(filepath).lower()
    if "微信" in fname or "wechat" in fname:
        return True
    head = _peek_excel_head(filepath) if _is_excel(filepath) else _peek_file_head(filepath)
    return "微信支付账单" in head or "微信" in head


def is_alipay_csv(filepath: str) -> bool:
    fname = os.path.basename(filepath).lower()
    if "支付宝" in fname or "alipay" in fname:
        return True
    head = _peek_excel_head(filepath) if _is_excel(filepath) else _peek_file_head(filepath)
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

    bill_files = sorted(
        [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith((".csv", ".xlsx"))]
    )
    for fp in bill_files:
        if is_wechat_csv(fp):
            result["wechat"].append(fp)
        elif is_alipay_csv(fp):
            result["alipay"].append(fp)
        else:
            result["unknown"].append(fp)

    return result


def read_bill_file(filepath: str) -> pd.DataFrame:
    """读取 csv / xlsx 账单文件，自动定位表头行，返回 DataFrame（字符串类型）"""
    header_keyword = "交易时间"
    ext = Path(filepath).suffix.lower()

    if ext == ".xlsx":
        df_raw = pd.read_excel(filepath, header=None, dtype=str)
        header_row = None
        for idx, row in df_raw.iterrows():
            if any(header_keyword in safe_str(cell) for cell in row):
                header_row = idx
                break
        if header_row is None:
            raise ValueError(f"无法在 Excel 文件 {filepath} 中找到账单表头行")
        df = pd.read_excel(filepath, header=header_row, dtype=str)
    else:
        encodings_to_try = ["utf-8", "utf-8-sig", "gbk", "gb18030"]
        header_row = None
        encoding = None
        for enc in encodings_to_try:
            try:
                with open(filepath, "r", encoding=enc) as f:
                    for idx, line in enumerate(f):
                        if line.startswith(header_keyword):
                            header_row = idx
                            encoding = enc
                            break
                if header_row is not None:
                    break
            except (UnicodeDecodeError, FileNotFoundError):
                continue
        if header_row is None:
            raise ValueError(f"无法在文件 {filepath} 中找到账单表头行")
        df = pd.read_csv(filepath, encoding=encoding, skiprows=header_row, dtype=str)

    df.columns = [c.strip() for c in df.columns]
    return df


# ══════════════════════════════════════════════════════════════════════
#  微信账单解析
# ══════════════════════════════════════════════════════════════════════

WECHAT_INTERNAL_TRANSFER_KEYWORDS = [
    "零钱通", "零钱提现", "零钱充值", "退回到零钱", "信用卡还款"
]


def _is_wechat_internal_transfer(row: pd.Series) -> bool:
    """判断微信记录是否为账户内部资金划转，不应计入真实收支。"""
    trade_type = safe_str(row.get("交易类型", ""))
    if any(kw in trade_type for kw in WECHAT_INTERNAL_TRANSFER_KEYWORDS):
        return True
    # 收/支为 "/" 通常表示微信内部流水（如转入零钱通），且交易对方和商品均为 "/"
    income_expense = safe_str(row.get("收/支", ""))
    counterparty = safe_str(row.get("交易对方", ""))
    product = safe_str(row.get("商品", ""))
    if income_expense == "/" and counterparty == "/" and product == "/":
        return True
    return False


def parse_wechat(filepath: str, self_name: str = "") -> pd.DataFrame:
    """解析微信支付账单 CSV / XLSX，返回 DataFrame"""
    log.info(f"解析微信账单: {filepath}")

    df = read_bill_file(filepath)
    log.info(f"  读取 {len(df)} 行原始记录，列: {list(df.columns)}")

    # 过滤资产内部划转
    if not df.empty:
        mask_internal = df.apply(_is_wechat_internal_transfer, axis=1)
        internal_count = mask_internal.sum()
        if internal_count:
            log.info(f"  过滤 {int(internal_count)} 条微信内部资金划转记录")
        df = df[~mask_internal]

    # 过滤与自身姓名的转账（可选）
    if self_name and "交易对方" in df.columns:
        mask_self = df["交易对方"].apply(lambda x: self_name in safe_str(x))
        df = df[~mask_self]

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


def parse_alipay(filepath: str) -> pd.DataFrame:
    """解析支付宝账单 CSV / XLSX，返回 DataFrame"""
    log.info(f"解析支付宝账单: {filepath}")

    df = read_bill_file(filepath)
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

    df = pd.concat(dfs, ignore_index=True)
    # 去除同一次上传中的成对支出+退款记录
    df = remove_refund_pairs(df)
    return df


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


def _remove_existing_expense_for_refund(refund: pd.Series, cursor: sqlite3.Cursor) -> int:
    """
    如果数据库中已存在与这笔退款对应的支出记录，则删除该支出记录。
    返回删除的记录数。
    """
    if refund.get("type") != "REFUND":
        return 0

    amount = abs(safe_float(refund.get("amount", 0)))
    source = safe_str(refund.get("source", ""))
    trade_time = safe_str(refund.get("trade_time", ""))
    counterparty = safe_str(refund.get("counterparty", ""))
    product = safe_str(refund.get("product", ""))
    product_norm = _normalize_product_for_pairing(product)
    order_number = _extract_order_number(product)

    if not amount or not source or not trade_time:
        return 0

    # 查询候选支出记录：同来源、同金额绝对值、时间前后 7 天内
    cursor.execute(
        """
        SELECT id, trade_time, counterparty, product
        FROM bills
        WHERE type = 'EXPENSE'
          AND source = ?
          AND ABS(amount) = ?
          AND trade_time BETWEEN datetime(?, '-7 days') AND datetime(?, '+7 days')
        """,
        (source, amount, trade_time, trade_time),
    )
    candidates = cursor.fetchall()

    deleted = 0
    for cid, ctime, ccp, cproduct in candidates:
        cproduct_norm = _normalize_product_for_pairing(cproduct)
        corder = _extract_order_number(cproduct)
        cp_match = counterparty in ("/", "") or ccp == counterparty
        product_match = (
            product_norm == cproduct_norm
            or (order_number and corder and order_number == corder)
            or (order_number and order_number in cproduct)
            or (corder and corder in product)
        )
        if cp_match and product_match:
            cursor.execute("DELETE FROM bills WHERE id = ?", (cid,))
            deleted += cursor.rowcount
            break
    return deleted


def insert_to_db(df: pd.DataFrame, conn: sqlite3.Connection) -> dict:
    """将 DataFrame 写入 SQLite，使用 INSERT OR IGNORE 基于 id 去重，并自动清理成对退款"""
    if df.empty:
        return {"total": 0, "inserted": 0, "skipped_duplicate": 0, "refund_pairs_removed": 0}

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
    refund_pairs_removed = 0

    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT OR IGNORE INTO {TABLE_NAME} ({', '.join(columns)}) VALUES ({placeholders})"

    for _, row in df.iterrows():
        # 如果是退款记录，先尝试删除数据库中对应的支出记录，并跳过插入该退款
        if row.get("type") == "REFUND":
            refund_pairs_removed += _remove_existing_expense_for_refund(row, cursor)
            continue

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
    return {
        "total": total,
        "inserted": inserted,
        "skipped_duplicate": skipped,
        "refund_pairs_removed": refund_pairs_removed,
    }
