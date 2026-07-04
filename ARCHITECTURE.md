# MiniFin 架构与 AI 协作指南

> 本文件面向后续维护/修改本项目的 AI 与人类开发者。
> 修改代码前请先阅读本节，确保与现有约定保持一致。

---

## 1. 项目定位

MiniFin 是一个**本地运行的个人账单看板**：
- 导入微信 / 支付宝 CSV 账单
- 自动去重、分类、汇总
- 通过浏览器看板查看支出趋势、分类占比、现金流日历与大额订单

**核心原则**：简单、本地、离线可用。避免引入不必要的框架或外部服务。

---

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+ / FastAPI / Uvicorn |
| 数据库 | SQLite (`wallet.db`，项目根目录） |
| 数据处理 | pandas |
| 分类模型 | scikit-learn（TF-IDF + LogisticRegression） |
| 模型持久化 | joblib (`training/models/*.pkl`) |
| 前端 | 原生 ES Module SPA，无构建工具 |
| 图表 | ApexCharts（CDN） |
| 样式 | 原生 CSS（`frontend/css/styles.css`） |

---

## 3. 目录结构

```
MiniFin/
├── run_backend.py                # 后端启动入口：python run_backend.py
├── requirements.txt              # Python 依赖
├── wallet.db                     # SQLite 数据库（运行时生成，gitignored）
├── README.md                     # 用户级快速开始文档
├── ARCHITECTURE.md               # 本文件：架构与协作约定
│
├── backend/                      # FastAPI 后端
│   ├── main.py                   # 路由、API、静态文件挂载
│   ├── parser.py                 # 账单解析核心（微信/支付宝 CSV）
│   └── classifier.py             # 加载训练好的模型，预测 Major/Sub 分类
│
├── db/                           # 数据库管理脚本（命令行工具）
│   ├── create_db.py              # 创建 wallet.db 及 bills/categories 表
│   ├── clear_bills.py            # 清空 bills 表
│   ├── seed_categories.py        # 初始化/更新分类配置
│   └── parse_bills.py            # 命令行账单解析入库
│
├── frontend/                     # 前端 SPA
│   ├── index.html                # 入口 HTML
│   ├── css/styles.css            # 全局样式
│   └── js/
│       ├── main.js               # 启动路由
│       ├── router.js             # hash 路由
│       ├── state.js              # 全局状态对象（含 filters）
│       ├── api.js                # 后端 API 封装
│       ├── utils.js              # 金额/标签/Toast 工具
│       ├── components/           # UI 组件
│       │   ├── CashFlowCalendar.js
│       │   ├── Charts.js
│       │   ├── FilterBar.js
│       │   ├── LargeOrders.js
│       │   ├── Layout.js
│       │   ├── SummaryCards.js
│       │   └── ...
│       └── pages/                # 页面组件
│           ├── DashboardPage.js
│           └── UploadPage.js
│
└── training/                     # 分类模型训练
    ├── train_category_classifier.py
    ├── Training Data.csv         # 标注训练数据
    └── models/                   # 模型工件（gitignored）
```

---

## 4. 数据模型

### 4.1 `bills` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PRIMARY KEY | `MD5(trade_time + amount + counterparty)`，用于跨文件去重 |
| `source` | TEXT | `WECHAT` / `ALIPAY` |
| `raw_id` | TEXT | 原始账单中的交易单号 |
| `trade_time` | TEXT | `YYYY-MM-DD HH:MM:SS` |
| `amount` | REAL | 支出为负，收入/退款为正 |
| `type` | TEXT | `EXPENSE` / `INCOME` / `REFUND` |
| `major_category` | TEXT | 大类（来自 `categories`） |
| `sub_category` | TEXT | 子类 |
| `counterparty` | TEXT | 交易对方 |
| `product` | TEXT | 商品说明 |
| `payment_method` | TEXT | 支付方式 |
| `raw_data` | TEXT | 原始 CSV 行 JSON 备份 |

### 4.2 `categories` 表

```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    major_category TEXT NOT NULL,
    sub_category TEXT NOT NULL,
    UNIQUE(major_category, sub_category)
);
```

- 分类配置是**纯展示/可选**的，不强制外键约束。
- 修改分类只需编辑 `db/seed_categories.py` 中的 `CATEGORIES` 字典，然后运行 `python -m db.seed_categories`。

---

## 5. 数据流

### 5.1 上传流程（Web）

```
用户拖拽 CSV ──> /api/upload ──> backend/main.py
                                     │
                                     ▼
                              backend/parser.py
                              - find_bill_files()
                              - parse_wechat() / parse_alipay()
                              - 生成 id、规范时间、金额正负
                                     │
                                     ▼
                              backend/classifier.py
                              - 预测 major/sub 分类
                                     │
                                     ▼
                         返回 records 给前端预览
                                     │
                         用户确认后 POST /api/bills/batch
                                     │
                                     ▼
                         backend/parser.py insert_to_db()
                         INSERT OR IGNORE 去重写入 wallet.db
```

### 5.2 命令行导入流程

```
python -m db.parse_bills --wechat a.csv --alipay b.csv
    │
    ▼
db/parse_bills.py ──> backend/parser.py ──> wallet.db
```

### 5.3 看板查询流程

```
前端页面
    │
    ├──> /api/bills/summary          ──┐
    ├──> /api/bills/expense_by_category──┤  均支持 start_date/end_date/source/keyword
    ├──> /api/bills/large_orders       ──┤  筛选参数
    ├──> /api/bills/daily_expenses     ──┤
    └──> /api/bills/by_day             ──┘
              │
              ▼
         backend/main.py 直接读 SQLite 返回 JSON
```

---

## 6. 关键约定

### 6.1 金额符号约定

- **支出（EXPENSE）**：`amount < 0`
- **收入（INCOME）**：`amount > 0`
- **退款（REFUND）**：`amount > 0`，`type = 'REFUND'`

所有汇总 SQL 都基于这一约定，**不要**在数据库中存储带符号字符串。

### 6.2 去重机制

- 主键 `id` 由 `trade_time + amount(6 位小数) + counterparty` MD5 生成。
- 入库使用 `INSERT OR IGNORE`，重复记录自动跳过。
- 同一次上传内也做 `drop_duplicates(subset=['id'])`。

### 6.3 文件编码

微信/支付宝 CSV 常见编码为 `gbk` / `gb18030` / `utf-8-sig`。解析器会**自动探测表头行和编码**，新增数据源时应遵循此模式。

### 6.4 筛选机制

- 前端 `state.js` 维护 `filters` 对象：`{ range, source, keyword, start_date, end_date }`
- `FilterBar.js` 负责将 range 预设转换为 `start_date` / `end_date`
- `api.js` 的 `buildQuery()` 将非空筛选参数拼接到 URL
- 后端 `_build_filter_conditions()` 统一构建 WHERE 子句，被 summary / expense_by_category / large_orders / daily_expenses / by_day 复用

### 6.5 图表重渲染

- `Charts.js` 维护 `chartInstances` 数组
- 每次渲染新图表前调用 `.destroy()` 销毁旧实例，防止 ApexCharts 内存泄漏和叠加渲染

### 6.6 现金流日历

- 默认展示**筛选范围内最新有支出的月份**，而非硬编码当前月
- 点击有数据的日期调用 `/api/bills/by_day` 展开当日明细
- 切换月份时清空详情面板

### 6.7 模型工件

训练脚本输出到 `training/models/`：

```
tfidf_vectorizer.pkl
major_classifier.pkl
major_label_encoder.pkl
sub_classifier.pkl
sub_label_encoder.pkl
metrics.json
```

- `classifier.py` 启动时懒加载这些工件；缺失时**静默降级**为空分类，不阻断流程。
- 修改模型结构后，必须重新训练并替换这些文件。

### 6.8 前端架构

- 无构建步骤，浏览器直接加载 ES Modules。
- 路由使用 URL hash：`#dashboard`、`#upload`。
- 组件返回 HTML 字符串，页面负责挂载事件与初始化图表。
- 不要引入 npm 包或打包工具；如需第三方库，使用 CDN 并在 `index.html` 中引入。

---

## 7. 常见修改场景

| 场景 | 推荐做法 |
|------|----------|
| 新增 API | 在 `backend/main.py` 添加路由，复用 `_build_filter_conditions()`；数据库操作后 `conn.close()` |
| 修改解析逻辑 | 改 `backend/parser.py`，保持返回标准 DataFrame；同时检查 `db/parse_bills.py` 是否受影响 |
| 新增账单源 | 在 `parser.py` 添加 `is_xxx_csv()` + `parse_xxx()`，并在 `parse_files()` 中接入 |
| 调整分类 | 编辑 `db/seed_categories.py` 的 `CATEGORIES`，运行 `python -m db.seed_categories` |
| 重训模型 | 更新 `training/Training Data.csv` 后运行 `python training/train_category_classifier.py` |
| 改前端样式 | 优先改 `frontend/css/styles.css`；保持响应式布局 |
| 新增前端页面 | 在 `frontend/js/pages/` 创建页面，在 `frontend/js/router.js` 注册路由 |
| 新增看板组件 | 在 `frontend/js/components/` 创建组件，在 `DashboardPage.js` 中引入并加载 |
| 新增筛选维度 | 同时修改 `FilterBar.js`、`state.js`、`api.js` 和后端对应路由 |

---

## 8. 开发命令

```bash
# 安装依赖（建议先激活 venv）
pip install -r requirements.txt

# 建库
python -m db.create_db

# 初始化分类
python -m db.seed_categories

# 启动服务
python run_backend.py

# 命令行导入账单
python -m db.parse_bills --wechat 微信账单.csv --alipay 支付宝账单.csv

# 训练分类模型
python training/train_category_classifier.py

# 清空账单
python -m db.clear_bills
```

---

## 9. 注意事项与雷区

1. **不要修改 `wallet.db` 的结构而不更新 `db/create_db.py`**；两者必须保持一致。
2. **`backend/parser.py` 与 `db/parse_bills.py` 共享解析逻辑**，改动时请兼顾命令行与 Web 两种入口。
3. **不要在前端使用 `innerHTML` 插入用户输入**。当前代码中涉及用户输入的地方（交易对方、商品）已做 `escapeHtml` 处理；新增功能如需展示用户输入请先转义。
4. **分类预测是可选能力**，`classifier.py` 在模型缺失时应返回空字符串，不能抛异常导致上传失败。
5. **Windows 环境**：使用 `python -m db.xxx` 方式运行脚本可避免路径问题。
6. **Git**：`wallet.db` 和 `training/models/` 已被 `.gitignore`，不要提交。
7. **后端进程**：Windows 上 `run_backend.py` 使用 `reload=True`，会启动父子进程；如遇到旧代码未生效，请检查是否有残留 `python.exe` 占用了 8765 端口。

---

## 10. 扩展建议（如需要）

- **分类规则引擎**：在 `classifier.py` 中增加基于关键词的规则作为模型预测的 fallback。
- **预算功能**：为每个 Major Category 设置月度预算，在看板显示「已用 / 预算」进度条。
- **异常洞察**：自动识别「某类别本月激增」「重复订阅」「大额单笔」等并展示为洞察卡片。
- **手动记账入口**：记录投资/储蓄/现金消费等账单 CSV 无法覆盖的交易。
- **多用户/多账本**：当前数据库为单用户设计；如需多账本，建议新增 `books` 表并在 `bills` 加 `book_id`。
- **定时同步**：可新增脚本调用 `backend/parser.parse_files()` 实现文件夹监听导入。
