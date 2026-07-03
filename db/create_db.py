"""一键创建数据库及 bills 表"""
import sqlite3
from pathlib import Path

DB = str(Path(__file__).parent.parent / "wallet.db")

conn = sqlite3.connect(DB)
conn.execute("""
    CREATE TABLE IF NOT EXISTS bills (
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

# ────────── 分类配置表 ──────────
conn.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        major_category  TEXT NOT NULL,
        sub_category    TEXT NOT NULL,
        UNIQUE(major_category, sub_category)
    )
""")

conn.commit()
conn.close()

print("数据库 wallet.db、bills 表、categories 表创建完成。")
