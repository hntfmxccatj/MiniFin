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

从项目根目录运行:
     python -m db.parse_bills --wechat ...
 或
     cd db && python parse_bills.py --wechat ...
"""
import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Ensure project root is in sys.path so "from backend.parser" works
_project_root = str(Path(__file__).parent.parent.resolve())
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.parser import (
    DB_PATH,
    TABLE_NAME,
    ensure_table,
    find_bill_files,
    insert_to_db,
    parse_alipay,
    parse_wechat,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("parse_bills")



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
            wx_exp = len(df_wx[df_wx['type'] == 'EXPENSE'])
            wx_inc = len(df_wx[df_wx['type'] == 'INCOME'])
            wx_ref = len(df_wx[df_wx['type'] == 'REFUND'])
            log.info(f"  微信 ({os.path.basename(fp)}): {len(df_wx)} 条 -> 支出 {wx_exp} | 收入 {wx_inc} | 退款 {wx_ref}")
            all_dfs.append(df_wx)

    # --- 支付宝 ---
    if alipay_path:
        found = find_bill_files(alipay_path)
        ali_files = found["alipay"]
        if not ali_files:
            log.warning(f"未找到支付宝账单文件: {alipay_path}")
        for fp in ali_files:
            df_ali = parse_alipay(fp)
            ali_exp = len(df_ali[df_ali['type'] == 'EXPENSE'])
            ali_inc = len(df_ali[df_ali['type'] == 'INCOME'])
            ali_ref = len(df_ali[df_ali['type'] == 'REFUND'])
            log.info(f"  支付宝 ({os.path.basename(fp)}): {len(df_ali)} 条 -> 支出 {ali_exp} | 收入 {ali_inc} | 退款 {ali_ref}")
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
        total_out = stats['total']
        inserted_out = stats['inserted']
        skipped_out = stats['skipped_duplicate']
        log.info(f"入库完成: 本次解析 {total_out} 条, 新写入 {inserted_out} 条, 跳过重复 {skipped_out} 条")

        # 汇总统计
        total_bills = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
        log.info(f"数据库中 bills 表当前共 {total_bills} 条记录")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
