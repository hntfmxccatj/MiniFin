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
| **机器学习分类** | 基于已标注账单训练层级文本分类器，上传时自动预测 Major / Sub（`training/train_from_bills.py`） |
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
    ├── train_from_bills.py       # 从数据库训练层级分类模型（推荐）
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

## 自动分类模型训练

MiniFin 使用账单中的手动分类记录训练文本分类器，在上传新账单时自动预测 Major / Sub 两层分类。

### 训练流程

1. **读取训练数据**：从 `wallet.db` 的 `bills` 表中读取已标注 `major_category` 和 `sub_category` 的记录。
2. **权威映射校验**：以 `categories` 表定义的 Major-Sub 关系为唯一权威来源，过滤掉 bills 中与其不一致的标注。
3. **特征构建**：将以下字段拼接为模型输入文本：
   - `counterparty`（交易对方）
   - `product`（商品）
   - `payment_method`（支付方式）
   - `source`（WECHAT / ALIPAY）
   - 原始账单中的 `交易类型`（如“商户消费”“扫二维码付款”等）
4. **文本向量化**：使用 TF-IDF（`char_wb` 2-5 gram），适合中英文混合的短文本。
5. **层级分类器**：
   - 先训练一个 **Major 分类器** 预测一级分类；
   - 再为每个 Major 单独训练一个 **Sub 分类器**，仅学习该 Major 下的 Sub 分布；
   - 预测时先得到 Major，再用对应 Major 的 Sub 分类器预测 Sub，确保 Sub 一定属于该 Major。
6. **约束兜底**：若 Sub 分类器不存在或预测失败，自动 fallback 到该 Major 下最常见的合法 Sub。

### 训练命令

```bash
source venv/Scripts/activate
python -m training.train_from_bills
```

训练完成后，模型工件保存到 `training/models/`：

- `tfidf_vectorizer.pkl`
- `major_classifier.pkl` / `major_label_encoder.pkl`
- `sub_classifiers.pkl` / `sub_label_encoders.pkl`
- `major_sub_map.json`（来自 `categories` 表的权威映射）
- `fallback_sub.json`
- `metrics.json`

### 自动加载

`backend/classifier.py` 会检测模型文件修改时间。重新训练后，后端无需重启，再次上传账单预览时即自动使用最新模型。

### 提升模型效果的建议

- 模型准确率直接取决于已标注数据量和分布均衡性。
- 优先补充样本较少的 Sub 类别（如 `Sports`、`Social`、`Trip & Holiday`、`Goals` 等）。
- 若发现某条记录的 Major/Sub 标注与 `categories` 表定义冲突，修正后重新训练即可。

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
