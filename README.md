# MiniFin — 个人账单数据看板

基于 FastAPI 后端 + 前端 SPA 的个人财务账单管理工具。  
支持微信/支付宝 CSV 账单上传、解析、分类和可视化分析。

---

## 功能

| 功能 | 说明 |
|------|------|
| **账单上传与解析** | 拖拽或选择微信/支付宝 CSV 文件，自动识别来源并解析为标准化数据 |
| **分类管理** | 支持 Major / Sub 两层分类（纯展示），可通过 `db/seed_categories.py` 自定义 |
| **概览看板** | 汇总卡片（总条数、总支出、总收入）+ 月度趋势图 + 支出分类饼图 + 交易对方排名 |
| **机器学习分类** | 基于标注数据训练文本分类器，自动预测分类（`train_category_classifier.py`） |
| **数据库工具** | 脚本化建库、清空、分类种子数据 |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 创建数据库

```bash
python -m db.create_db
```

（可选）初始化分类配置：

```bash
python -m db.seed_categories
```

### 3. 启动服务

```bash
python run_backend.py
```

打开浏览器访问 `http://127.0.0.1:8765`

### 4. 导入历史账单（可选）

```bash
python -m db.parse_bills --wechat 微信账单.csv --alipay 支付宝账单.csv
```

---

## 项目结构

```
MiniFin/
├── run_backend.py           # 后端启动入口
├── requirements.txt         # Python 依赖
├── train_category_classifier.py   # 分类模型训练
├── Training Data.csv        # 标注的训练数据
├── wallet.db                # SQLite 数据库
├── backend/
│   ├── main.py              # FastAPI 路由
│   └── parser.py            # 账单解析与入库核心
├── db/                      # 数据库管理脚本
│   ├── create_db.py
│   ├── clear_bills.py
│   ├── seed_categories.py
│   └── parse_bills.py
├── frontend/                # 前端 SPA（纯原生 JS）
│   ├── index.html
│   ├── css/styles.css
│   └── js/ ...
└── models/                  # 训练好的模型文件（gitignored）
```

---

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SQLite
- **前端**: 原生 JS ES Module SPA / ApexCharts
- **机器学习**: scikit-learn (TF-IDF + Logistic Regression)
