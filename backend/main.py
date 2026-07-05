"""
MiniFin 账单看板 - FastAPI 后端
"""
import calendar
import os
import shutil
import sqlite3
import tempfile
from datetime import date
from pathlib import Path
from typing import List

from fastapi import FastAPI, Query, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd

from backend.classifier import predict_categories
from backend.parser import (
    DB_PATH,
    ensure_table as ensure_bills_table,
    insert_to_db,
    parse_files,
)


# 项目根目录 (backend/ 的上级目录)
ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "wallet.db"

app = FastAPI(title="MiniFin API")

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ────────── 通用筛选构建 ──────────

def _build_filter_conditions(
    source: str = "",
    keyword: str = "",
    start_date: str = "",
    end_date: str = "",
    base_conditions: list[str] | None = None,
) -> tuple[list[str], list]:
    """构建 WHERE 子句条件与参数列表"""
    where = list(base_conditions) if base_conditions else ["1=1"]
    params = []

    if source:
        where.append("source = ?")
        params.append(source.upper())
    if keyword:
        where.append("(counterparty LIKE ? OR product LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if start_date:
        where.append("trade_time >= ?")
        params.append(start_date)
    if end_date:
        where.append("trade_time <= ?")
        params.append(end_date + " 23:59:59")

    return where, params


def _where_clause(conditions: list[str]) -> str:
    return " AND ".join(conditions)


# ────────── API 路由 ──────────

@app.get("/api/bills")
def get_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    source: str = Query("", description="WECHAT / ALIPAY"),
    bill_type: str = Query("", description="EXPENSE / INCOME / REFUND"),
    start_date: str = Query("", description="YYYY-MM-DD"),
    end_date: str = Query("", description="YYYY-MM-DD"),
    keyword: str = Query("", description="搜索交易对方或商品"),
):
    """分页查询账单列表"""
    conn = get_db()
    try:
        where = ["1=1"]
        params = []

        if source:
            where.append("source = ?")
            params.append(source.upper())
        if bill_type:
            where.append("type = ?")
            params.append(bill_type.upper())
        if start_date:
            where.append("trade_time >= ?")
            params.append(start_date)
        if end_date:
            where.append("trade_time <= ?")
            params.append(end_date + " 23:59:59")
        if keyword:
            where.append("(counterparty LIKE ? OR product LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where_clause = " AND ".join(where)

        # 总数
        count_sql = f"SELECT COUNT(*) FROM bills WHERE {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # 数据
        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM bills
            WHERE {where_clause}
            ORDER BY trade_time DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [page_size, offset]).fetchall()
        bills = [dict(r) for r in rows]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "data": bills,
        }
    finally:
        conn.close()


@app.get("/api/bills/summary")
def get_summary(
    start_date: str = Query("", description="YYYY-MM-DD"),
    end_date: str = Query("", description="YYYY-MM-DD"),
    source: str = Query("", description="WECHAT / ALIPAY"),
    keyword: str = Query("", description="搜索交易对方或商品"),
):
    """汇总统计（支持时间范围、来源、关键词筛选）"""
    conn = get_db()
    try:
        where, params = _build_filter_conditions(source, keyword, start_date, end_date)
        where_clause = _where_clause(where)

        # 按类型汇总
        by_type = conn.execute(
            f"""
            SELECT type, COUNT(*) as count, SUM(amount) as total_amount
            FROM bills
            WHERE {where_clause}
            GROUP BY type
            """,
            params,
        ).fetchall()

        # 按来源汇总
        by_source = conn.execute(
            f"""
            SELECT source, COUNT(*) as count, SUM(amount) as total_amount
            FROM bills
            WHERE {where_clause}
            GROUP BY source
            """,
            params,
        ).fetchall()

        # 按月汇总 (支出)
        monthly = conn.execute(
            f"""
            SELECT substr(trade_time, 1, 7) as month,
                   COUNT(*) as count,
                   SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as expense,
                   SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as income
            FROM bills
            WHERE {where_clause}
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
            """,
            params,
        ).fetchall()

        # 总数
        total_count = conn.execute(
            f"SELECT COUNT(*) FROM bills WHERE {where_clause}", params
        ).fetchone()[0]
        total_expense = conn.execute(
            f"SELECT SUM(amount) FROM bills WHERE amount < 0 AND {where_clause}",
            params,
        ).fetchone()[0] or 0
        total_income = conn.execute(
            f"SELECT SUM(amount) FROM bills WHERE amount > 0 AND {where_clause}",
            params,
        ).fetchone()[0] or 0

        # 参考月份：优先使用 end_date 所在月，否则为当前月
        if end_date:
            ref = date.fromisoformat(end_date)
        else:
            ref = date.today()
        ref_month_str = ref.strftime("%Y-%m")
        ref_year, ref_month_num = ref.year, ref.month
        days_in_month = calendar.monthrange(ref_year, ref_month_num)[1]
        # 参考月为本月时，today_day 取当前天；历史月则取该月最后一天
        today_day = min(date.today().day, days_in_month) if ref_month_str == date.today().strftime("%Y-%m") else days_in_month

        # 参考月内支出（同时受筛选范围约束）
        ref_where = where + ["substr(trade_time, 1, 7) = ?"]
        ref_params = params + [ref_month_str]
        current_month_row = conn.execute(
            f"""
            SELECT SUM(amount) as expense
            FROM bills
            WHERE type = 'EXPENSE' AND {_where_clause(ref_where)}
            """,
            ref_params,
        ).fetchone()
        current_month_expense = abs(current_month_row["expense"] or 0)

        avg_daily_expense = (
            round(current_month_expense / today_day, 2) if today_day > 0 else 0
        )
        projected_month_expense = round(avg_daily_expense * days_in_month, 2)

        return {
            "total_count": total_count,
            "total_expense": round(total_expense, 2),
            "total_income": round(total_income, 2),
            "avg_daily_expense": avg_daily_expense,
            "projected_month_expense": projected_month_expense,
            "by_type": [dict(r) for r in by_type],
            "by_source": [dict(r) for r in by_source],
            "monthly": [dict(r) for r in monthly],
        }
    finally:
        conn.close()


@app.get("/api/bills/counterparties")
def get_counterparties(limit: int = Query(20, ge=1, le=100)):
    """支出最多的交易对方排名"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT counterparty,
                   COUNT(*) as count,
                   SUM(amount) as total_amount
            FROM bills
            WHERE type = 'EXPENSE'
            GROUP BY counterparty
            ORDER BY total_amount ASC
            LIMIT ?
        """, [limit]).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/bills/expense_by_category")
def get_expense_by_category(
    start_date: str = Query("", description="YYYY-MM-DD"),
    end_date: str = Query("", description="YYYY-MM-DD"),
    source: str = Query("", description="WECHAT / ALIPAY"),
    keyword: str = Query("", description="搜索交易对方或商品"),
):
    """按 Major Category 分月聚合支出，支持筛选"""
    conn = get_db()
    try:
        where, params = _build_filter_conditions(source, keyword, start_date, end_date)
        where_clause = _where_clause(where)

        # 取筛选范围内的月份
        month_rows = conn.execute(
            f"""
            SELECT substr(trade_time, 1, 7) as month
            FROM bills
            WHERE type = 'EXPENSE' AND {where_clause}
            GROUP BY month
            ORDER BY month DESC
            """,
            params,
        ).fetchall()
        months = [r["month"] for r in reversed(month_rows)]

        if not months:
            return {"months": [], "series": [], "totals_by_major": []}

        # 按月份 + 大类聚合
        rows = conn.execute(
            f"""
            SELECT substr(trade_time, 1, 7) as month,
                   COALESCE(NULLIF(major_category, ''), '未分类') as major_category,
                   SUM(ABS(amount)) as total_amount,
                   COUNT(*) as count
            FROM bills
            WHERE type = 'EXPENSE'
              AND substr(trade_time, 1, 7) IN ({', '.join(['?'] * len(months))})
              AND {where_clause}
            GROUP BY month, major_category
            ORDER BY month DESC, total_amount DESC
            """,
            months + params,
        ).fetchall()

        # 构建 month -> {category: amount} 映射
        data_by_month = {m: {} for m in months}
        totals_by_major = {}
        for r in rows:
            month = r["month"]
            major = r["major_category"]
            amount = r["total_amount"] or 0
            data_by_month[month][major] = amount
            totals_by_major[major] = totals_by_major.get(major, 0) + amount

        # 获取所有类别，按总额排序
        categories = sorted(
            totals_by_major.keys(),
            key=lambda c: totals_by_major[c],
            reverse=True,
        )

        # 将未分类放到最后
        if "未分类" in categories:
            categories.remove("未分类")
            categories.append("未分类")

        # 构建 series
        series = [
            {
                "name": cat,
                "data": [round(data_by_month[m].get(cat, 0), 2) for m in months],
            }
            for cat in categories
        ]

        totals_list = [
            {
                "major_category": cat,
                "total_amount": round(totals_by_major[cat], 2),
            }
            for cat in categories
        ]

        return {
            "months": months,
            "series": series,
            "totals_by_major": totals_list,
        }
    finally:
        conn.close()


@app.get("/api/bills/budget_summary")
def get_budget_summary(
    start_date: str = Query("", description="YYYY-MM-DD"),
    end_date: str = Query("", description="YYYY-MM-DD"),
    source: str = Query("", description="WECHAT / ALIPAY"),
    keyword: str = Query("", description="搜索交易对方或商品"),
):
    """按 Needs / Wants / Savings & Debt / Uncategorized 汇总支出占比"""
    conn = get_db()
    try:
        where, params = _build_filter_conditions(source, keyword, start_date, end_date)
        where.append("b.type = 'EXPENSE'")
        where_clause = _where_clause(where)

        rows = conn.execute(
            f"""
            SELECT COALESCE(NULLIF(c.budget_group, ''), 'Uncategorized') as budget_group,
                   SUM(ABS(b.amount)) as total_amount
            FROM bills b
            LEFT JOIN categories c
                   ON b.major_category = c.major_category
                  AND b.sub_category = c.sub_category
            WHERE {where_clause}
            GROUP BY budget_group
            ORDER BY total_amount DESC
            """,
            params,
        ).fetchall()

        groups = [dict(r) for r in rows]
        total = sum(g["total_amount"] or 0 for g in groups)

        for g in groups:
            amount = g["total_amount"] or 0
            g["total_amount"] = round(amount, 2)
            g["percentage"] = round(amount / total * 100, 2) if total > 0 else 0

        # 固定顺序，便于图表展示
        order = ["Needs", "Wants", "Savings & Debt", "Uncategorized", "Income"]
        groups.sort(key=lambda g: order.index(g["budget_group"]) if g["budget_group"] in order else 99)

        return {
            "total": round(total, 2),
            "groups": groups,
        }
    finally:
        conn.close()


@app.get("/api/bills/large_orders")
def get_large_orders(
    limit: int = Query(5, ge=1, le=100),
    start_date: str = Query("", description="YYYY-MM-DD"),
    end_date: str = Query("", description="YYYY-MM-DD"),
    source: str = Query("", description="WECHAT / ALIPAY"),
    keyword: str = Query("", description="搜索交易对方或商品"),
):
    """筛选范围内支出金额最大的 N 笔交易"""
    conn = get_db()
    try:
        where, params = _build_filter_conditions(source, keyword, start_date, end_date)
        where.append("type = 'EXPENSE'")
        where_clause = _where_clause(where)

        rows = conn.execute(
            f"""
            SELECT id, source, trade_time, counterparty, product,
                   major_category, sub_category, amount
            FROM bills
            WHERE {where_clause}
            ORDER BY amount ASC
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/bills/daily_expenses")
def get_daily_expenses(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    source: str = Query("", description="WECHAT / ALIPAY"),
    keyword: str = Query("", description="搜索交易对方或商品"),
):
    """返回某年某月每天的支出合计"""
    conn = get_db()
    try:
        where, params = _build_filter_conditions(source, keyword)
        where.append("type = 'EXPENSE'")
        where.append("substr(trade_time, 1, 7) = ?")
        params.append(f"{year:04d}-{month:02d}")
        where_clause = _where_clause(where)

        rows = conn.execute(
            f"""
            SELECT CAST(substr(trade_time, 9, 2) AS INTEGER) as day,
                   SUM(ABS(amount)) as total_amount,
                   COUNT(*) as count
            FROM bills
            WHERE {where_clause}
            GROUP BY day
            ORDER BY day
            """,
            params,
        ).fetchall()

        days = [{"day": r["day"], "amount": r["total_amount"] or 0, "count": r["count"]} for r in rows]
        return {"year": year, "month": month, "days": days}
    finally:
        conn.close()


@app.get("/api/bills/by_day")
def get_bills_by_day(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    day: int = Query(..., ge=1, le=31),
    source: str = Query("", description="WECHAT / ALIPAY"),
    keyword: str = Query("", description="搜索交易对方或商品"),
):
    """返回某年某月某日的所有支出明细"""
    conn = get_db()
    try:
        date_prefix = f"{year:04d}-{month:02d}-{day:02d}"
        where, params = _build_filter_conditions(source, keyword)
        where.append("type = 'EXPENSE'")
        where.append("trade_time LIKE ?")
        params.append(date_prefix + "%")
        where_clause = _where_clause(where)

        rows = conn.execute(
            f"""
            SELECT id, source, trade_time, counterparty, product,
                   major_category, sub_category, amount
            FROM bills
            WHERE {where_clause}
            ORDER BY trade_time DESC
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/categories")
def get_categories():
    """获取所有分类配置 (major + sub)"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, major_category, sub_category
            FROM categories
            ORDER BY major_category, sub_category
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/categories/tree")
def get_categories_tree():
    """获取级联分类：{major_category: [sub_category1, sub_category2, ...]}"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT major_category, sub_category
            FROM categories
            ORDER BY major_category, sub_category
        """).fetchall()
        tree = {}
        for r in rows:
            major = r["major_category"]
            sub = r["sub_category"]
            tree.setdefault(major, []).append(sub)
        return tree
    finally:
        conn.close()


@app.post("/api/upload")
async def upload_bills(files: List[UploadFile] = File(...)):
    """
    拖拽上传微信 / 支付宝 CSV / XLSX 账单文件。
    解析后返回标准化数据，不入库（前端可预览后再批量保存）。
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="minifin_"))
    saved = []
    try:
        for up in files:
            if not up.filename.lower().endswith((".csv", ".xlsx")):
                continue
            dest = tmp_dir / up.filename
            with open(dest, "wb") as f:
                shutil.copyfileobj(up.file, f)
            saved.append(str(dest))

        if not saved:
            return {"records": [], "total": 0, "message": "未接收到 CSV 或 XLSX 文件"}

        # 合并解析所有文件
        dfs = []
        for fp in saved:
            dfs.append(parse_files(fp))

        if not dfs or all(d.empty for d in dfs):
            return {"records": [], "total": 0, "message": "未能解析出有效记录"}


        df = pd.concat(dfs, ignore_index=True)
        # 去除内部重复（同一次上传里的同一笔交易）
        df = df.drop_duplicates(subset=["id"], keep="first")
        records = df.where(pd.notna(df), None).to_dict(orient="records")
        # 金额和 ID 列需要正确处理 NaN
        for r in records:
            r["amount"] = round(float(r["amount"]), 2)
            r["id"] = str(r["id"])

        # 自动预测 Major / Sub 分类并回填
        predictions = predict_categories(records)
        for r, (major, sub) in zip(records, predictions):
            r["major_category"] = major
            r["sub_category"] = sub

        return {"records": records, "total": len(records)}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/bills/batch")
async def save_bills(request: Request):
    """批量保存（含分类）到数据库"""
    payload = await request.json()
    records = payload.get("records", [])
    if not records:
        return {"total": 0, "inserted": 0, "skipped_duplicate": 0}

    df = pd.DataFrame(records)
    conn = get_db()
    try:
        ensure_bills_table(conn)
        stats = insert_to_db(df, conn)
        return stats
    finally:
        conn.close()


# 挂载前端静态文件
frontend_path = ROOT / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
