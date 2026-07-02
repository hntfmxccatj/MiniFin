"""一键创建数据库及 bills 表"""
import sqlite3

DB = "wallet.db"

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
conn.commit()
conn.close()

print("数据库 wallet.db 及 bills 表创建完成。")
