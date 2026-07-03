"""初始化/更新分类配置表

后续修改类别只需要编辑这个文件里的 CATEGORIES 字典，再运行一次脚本即可。
"""
import sqlite3
from pathlib import Path

# 数据库路径：项目根目录下的 wallet.db
DB_PATH = Path(__file__).parent.parent / "wallet.db"

# ────────── 分类配置（可修改） ──────────
CATEGORIES = {
    "Goals": [
        "General Savings",
        "Investments",
        "Emergency Fund",
    ],
    "Liability": [
        "Credit Card",
        "Hua Bei",
        "Bai Tiao",
    ],
    "Quality of Life": [
        "Entertainment",
        "Sports",
        "Pets",
        "Drinks",
        "Clothing",
        "Snacks",
        "Stuff I forgot to plan for",
        "Dining out",
        "Social",
        "Education & Courses",
    ],
    "Everyday Expenses": [
        "Diet",
        "Pets",
        "Grocery",
        "Transportation",
        "Health",
        "Household Supplies",
        "Home Maintenance",
    ],
    "Bills": [
        "AI Subscription",
        "TV, phone and internet",
        "HairCut",
        "Rent",
        "Annual Subscriptions",
    ],
    "Irregular And Annual Expenses": [
        "Trip & Holiday",
        "Household Supplies (Bulk)",
        "Tech & Others",
    ],
    "Salary": [
        "Salary",
    ],
}


def seed_categories(db_path: str | Path = DB_PATH) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = [
            (major, sub)
            for major, subs in CATEGORIES.items()
            for sub in subs
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO categories (major_category, sub_category) VALUES (?, ?)",
            rows,
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        print(f"Categories seeded: {len(rows)} configured, {count} total in DB.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_categories()
