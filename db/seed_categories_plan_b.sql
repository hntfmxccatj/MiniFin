-- 方案 B（精简版）：基于 50/30/20 预算框架的分类体系
-- 执行前请备份 wallet.db

DELETE FROM categories;

-- ==================== Needs（必需支出）====================

INSERT INTO categories (budget_group, major_category, sub_category) VALUES
('Needs', 'Housing & Utilities', 'Rent'),
('Needs', 'Housing & Utilities', 'Utilities'),
('Needs', 'Housing & Utilities', 'Internet & Phone'),
('Needs', 'Housing & Utilities', 'Property Management'),
('Needs', 'Housing & Utilities', 'Home Maintenance'),
('Needs', 'Food & Groceries', 'Groceries'),
('Needs', 'Food & Groceries', 'Diet'),
('Needs', 'Transportation', 'Public Transit'),
('Needs', 'Transportation', 'Ride Sharing'),
('Needs', 'Health & Insurance', 'Medical'),
('Needs', 'Health & Insurance', 'Pharmacy'),
('Needs', 'Health & Insurance', 'Insurance'),
('Needs', 'Personal Care & Pets', 'HairCut'),
('Needs', 'Personal Care & Pets', 'Toiletries'),
('Needs', 'Personal Care & Pets', 'Pet Expenses'),
('Needs', 'Personal Care & Pets', 'Fitness & Sports');

-- ==================== Wants（品质支出）====================

INSERT INTO categories (budget_group, major_category, sub_category) VALUES
('Wants', 'Dining & Drinks', 'Dining out'),
('Wants', 'Dining & Drinks', 'Drinks'),
('Wants', 'Dining & Drinks', 'Snacks'),
('Wants', 'Dining & Drinks', 'Takeout'),
('Wants', 'Entertainment & Social', 'Entertainment'),
('Wants', 'Entertainment & Social', 'Social'),
('Wants', 'Entertainment & Social', 'Hobbies'),
('Wants', 'Entertainment & Social', 'Education & Courses'),
('Wants', 'Shopping', 'Clothing'),
('Wants', 'Shopping', 'Electronics'),
('Wants', 'Shopping', 'Gifts'),
('Wants', 'Shopping', 'Home Goods'),
('Wants', 'Subscriptions', 'Software & Apps'),
('Wants', 'Subscriptions', 'Streaming'),
('Wants', 'Subscriptions', 'Memberships'),
('Wants', 'Travel', 'Trip & Holiday'),
('Wants', 'Travel', 'Flights'),
('Wants', 'Travel', 'Accommodation');

-- ==================== Savings & Debt（储蓄与还债）====================

INSERT INTO categories (budget_group, major_category, sub_category) VALUES
('Savings & Debt', 'Savings & Investments', 'Emergency Fund'),
('Savings & Debt', 'Savings & Investments', 'Investments'),
('Savings & Debt', 'Savings & Investments', 'General Savings'),
('Savings & Debt', 'Debt Payments', 'Credit Card'),
('Savings & Debt', 'Debt Payments', 'Hua Bei'),
('Savings & Debt', 'Debt Payments', 'Bai Tiao'),
('Savings & Debt', 'Debt Payments', 'Loans');

-- ==================== Income（收入）====================

INSERT INTO categories (budget_group, major_category, sub_category) VALUES
('Income', 'Income', 'Salary'),
('Income', 'Income', 'Other Income');

-- ==================== Uncategorized（未分类）====================

INSERT INTO categories (budget_group, major_category, sub_category) VALUES
('Uncategorized', 'Uncategorized', 'Fees & Fines'),
('Uncategorized', 'Uncategorized', 'Others');
