# MiniFin — 个人账单数据看板

基于 FastAPI 后端 + 前端 SPA 的本地个人财务账单管理工具。  
支持微信/支付宝 CSV 账单上传、解析、自动分类和多维度可视化分析。

---

## 功能

| 功能 | 说明 |
|------|------|
| **账单上传与解析** | 拖拽或选择微信/支付宝 CSV 文件，自动识别来源并解析为标准化数据 |
| **分类管理** | 支持 Major / Sub 两层分类（纯展示），可通过 `db/seed_categories.py` 自定义 |
| **概览看板** | 以支出为中心：KPI 条、分类堆叠趋势图、分类排名、现金流日历、大额订单 |
| **顶部筛选栏** | 按时间范围 / 来源 / 关键词联动筛选所有看板数据 |
| **现金流日历** | 按天查看支出热力，点击日期可展开当日明细 |
| **大额订单** | 筛选范围内支出金额最大的 Top 5/10/15/20 笔交易 |
| **机器学习分类** | 基于标注数据训练文本分类器，自动预测分类（`train_category_classifier.py`） |
| **数据库工具** | 脚本化建库、清空、分类种子数据 |

---

## 快速开始

### 1. 安装依赖

建议使用 Python 虚拟环境：

```bash
# 创建并激活 venv（Windows / Git Bash）
python -m venv venv
source venv/Scripts/activate

# 安装依赖
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
├── run_backend.py                # 后端启动入口
├── requirements.txt              # Python 依赖
├── wallet.db                     # SQLite 数据库（运行时生成，gitignored）
├── README.md                     # 本文件
├── ARCHITECTURE.md               # 架构与 AI 协作指南
│
├── backend/                      # FastAPI 后端
│   ├── main.py                   # 路由、API、静态文件挂载
│   ├── parser.py                 # 账单解析与入库核心
│   └── classifier.py             # 分类模型推理
│
├── db/                           # 数据库管理脚本
│   ├── create_db.py
│   ├── clear_bills.py
│   ├── seed_categories.py
│   └── parse_bills.py
│
├── frontend/                     # 前端 SPA（纯原生 JS）
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── main.js
│       ├── router.js
│       ├── state.js
│       ├── api.js
│       ├── utils.js
│       ├── components/           # UI 组件
│       │   ├── CashFlowCalendar.js
│       │   ├── Charts.js
│       │   ├── FilterBar.js
│       │   ├── LargeOrders.js
│       │   ├── Layout.js
│       │   ├── Sidebar.js
│       │   ├── SummaryCards.js
│       │   └── ...
│       └── pages/                # 页面组件
│           ├── DashboardPage.js
│           └── UploadPage.js
│
└── training/                     # 分类模型训练
    ├── train_category_classifier.py
    ├── Training Data.csv
    └── models/                   # 模型工件（gitignored）
```

---

## 主要 API

| 接口 | 说明 |
|------|------|
| `GET /api/bills` | 分页查询账单列表 |
| `GET /api/bills/summary` | 汇总统计（支持时间/来源/关键词筛选） |
| `GET /api/bills/expense_by_category` | 按 Major Category 分月聚合（支持筛选） |
| `GET /api/bills/large_orders` | 大额订单 Top N（支持筛选） |
| `GET /api/bills/daily_expenses` | 某月每日支出合计 |
| `GET /api/bills/by_day` | 某日支出明细 |
| `POST /api/upload` | 上传 CSV 账单预览 |
| `POST /api/bills/batch` | 批量保存账单 |

---

## 技术栈

- **后端**: Python 3.11+ / FastAPI / Uvicorn / SQLite
- **前端**: 原生 JS ES Module SPA / ApexCharts
- **机器学习**: scikit-learn (TF-IDF + Logistic Regression)

---

## 使用提示

- 看板默认按「全部」时间范围加载，避免首次打开时因当前月无数据而空白。
- 现金流日历默认展示最新有支出的月份；点击有颜色的日期可查看当日明细。
- 筛选栏会联动刷新 KPI、趋势图、分类排名、日历和大额订单。
