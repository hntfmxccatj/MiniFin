"""
账单解析与入库脚本

功能：
  - 读取微信支付 / 支付宝导出的原始 CSV 账单文件
  - 完成清洗、规范化、去重
  - 写入本地 SQLite 数据库 wallet.db 的 bills 表

用法：
  1. 激活 venv 后，安装依赖：pip install pandas
  2. 将微信和支付宝 CSV 文件放在当前目录
  3. 运行时指定文件路径：
     python parse_bills.py --wechat 微信账单.csv
     python parse_bills.py --alipay 支付宝账单.csv
     python parse_bills.py --wechat WX.csv --alipay ALIPAY.csv
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

# ────────── 基础配置 ──────────
DB_PATH = Path(__file__).parent / "wallet.db"
TABLE_NAME = "bills"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("parse_bills")


# ══════════════════════════════════════════════════════════════════════
#  辅助函数
# ══════════════════════════════════════════════════════════════════════

def md5(text: str) -> str:
    """返回字符串的 MD5 十六进制摘要"""
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
    """
    将交易时间统一为 "YYYY-MM-DD HH:MM:SS"
    常见输入格式：
      - 2024-01-15 14:30:25
      - 2024/01/15 14:30:25
      - 2024-01-15 14:30
    """
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
    # 兜底：让 pandas 自动推断
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
#  文件夹扫描 & 文件类型识别
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
    """通过文件名或文件内容判断是否为微信账单 CSV"""
    fname = os.path.basename(filepath).lower()
    if "微信" in fname or "wechat" in fname:
        return True
    head = _peek_file_head(filepath)
    return "微信支付账单" in head or "微信" in head


def is_alipay_csv(filepath: str) -> bool:
    """通过文件名或文件内容判断是否为支付宝账单 CSV"""
    fname = os.path.basename(filepath).lower()
    if "支付宝" in fname or "alipay" in fname:
        return True
    head = _peek_file_head(filepath)
    return "支付宝账户" in head or "支付宝" in head


def find_bill_files(path: str) -> dict:
    """
    输入路径可以是文件也可以是文件夹。
    返回 {"wechat": [file1, file2, ...], "alipay": [...]}
    """
    result = {"wechat": [], "alipay": []}

    if os.path.isfile(path):
        # 单文件：通过内容判断类型
        if is_wechat_csv(path):
            result["wechat"].append(path)
        elif is_alipay_csv(path):
            result["alipay"].append(path)
        else:
            log.warning(f"  无法识别文件类型: {path}")
        return result

    if not os.path.isdir(path):
        log.error(f"路径不存在: {path}")
        return result

    # 文件夹：扫描所有 CSV 文件
    csv_files = sorted(
        [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(".csv")]
    )
    if not csv_files:
        log.warning(f"  文件夹中没有 CSV 文件: {path}")
        return result

    for fp in csv_files:
        if is_wechat_csv(fp):
            result["wechat"].append(fp)
        elif is_alipay_csv(fp):
            result["alipay"].append(fp)
        else:
            log.warning(f"  跳过无法识别的文件: {os.path.basename(fp)}")

    return result


# ══════════════════════════════════════════════════════════════════════
#  微信账单解析
# ══════════════════════════════════════════════════════════════════════

# 资产内部划转 —— 交易类型或其他特征匹配时丢弃
WECHAT_INTERNAL_TRANSFER_TYPES = {
    "零钱提现", "转入零钱通", "零钱充值", "转账-退回到零钱",
}

WECHAT_INTERNAL_TRANSFER_KEYWORDS = ["零钱通"]

# 声明为自己姓名的，在解析时可通过运行参数传入
# 这里只做关键字模糊匹配


def find_wechat_header_line(filepath: str) -> int:
    """
    动态查找微信 CSV 真正的表头行。
    微信账单 CSV 开头有若干统计说明行，真正表头以 '交易时间,交易类型,交易对方' 开头。
    返回表头所在行号（0-based）。
    """
    encodings_to_try = ["utf-8", "utf-8-sig", "gbk", "gb18030"]
    header_keywords = "交易时间"

    for enc in encodings_to_try:
        try:
            with open(filepath, "r", encoding=enc) as f:
                for idx, line in enumerate(f):
                    if line.startswith(header_keywords):
                        log.info(f"  微信表头位于第 {idx} 行，编码: {enc}")
                        return idx, enc
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    raise ValueError(f"无法在文件 {filepath} 中找到微信账单表头行")


def parse_wechat(filepath: str, self_name: str = "") -> pd.DataFrame:
    """
    解析微信支付账单 CSV，返回清洗后的 DataFrame（字段与 bills 表对齐）。
    """
    log.info(f"解析微信账单: {filepath}")

    skip_rows, encoding = find_wechat_header_line(filepath)

    # 读取 CSV，跳过表头之前的说明行
    df = pd.read_csv(
        filepath,
        encoding=encoding,
        skiprows=skip_rows,
        dtype=str,
    )

    # 统一列名（去除首尾空格，统一键名）
    df.columns = [c.strip() for c in df.columns]
    log.info(f"  读取 {len(df)} 行原始记录，列: {list(df.columns)}")

    # ---------- 过滤：资产内部划转 ----------
    # 规则 a: 交易类型命中
    if "交易类型" in df.columns:
        mask_tt = df["交易类型"].apply(
            lambda x: safe_str(x) in WECHAT_INTERNAL_TRANSFER_TYPES
        )
        df = df[~mask_tt]
        log.info(f"  过滤交易类型内部划转，剩余 {len(df)} 行")

    # 规则 a2: 交易对手包含零钱通 或 用户自身姓名
    if "交易对方" in df.columns:
        # 零钱通
        mask_cp = df["交易对方"].apply(
            lambda x: any(kw in safe_str(x) for kw in WECHAT_INTERNAL_TRANSFER_KEYWORDS)
        )
        # 自身姓名（如果指定了）
        if self_name:
            mask_self = df["交易对方"].apply(lambda x: self_name in safe_str(x))
            mask_cp = mask_cp | mask_self
        df = df[~mask_cp]
        log.info(f"  过滤交易对手内部划转，剩余 {len(df)} 行")

    # ---------- 字段映射 ----------
    records = []
    skip_count = 0

    for _, row in df.iterrows():
        # 如果整行都为空，跳过
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

        # 跳过空交易时间、空交易对手的行（可能是汇总行）
        if not trade_time_str:
            skip_count += 1
            continue

        trade_time = normalize_trade_time(trade_time_str)
        amount = safe_float(amount_raw)

        # ---------- 收支类型 & 金额符号 ----------
        # 退款判断优先级最高
        is_refund = False
        if "退款" in trade_type or ("退款" in product) or ("退款" in income_expense and income_expense == "收入"):
            # 需要细分辨别：如果是收入且带退款标记，则为退款
            if "退款" in trade_type or "退款" in product:
                is_refund = True
            elif income_expense == "收入" and "退款" in trade_type:
                is_refund = True
            elif income_expense == "支出" and "退款" in trade_type:
                # 退款的对方视角，类型还是支出
                is_refund = False

        # 更精确的退款判定
        if "退款" in trade_type:
            is_refund = True

        if income_expense == "支出":
            bill_type = "EXPENSE"
            amount = -abs(amount)  # 消费强制负数
        elif income_expense == "收入":
            if is_refund:
                bill_type = "REFUND"
                amount = abs(amount)  # 退款强制正数
            else:
                bill_type = "INCOME"
                amount = abs(amount)  # 收入保持正数
        else:
            # 无法判定收支方向，默认支出
            bill_type = "EXPENSE"
            amount = -abs(amount)

        # 回补：如果类型已标记为退款但金额为负数，纠正为正
        if is_refund and amount < 0:
            amount = abs(amount)

        # 生成唯一 ID
        bill_id = generate_id(trade_time, amount, counterparty)

        # 原始数据快照
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

    log.info(f"  解析完成: {len(records)} 条有效记录 (跳过空行 {skip_count} 行)")
    return pd.DataFrame(records)


# ══════════════════════════════════════════════════════════════════════
#  支付宝账单解析
# ══════════════════════════════════════════════════════════════════════

ALIPAY_INTERNAL_STATUS = {"资金转移", "信用还款", "还款成功"}


def find_alipay_header_line(filepath: str):
    """
    动态查找支付宝 CSV 真正的表头行。
    支付宝 CSV 表头以 '交易时间' 开头，列如：交易时间,交易分类,交易对方,...
    """
    encodings_to_try = ["gbk", "gb18030", "utf-8", "utf-8-sig"]
    header_keyword = "交易时间"

    for enc in encodings_to_try:
        try:
            with open(filepath, "r", encoding=enc) as f:
                for idx, line in enumerate(f):
                    if line.startswith(header_keyword):
                        log.info(f"  支付宝表头位于第 {idx} 行，编码: {enc}")
                        return idx, enc
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    raise ValueError(f"无法在文件 {filepath} 中找到支付宝账单表头行")


def parse_alipay(filepath: str) -> pd.DataFrame:
    """
    解析支付宝账单 CSV，返回清洗后的 DataFrame。
    """
    log.info(f"解析支付宝账单: {filepath}")

    skip_rows, encoding = find_alipay_header_line(filepath)

    # 读取 CSV（支付宝 CSV 用逗号分隔，但有 \t 出现在字段值中，pandas 可正常处理）
    df = pd.read_csv(
        filepath,
        encoding=encoding,
        skiprows=skip_rows,
        dtype=str,
    )

    df.columns = [c.strip() for c in df.columns]
    log.info(f"  读取 {len(df)} 行原始记录，列: {list(df.columns)}")

    # ---------- 过滤：内部划转 ----------
    # 规则: 交易状态 含 '资金转移'、'信用还款'
    if "交易状态" in df.columns:
        mask_status = df["交易状态"].apply(
            lambda x: any(kw in safe_str(x) for kw in ALIPAY_INTERNAL_STATUS)
        )
        before = len(df)
        df = df[~mask_status]
        log.info(f"  过滤交易状态内部划转: {before} -> {len(df)} 行")

    # 规则: 收/支='不计收支'，但保留退款记录（支付宝退款收/支也为不计收支）
    if "收/支" in df.columns:
        is_refund_row = df["交易状态"].apply(lambda x: "退款" in safe_str(x))
        mask_no_account = df["收/支"].apply(lambda x: safe_str(x) == "不计收支")
        # 剔除不计收支但保留退款
        mask_filter = mask_no_account & ~is_refund_row
        before = len(df)
        df = df[~mask_filter]
        log.info(f"  过滤不计收支（保留退款）: {before} -> {len(df)} 行")

    # 切除尾部汇总行：最后一个有效交易时间之后的行
    if "交易时间" in df.columns:
        valid_idx = df["交易时间"].apply(lambda x: bool(safe_str(x)))
        try:
            last_valid = valid_idx[valid_idx].index[-1]
            df = df.loc[:last_valid]
            log.info(f"  切除尾部汇总行，截取到第 {last_valid} 行")
        except IndexError:
            pass

    # ---------- 字段映射 ----------
    records = []
    skip_count = 0

    for _, row in df.iterrows():
        if row.isna().all():
            continue

        # 实际支付宝列名映射
        raw_id = safe_str(row.get("交易订单号", row.get("交易号", "")))
        trade_time_str = safe_str(row.get("交易时间", ""))
        counterparty = safe_str(row.get("交易对方", ""))
        product = safe_str(row.get("商品说明", row.get("商品名称", row.get("商品", ""))))
        amount_str = safe_str(row.get("金额", ""))
        trade_status = safe_str(row.get("交易状态", ""))
        income_expense = safe_str(row.get("收/支", ""))
        trade_category = safe_str(row.get("交易分类", ""))  # 支付宝自带分类
        payment_method = safe_str(row.get("收/付款方式", row.get("支付方式", "")))

        if not trade_time_str:
            skip_count += 1
            continue

        trade_time = normalize_trade_time(trade_time_str)
        amount = safe_float(amount_str)

        # ---------- 收支类型 & 金额符号 ----------
        # 退款判定（优先）：交易状态含退款字样 或 交易分类为退款
        is_refund = False
        if "退款成功" in trade_status or "相关消费已退款" in trade_status or "交易关闭" == trade_status and trade_category == "退款":
            is_refund = True
        if trade_category == "退款":
            is_refund = True

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
            # 不明方向，默认为支出
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

    log.info(f"  解析完成: {len(records)} 条有效记录 (跳过空行 {skip_count} 行)")
    return pd.DataFrame(records)


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
    """
    将清洗后的 DataFrame 写入 SQLite。
    使用 INSERT OR IGNORE 基于主键 id 去重。
    返回统计信息。
    """
    if df.empty:
        return {"total": 0, "inserted": 0, "skipped_duplicate": 0}

    columns = [
        "id", "source", "raw_id", "trade_time", "amount", "type",
        "major_category", "sub_category", "counterparty", "product",
        "payment_method", "raw_data",
    ]

    # 确保列顺序一致
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

    return {
        "total": total,
        "inserted": inserted,
        "skipped_duplicate": skipped,
    }


# ══════════════════════════════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════════════════════════════

def interactive_mode():
    """交互模式：引导式输入，适合直接运行"""
    print("=" * 50)
    print("  账单解析与入库工具")
    print("=" * 50)
    print()
    print("请选择要解析的账单类型：")
    print("  [1] 微信支付")
    print("  [2] 支付宝")
    print("  [3] 两者都有")
    print()

    try:
        choice = input("请输入选项 (1/2/3): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        sys.exit(0)

    if choice not in ("1", "2", "3"):
        print("无效选项，请输入 1、2 或 3")
        sys.exit(1)

    wechat_path = None
    alipay_path = None

    if choice in ("1", "3"):
        wechat_path = input("请输入微信账单 CSV 所在文件夹路径（或单个 CSV 文件路径）: ").strip().strip('"')
        if not wechat_path:
            print("未输入路径，跳过微信账单。")
            wechat_path = None

    if choice in ("2", "3"):
        alipay_path = input("请输入支付宝账单 CSV 所在文件夹路径（或单个 CSV 文件路径）: ").strip().strip('"')
        if not alipay_path:
            print("未输入路径，跳过支付宝账单。")
            alipay_path = None

    if not wechat_path and not alipay_path:
        print("没有指定任何路径，退出。")
        sys.exit(1)

    print()
    return wechat_path, alipay_path, "", False


def main():
    # 如果没有任何命令行参数，进入交互模式
    if len(sys.argv) == 1:
        wechat_path, alipay_path, self_name, dry_run = interactive_mode()
    else:
        parser = argparse.ArgumentParser(
            description="微信/支付宝账单解析与入库脚本",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
示例:
    python parse_bills.py --wechat  微信支付账单.csv
    python parse_bills.py --alipay  alipay_record.csv
    python parse_bills.py --wechat WX.csv --alipay ALIPAY.csv --self-name 张三

直接运行（不带参数）进入交互模式:
    python parse_bills.py
            """,
        )
        parser.add_argument("--wechat", type=str, default=None,
                            help="微信支付导出的 CSV 文件路径")
        parser.add_argument("--alipay", type=str, default=None,
                            help="支付宝导出的 CSV 文件路径")
        parser.add_argument("--self-name", type=str, default="",
                            help="你的姓名，用于过滤微信中与自身姓名相关的内部划转交易")
        parser.add_argument("--dry-run", action="store_true",
                            help="仅解析预览，不写入数据库")
        parser.add_argument("--no-dedup", action="store_true",
                            help="不做去重，允许重复写入（忽略主键冲突）")

        args = parser.parse_args()

        if not args.wechat and not args.alipay:
            parser.print_help()
            log.error("请至少指定一个账单文件: --wechat 或 --alipay")
            sys.exit(1)

        wechat_path = args.wechat
        alipay_path = args.alipay
        self_name = args.self_name
        dry_run = args.dry_run

    # 收集所有解析结果
    all_dfs = []

    # --- 微信 ---
    if wechat_path:
        found = find_bill_files(wechat_path)
        wx_files = found["wechat"]
        if not wx_files:
            log.warning(f"未找到微信账单文件: {wechat_path}")
        for fp in wx_files:
            df_wx = parse_wechat(fp, self_name=self_name)
            log.info(f"  微信 ({os.path.basename(fp)}): {len(df_wx)} 条 -> "
                     f"支出 {len(df_wx[df_wx['type']=='EXPENSE'])} | "
                     f"收入 {len(df_wx[df_wx['type']=='INCOME'])} | "
                     f"退款 {len(df_wx[df_wx['type']=='REFUND'])}")
            all_dfs.append(df_wx)

    # --- 支付宝 ---
    if alipay_path:
        found = find_bill_files(alipay_path)
        ali_files = found["alipay"]
        if not ali_files:
            log.warning(f"未找到支付宝账单文件: {alipay_path}")
        for fp in ali_files:
            df_ali = parse_alipay(fp)
            log.info(f"  支付宝 ({os.path.basename(fp)}): {len(df_ali)} 条 -> "
                     f"支出 {len(df_ali[df_ali['type']=='EXPENSE'])} | "
                     f"收入 {len(df_ali[df_ali['type']=='INCOME'])} | "
                     f"退款 {len(df_ali[df_ali['type']=='REFUND'])}")
            all_dfs.append(df_ali)

    if not all_dfs:
        log.error("没有解析到任何有效数据")
        sys.exit(1)

    # 合并
    final_df = pd.concat(all_dfs, ignore_index=True)
    log.info(f"合并后共 {len(final_df)} 条记录")

    if dry_run:
        log.info("=== 预览模式（不写入库）===")
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 200)
        pd.set_option("display.max_rows", 20)
        print(final_df.to_string(index=False))
        log.info(f"总计 {len(final_df)} 条记录")
        return

    # 写入 SQLite
    conn = sqlite3.connect(str(DB_PATH))
    try:
        ensure_table(conn)
        stats = insert_to_db(final_df, conn)
        log.info("=" * 50)
        log.info(f"入库完成: 本次解析 {stats['total']} 条, "
                 f"新写入 {stats['inserted']} 条, "
                 f"跳过重复 {stats['skipped_duplicate']} 条")

        # 汇总统计
        total_bills = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
        log.info(f"数据库中 bills 表当前共 {total_bills} 条记录")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
