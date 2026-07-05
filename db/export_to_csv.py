"""
导出 wallet.db 中的 bills 和 categories 表为 CSV。

用法：
    python -m db.export_to_csv

导出文件位于项目根目录的 exports/ 文件夹下，文件名带时间戳。
"""
import csv
import sqlite3
from datetime import datetime
from pathlib import Path

DB = str(Path(__file__).parent.parent / "wallet.db")
EXPORT_DIR = Path(__file__).parent.parent / "exports"


def export_table(conn, table_name, output_path):
    """将单张表内容写入 CSV，返回导出行数。"""
    cursor = conn.execute(f"SELECT * FROM {table_name}")
    headers = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    # 使用 utf-8-sig 便于 Excel 直接打开中文不乱码
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    return len(rows)


def main():
    EXPORT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    conn = sqlite3.connect(DB)
    try:
        bills_path = EXPORT_DIR / f"bills_{timestamp}.csv"
        categories_path = EXPORT_DIR / f"categories_{timestamp}.csv"

        bills_count = export_table(conn, "bills", bills_path)
        categories_count = export_table(conn, "categories", categories_path)

        print(f"导出完成：")
        print(f"  - {bills_path}  ({bills_count} 条 bills 记录)")
        print(f"  - {categories_path}  ({categories_count} 条 categories 记录)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
