"""
MiniFin 账单看板 - FastAPI 后端
"""
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, Query, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd

from backend.parser import (
    DB_PATH,
    ensure_table as ensure_bills_table,
    find_bill_files,
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
def get_summary():
    """汇总统计"""
    conn = get_db()
    try:
        # 按类型汇总
        by_type = conn.execute("""
            SELECT type, COUNT(*) as count, SUM(amount) as total_amount
            FROM bills GROUP BY type
        """).fetchall()

        # 按来源汇总
        by_source = conn.execute("""
            SELECT source, COUNT(*) as count, SUM(amount) as total_amount
            FROM bills GROUP BY source
        """).fetchall()

        # 按月汇总 (支出)
        monthly = conn.execute("""
            SELECT substr(trade_time, 1, 7) as month,
                   COUNT(*) as count,
                   SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as expense,
                   SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as income
            FROM bills
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """).fetchall()

        # 总数
        total_count = conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
        total_expense = conn.execute(
            "SELECT SUM(amount) FROM bills WHERE amount < 0"
        ).fetchone()[0] or 0
        total_income = conn.execute(
            "SELECT SUM(amount) FROM bills WHERE amount > 0"
        ).fetchone()[0] or 0

        return {
            "total_count": total_count,
            "total_expense": round(total_expense, 2),
            "total_income": round(total_income, 2),
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


@app.post("/api/upload")
async def upload_bills(files: List[UploadFile] = File(...)):
    """
    拖拽上传微信 / 支付宝 CSV 账单文件。
    解析后返回标准化数据，不入库（前端可预览后再批量保存）。
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="minifin_"))
    saved = []
    try:
        for up in files:
            if not up.filename.lower().endswith(".csv"):
                continue
            dest = tmp_dir / up.filename
            with open(dest, "wb") as f:
                shutil.copyfileobj(up.file, f)
            saved.append(str(dest))

        if not saved:
            return {"records": [], "total": 0, "message": "未接收到 CSV 文件"}

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
