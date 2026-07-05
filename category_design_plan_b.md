# MiniFin 分类体系设计方案 B（精简版）：50/30/20 预算框架

## 一、设计原则

采用主流个人财务管理中的 **50/30/20 法则**：

- **50% Needs（必需支出）**：维持基本生活无法避免的开支
- **30% Wants（品质支出）**：提升生活质量、可压缩的开支
- **20% Savings & Debt（储蓄与还债）**：应急、投资、还债

本次精简基于以下约束：

- 不买车：去除 Fuel / Vehicle Maintenance / Parking
- 宠物支出简单：无美容类，并入 Needs 下的个人护理 Major
- 运动健身开支可控：并入 Needs 下的 Personal Care & Pets
- 配饰并入衣物：减少细分类别

---

## 二、Major / Sub 分类设计

### 1. Housing & Utilities（住房与水电）— Needs

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Rent | 房租 | 月租、租房押金 |
| Utilities | 水电煤 | 水费、电费、燃气费 |
| Internet & Phone | 网络与电话 | 宽带、手机话费 |
| Property Management | 物业费 | 小区物业费 |
| Home Maintenance | 房屋维修 | 修水管、换锁、家电维修 |

### 2. Food & Groceries（食品与日用品）— Needs

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Groceries | 食材与日用品 | 超市买菜、米面油、日用品 |
| Diet | 日常三餐 | 食堂、便利店盒饭、自己做饭 |

> 注意：外出就餐、咖啡奶茶、零食不属于 Needs，归入 `Dining & Drinks`。

### 3. Transportation（交通）— Needs

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Public Transit | 公共交通 | 地铁、公交、高铁 |
| Ride Sharing | 网约车/出租车 | 滴滴、出租车 |

> 说明：因不买车，仅保留公共交通和打车。

### 4. Health & Insurance（健康与保险）— Needs

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Medical | 医疗 | 医院挂号、诊疗费 |
| Pharmacy | 药品 | 药店买药 |
| Insurance | 保险 | 医保、商业保险 |

### 5. Personal Care & Pets（个人护理、宠物与运动）— Needs

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| HairCut | 理发 | 理发 |
| Toiletries | 洗护用品 | 牙膏、洗发水、护肤品 |
| Pet Expenses | 宠物支出 | 猫粮狗粮、宠物用品、基础看病 |
| Fitness & Sports | 健身与运动 | 健身房、运动课程、球类、游泳、运动装备 |

> 说明：
> - 宠物支出合并为一个 Sub，涵盖食品、用品和基础医疗。美容类支出暂不考虑。
> - 健身与运动开支可控且金额较小，归入 Needs 下的个人护理大类，不再单独设 Major。

---

### 6. Dining & Drinks（外出餐饮与饮品）— Wants

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Dining out | 外出就餐 | 餐厅、火锅、烧烤 |
| Drinks | 饮品 | 咖啡、奶茶、酒吧 |
| Snacks | 零食 | 薯片、甜点、便利店零食 |
| Takeout | 外卖 | 美团、饿了么 |

### 7. Entertainment & Social（娱乐与社交）— Wants

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Entertainment | 娱乐活动 | 电影、KTV、游戏、演出 |
| Social | 社交聚会 | 朋友聚餐 AA、请客、红包 |
| Hobbies | 兴趣爱好 | 摄影、绘画、乐器、模型 |
| Education & Courses | 教育与课程 | 在线课程、考证、书籍 |

### 8. Shopping（购物）— Wants

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Clothing | 衣物配饰 | 衣服、鞋子、包包、首饰、手表、眼镜 |
| Electronics | 电子产品 | 手机、电脑、耳机 |
| Gifts | 礼物 | 送人的礼物、红包 |
| Home Goods | 家居用品 | 家具、装饰、厨具 |

> 说明：`Accessories` 已并入 `Clothing`。

### 9. Subscriptions（订阅服务）— Wants

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Software & Apps | 软件与应用 | ChatGPT、Notion、AI 工具 |
| Streaming | 流媒体 | Netflix、Spotify、B站会员 |
| Memberships | 会员 | 山姆会员、视频会员 |

### 10. Travel（旅行）— Wants

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Trip & Holiday | 旅行度假 | 旅游总支出 |
| Flights | 机票 | 飞机票 |
| Accommodation | 住宿 | 酒店、民宿 |

---

### 11. Savings & Investments（储蓄与投资）— Savings

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Emergency Fund | 应急基金 | 存入应急账户 |
| Investments | 投资 | 基金、股票、理财产品 |
| General Savings | 一般储蓄 | 定期存款、普通储蓄 |

### 12. Debt Payments（债务偿还）— Savings / Debt

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Credit Card | 信用卡还款 | 信用卡账单还款 |
| Hua Bei | 花呗 | 花呗还款 |
| Bai Tiao | 白条 | 京东白条还款 |
| Loans | 贷款 | 房贷、车贷、消费贷还款 |

### 13. Income（收入）

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Salary | 工资 | 月薪、奖金 |
| Other Income | 其他收入 | 兼职、理财收益、红包 |

### 14. Uncategorized（未分类）

| Sub Category | 中文说明 | 示例 |
|---|---|---|
| Fees & Fines | 手续费与罚款 | 转账手续费、罚款 |
| Others | 其他 | 暂时无法归类的支出 |

---

## 三、预算归属速查表

| budget_group | 预算建议 | 包含 Major |
|---|---|---|
| Needs | ≤ 50% | Housing & Utilities, Food & Groceries, Transportation, Health & Insurance, Personal Care & Pets |
| Wants | ≤ 30% | Dining & Drinks, Entertainment & Social, Shopping, Subscriptions, Travel |
| Savings & Debt | ≥ 20% | Savings & Investments, Debt Payments |
| Income | 不参与支出占比 | Income |
| Uncategorized | 视具体支出重新归类 | Uncategorized |

---

## 四、与原分类的映射关系

| 原 Major | 原 Sub | 新 Major | 新 Sub | 备注 |
|---|---|---|---|---|
| Bills | Rent | Housing & Utilities | Rent | 更准确的归类 |
| Bills | TV, phone and internet | Housing & Utilities | Internet & Phone | 属于住房相关 |
| Bills | AI Subscription | Subscriptions | Software & Apps | 软件订阅 |
| Bills | Annual Subscriptions | Subscriptions | Streaming / Memberships | 流媒体或会员 |
| Bills | HairCut | Personal Care & Pets | HairCut | 不是账单 |
| Everyday Expenses | Diet | Food & Groceries | Diet | 三餐 |
| Everyday Expenses | Grocery | Food & Groceries | Groceries | 食材与日用品 |
| Everyday Expenses | Transportation | Transportation | Public Transit / Ride Sharing | 不买车，去掉车辆相关 |
| Everyday Expenses | Health | Health & Insurance | Medical / Pharmacy | 可细分 |
| Everyday Expenses | Home Maintenance | Housing & Utilities | Home Maintenance | 住房维修 |
| Everyday Expenses | Household Supplies | Shopping | Home Goods | 家居用品 |
| Everyday Expenses | Pets | Personal Care & Pets | Pet Expenses | 并入个人护理 |
| Everyday Expenses | Sports | Personal Care & Pets | Fitness & Sports | 归入 Needs |
| Quality of Life | Clothing | Shopping | Clothing | 含配饰 |
| Quality of Life | Dining out | Dining & Drinks | Dining out | 外出就餐 |
| Quality of Life | Drinks | Dining & Drinks | Drinks | 饮品 |
| Quality of Life | Entertainment | Entertainment & Social | Entertainment | 娱乐 |
| Quality of Life | Pets | Personal Care & Pets | Pet Expenses | 并入个人护理 |
| Quality of Life | Snacks | Dining & Drinks | Snacks | 零食 |
| Quality of Life | Social | Entertainment & Social | Social | 社交 |
| Quality of Life | Sports | Personal Care & Pets | Fitness & Sports | 归入 Needs |
| Quality of Life | Stuff I forgot to plan for | Uncategorized | Others | 统一为未分类 |
| Irregular And Annual Expenses | Household Supplies (Bulk) | Shopping | Home Goods | 家居用品 |
| Irregular And Annual Expenses | Tech & Others | Shopping | Electronics / Miscellaneous | 拆分 |
| Irregular And Annual Expenses | Trip & Holiday | Travel | Trip & Holiday | 旅行 |
| Irregular And Annual Expenses | Diet | Food & Groceries | Diet | 归入食品 |
| Irregular And Annual Expenses | Entertainment | Entertainment & Social | Entertainment | 归入娱乐 |
| Goals | Emergency Fund | Savings & Investments | Emergency Fund | 储蓄 |
| Goals | General Savings | Savings & Investments | General Savings | 储蓄 |
| Goals | Investments | Savings & Investments | Investments | 投资 |
| Liability | Credit Card | Debt Payments | Credit Card | 债务偿还 |
| Liability | Hua Bei | Debt Payments | Hua Bei | 债务偿还 |
| Liability | Bai Tiao | Debt Payments | Bai Tiao | 债务偿还 |
| Salary | Salary | Income | Salary | 收入 |

---

## 五、实施建议

### 阶段 1：重建 categories 表（必选）

用新的 Major / Sub 列表替换 `categories` 表内容。

### 阶段 2：迁移 bills 历史数据（必选）

编写 SQL 迁移脚本，把旧的 Major/Sub 组合映射到新的分类体系。

### 阶段 3：重新训练模型（必选）

运行 `python -m training.train_from_bills`，新模型会基于新的分类结构学习。

### 阶段 4：新增预算分析看板（可选）

在前端增加 Needs / Wants / Savings 占比图表，直接应用 50/30/20 法则。

---

## 六、建议优先使用的核心 Sub（数据量不足时可先只保留这些）

如果当前标注数据不足以训练所有 Sub，建议先保留以下核心类别：

- **Housing & Utilities**: Rent, Internet & Phone
- **Food & Groceries**: Groceries, Diet
- **Transportation**: Public Transit, Ride Sharing
- **Health & Insurance**: Medical, Insurance
- **Personal Care & Pets**: HairCut, Pet Expenses, Fitness & Sports
- **Dining & Drinks**: Dining out, Drinks, Snacks
- **Entertainment & Social**: Entertainment, Social
- **Shopping**: Clothing, Electronics
- **Subscriptions**: Software & Apps, Streaming
- **Travel**: Trip & Holiday
- **Savings & Investments**: Investments, Emergency Fund
- **Debt Payments**: Credit Card, Hua Bei
- **Income**: Salary
- **Uncategorized**: Others
