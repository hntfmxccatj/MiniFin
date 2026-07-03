"""清空 bills 表数据"""
import sqlite3
from pathlib import Path

DB = str(Path(__file__).parent.parent / "wallet.db")

conn = sqlite3.connect(DB)
count = conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
conn.execute("DELETE FROM bills")
conn.commit()
conn.close()

print(f"已清空 bills 表，共删除 {count} 条记录。")
