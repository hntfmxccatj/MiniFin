"""
将 bills 表中的旧 Major/Sub 分类映射到方案 B（精简版）的新分类体系。

用法：
    source venv/Scripts/activate
    python -m db.migrate_categories_plan_b

执行前会自动备份 wallet.db。
"""
import sqlite3
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DB = Path(__file__).parent.parent / "wallet.db"

# 旧 (major, sub) -> 新 (major, sub)
MIGRATION_MAP = {
    # Bills
    ("Bills", "Rent"): ("Housing & Utilities", "Rent"),
    ("Bills", "TV, phone and internet"): ("Housing & Utilities", "Internet & Phone"),
    ("Bills", "AI Subscription"): ("Subscriptions", "Software & Apps"),
    ("Bills", "Annual Subscriptions"): ("Subscriptions", "Memberships"),
    ("Bills", "HairCut"): ("Personal Care & Pets", "HairCut"),

    # Everyday Expenses
    ("Everyday Expenses", "Diet"): ("Food & Groceries", "Diet"),
    ("Everyday Expenses", "Grocery"): ("Food & Groceries", "Groceries"),
    ("Everyday Expenses", "Transportation"): ("Transportation", "Public Transit"),
    ("Everyday Expenses", "Health"): ("Health & Insurance", "Medical"),
    ("Everyday Expenses", "Home Maintenance"): ("Housing & Utilities", "Home Maintenance"),
    ("Everyday Expenses", "Household Supplies"): ("Shopping", "Home Goods"),
    ("Everyday Expenses", "Pets"): ("Personal Care & Pets", "Pet Expenses"),
    ("Everyday Expenses", "Sports"): ("Personal Care & Pets", "Fitness & Sports"),

    # Quality of Life
    ("Quality of Life", "Clothing"): ("Shopping", "Clothing"),
    ("Quality of Life", "Diet"): ("Food & Groceries", "Diet"),
    ("Quality of Life", "Dining out"): ("Dining & Drinks", "Dining out"),
    ("Quality of Life", "Drinks"): ("Dining & Drinks", "Drinks"),
    ("Quality of Life", "Entertainment"): ("Entertainment & Social", "Entertainment"),
    ("Quality of Life", "Pets"): ("Personal Care & Pets", "Pet Expenses"),
    ("Quality of Life", "Snacks"): ("Dining & Drinks", "Snacks"),
    ("Quality of Life", "Social"): ("Entertainment & Social", "Social"),
    ("Quality of Life", "Sports"): ("Personal Care & Pets", "Fitness & Sports"),
    ("Quality of Life", "Stuff I forgot to plan for"): ("Uncategorized", "Others"),

    # Irregular And Annual Expenses
    ("Irregular And Annual Expenses", "Household Supplies (Bulk)"): ("Shopping", "Home Goods"),
    ("Irregular And Annual Expenses", "Tech & Others"): ("Shopping", "Electronics"),
    ("Irregular And Annual Expenses", "Trip & Holiday"): ("Travel", "Trip & Holiday"),
    ("Irregular And Annual Expenses", "Diet"): ("Food & Groceries", "Diet"),
    ("Irregular And Annual Expenses", "Entertainment"): ("Entertainment & Social", "Entertainment"),

    # Miscellaneous (old) -> Uncategorized (new)
    ("Miscellaneous", "Uncategorized"): ("Uncategorized", "Others"),
    ("Miscellaneous", "Others"): ("Uncategorized", "Others"),
    ("Miscellaneous", "Fees & Fines"): ("Uncategorized", "Fees & Fines"),

    # Goals
    ("Goals", "Emergency Fund"): ("Savings & Investments", "Emergency Fund"),
    ("Goals", "General Savings"): ("Savings & Investments", "General Savings"),
    ("Goals", "Investments"): ("Savings & Investments", "Investments"),

    # Liability
    ("Liability", "Credit Card"): ("Debt Payments", "Credit Card"),
    ("Liability", "Hua Bei"): ("Debt Payments", "Hua Bei"),
    ("Liability", "Bai Tiao"): ("Debt Payments", "Bai Tiao"),

    # Salary
    ("Salary", "Salary"): ("Income", "Salary"),
}


def backup_db():
    backup_path = DB.parent / f"wallet.db.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy(DB, backup_path)
    print(f"已备份数据库到: {backup_path}")


def main():
    backup_db()

    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # 加载新 categories 表用于校验
    valid_map = defaultdict(set)
    for r in conn.execute("SELECT major_category, sub_category FROM categories"):
        valid_map[r["major_category"]].add(r["sub_category"])

    # 读取所有已分类记录
    cur = conn.execute(
        "SELECT id, major_category, sub_category FROM bills "
        "WHERE major_category IS NOT NULL AND major_category != ''"
    )
    rows = cur.fetchall()

    migrated = 0
    skipped = 0
    invalid_after = []

    for r in rows:
        old = (r["major_category"], r["sub_category"])
        new = MIGRATION_MAP.get(old)

        if not new:
            print(f"  未找到映射，跳过: {old[0]} / {old[1]} (id={r['id']})")
            skipped += 1
            continue

        new_major, new_sub = new

        # 校验新分类是否合法
        if new_major not in valid_map or new_sub not in valid_map[new_major]:
            print(f"  映射后分类不合法: {old[0]} / {old[1]} -> {new_major} / {new_sub}")
            invalid_after.append((r["id"], old, new))
            continue

        conn.execute(
            "UPDATE bills SET major_category = ?, sub_category = ? WHERE id = ?",
            (new_major, new_sub, r["id"]),
        )
        migrated += 1

    conn.commit()

    print(f"\n迁移完成:")
    print(f"  已迁移: {migrated} 条")
    print(f"  跳过: {skipped} 条")
    if invalid_after:
        print(f"  映射后非法: {len(invalid_after)} 条")

    # 统计迁移后的分布
    print("\n迁移后 Major 分布:")
    for r in conn.execute(
        "SELECT major_category, COUNT(*) as cnt FROM bills "
        "WHERE major_category IS NOT NULL AND major_category != '' "
        "GROUP BY major_category ORDER BY cnt DESC"
    ):
        print(f"  {r['major_category']}: {r['cnt']}")

    conn.close()


if __name__ == "__main__":
    main()
