"""
清洗 wallet.db 中被误判为支出的微信内部资金划转记录。

这些记录本身不是真实消费（如转入零钱通、零钱提现等），
在旧版 parser 中因为"收/支"字段为 "/" 而被错误标记为 EXPENSE。

用法：
    python -m db.cleanup_internal_transfers

默认仅预览，加 --apply 才会真正删除：
    python -m db.cleanup_internal_transfers --apply
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

# 兼容 Windows Git Bash / cmd 等默认 GBK 编码终端
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB = str(Path(__file__).parent.parent / "wallet.db")

# 微信资金划转类交易类型关键词
WECHAT_TRANSFER_KEYWORDS = [
    "零钱通",
    "零钱提现",
    "零钱充值",
    "退回到零钱",
    "信用卡还款",
]


def find_internal_transfer_records(conn):
    """找出微信中被误判为 EXPENSE 的资金划转记录。"""
    cur = conn.execute(
        "SELECT id, trade_time, amount, counterparty, product, raw_data "
        "FROM bills WHERE source = 'WECHAT' AND type = 'EXPENSE'"
    )
    to_delete = []
    for row in cur.fetchall():
        raw = json.loads(row["raw_data"])
        trade_type = raw.get("交易类型", "")
        income_expense = raw.get("收/支", "")
        # 交易类型命中资金划转关键词
        if any(kw in trade_type for kw in WECHAT_TRANSFER_KEYWORDS):
            to_delete.append(row)
            continue
        # 收/支为 "/" 且交易对方为 "/" 的异常记录，通常是微信内部流水
        if income_expense == "/" and row["counterparty"] == "/" and row["product"] == "/":
            to_delete.append(row)
    return to_delete


def main():
    parser = argparse.ArgumentParser(description="清洗微信内部资金划转误判记录")
    parser.add_argument("--apply", action="store_true", help="真正执行删除，默认仅预览")
    args = parser.parse_args()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        records = find_internal_transfer_records(conn)
        if not records:
            print("未发现需要清洗的微信资金划转误判记录。")
            return

        total_amount = sum(abs(r["amount"]) for r in records)
        print(f"发现 {len(records)} 条疑似资金划转记录（合计 ¥{total_amount:.2f}）：")
        for r in records:
            raw = json.loads(r["raw_data"])
            print(
                f"  - {r['id']} | {r['trade_time']} | "
                f"¥{abs(r['amount']):.2f} | {raw.get('交易类型', '')}"
            )

        if args.apply:
            ids = [r["id"] for r in records]
            placeholders = ",".join(["?"] * len(ids))
            conn.execute(f"DELETE FROM bills WHERE id IN ({placeholders})", ids)
            conn.commit()
            print(f"\n已删除 {len(ids)} 条记录。")
        else:
            print("\n这是预览模式，未执行删除。如需删除请加上 --apply 参数。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
