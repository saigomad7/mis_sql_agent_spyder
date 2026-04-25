-- =============================================
-- mis_sql_agent 샘플 데이터베이스 초기화
-- 4-table JOIN 실험용
-- =============================================

-- 기존 테이블 제거 (재실행 시 충돌 방지)
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS categories CASCADE;

-- =============================================
-- 1. categories (카테고리)
-- =============================================
CREATE TABLE categories (
    category_id   SERIAL PRIMARY KEY,
    category_name VARCHAR(50)  NOT NULL,
    description   TEXT
);

INSERT INTO categories (category_name, description) VALUES
('전자제품',   '스마트폰, 노트북, 태블릿 등 전자기기'),
('의류',       '남성복, 여성복, 스포츠웨어'),
('식품',       '신선식품, 가공식품, 음료'),
('도서',       '소설, 자기계발, 기술서적'),
('스포츠용품', '운동기구, 아웃도어, 스포츠웨어');

-- =============================================
-- 2. products (상품) → categories 참조
-- =============================================
CREATE TABLE products (
    product_id   SERIAL PRIMARY KEY,
    category_id  INT REFERENCES categories(category_id),
    product_name VARCHAR(100)   NOT NULL,
    price        NUMERIC(10,2)  NOT NULL,
    stock        INT DEFAULT 0
);

INSERT INTO products (category_id, product_name, price, stock) VALUES
-- 전자제품
(1, '갤럭시 S24',        1200000, 50),
(1, '아이폰 15 Pro',     1500000, 30),
(1, '맥북 에어 M3',      1800000, 20),
(1, '갤럭시 탭 S9',       900000, 40),
(1, '소니 헤드폰 WH-1000', 400000, 60),
-- 의류
(2, '나이키 런닝화',       150000, 100),
(2, '아디다스 후드티',      80000, 80),
(2, '유니클로 청바지',       50000, 120),
(2, '폴로 셔츠',            70000, 90),
-- 식품
(3, '제주 감귤 5kg',        25000, 200),
(3, '유기농 녹차',           15000, 150),
(3, '스타벅스 원두 500g',    22000, 100),
-- 도서
(4, '파이썬 머신러닝',       35000, 60),
(4, 'LangChain 완전정복',    32000, 45),
(4, '데이터베이스 설계론',    28000, 30),
-- 스포츠용품
(5, '요가 매트',             45000, 70),
(5, '덤벨 세트 10kg',        60000, 40),
(5, '등산 백팩 60L',         120000, 25);

-- =============================================
-- 3. customers (고객)
-- =============================================
CREATE TABLE customers (
    customer_id  SERIAL PRIMARY KEY,
    name         VARCHAR(50)  NOT NULL,
    email        VARCHAR(100) UNIQUE NOT NULL,
    city         VARCHAR(50),
    grade        VARCHAR(10)  DEFAULT 'NORMAL',  -- NORMAL / VIP / VVIP
    join_date    DATE         NOT NULL
);

INSERT INTO customers (name, email, city, grade, join_date) VALUES
('김민준', 'minjun.kim@email.com',   '서울', 'VVIP', '2022-01-15'),
('이서연', 'seoyeon.lee@email.com',  '부산', 'VIP',  '2022-03-20'),
('박지호', 'jiho.park@email.com',    '서울', 'VIP',  '2022-06-10'),
('최아름', 'areum.choi@email.com',   '대구', 'NORMAL','2023-01-05'),
('정우진', 'woojin.jung@email.com',  '인천', 'NORMAL','2023-03-18'),
('강하늘', 'haneul.kang@email.com',  '서울', 'VIP',  '2023-05-22'),
('윤서준', 'seojun.yoon@email.com',  '광주', 'NORMAL','2023-07-30'),
('임나연', 'nayeon.lim@email.com',   '서울', 'VVIP', '2023-09-14'),
('오태양', 'taeyang.oh@email.com',   '대전', 'NORMAL','2023-11-01'),
('한지민', 'jimin.han@email.com',    '부산', 'VIP',  '2024-01-20');

-- =============================================
-- 4. orders (주문) → customers 참조
-- =============================================
CREATE TABLE orders (
    order_id    SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id),
    order_date  DATE         NOT NULL,
    status      VARCHAR(20)  DEFAULT 'completed',  -- completed / pending / cancelled
    total_amount NUMERIC(12,2)
);

INSERT INTO orders (customer_id, order_date, status, total_amount) VALUES
(1,  '2024-01-10', 'completed',  1600000),
(1,  '2024-02-15', 'completed',   435000),
(2,  '2024-01-20', 'completed',   230000),
(3,  '2024-02-01', 'completed',  1800000),
(3,  '2024-03-05', 'pending',     150000),
(4,  '2024-02-10', 'completed',    85000),
(5,  '2024-03-01', 'completed',    60000),
(6,  '2024-03-10', 'completed',   520000),
(7,  '2024-03-15', 'cancelled',   120000),
(8,  '2024-04-01', 'completed',  2100000),
(8,  '2024-04-10', 'completed',    67000),
(9,  '2024-04-05', 'completed',    45000),
(10, '2024-04-15', 'completed',   180000),
(1,  '2024-04-20', 'completed',   900000),
(2,  '2024-05-01', 'pending',      32000);

-- =============================================
-- 5. order_items (주문 항목) → orders, products 참조
--    customers ↔ orders ↔ order_items ↔ products ↔ categories
--    => 5개 테이블, 4-JOIN 자유롭게 가능
-- =============================================
CREATE TABLE order_items (
    item_id    SERIAL PRIMARY KEY,
    order_id   INT REFERENCES orders(order_id),
    product_id INT REFERENCES products(product_id),
    quantity   INT           NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL
);

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
-- order 1: 김민준 (갤럭시S24 + 아이폰15)
(1,  1,  1, 1200000),
(1,  2,  1, 1500000),  -- 실제 total은 예시값
-- order 2: 김민준 (소니헤드폰 + 나이키)
(2,  5,  1,  400000),
(2,  6,  1,  150000),
-- order 3: 이서연 (유니클로 + 폴로셔츠)
(3,  8,  2,   50000),
(3,  9,  1,   70000),
-- order 4: 박지호 (맥북)
(4,  3,  1, 1800000),
-- order 5: 박지호 (나이키)
(5,  6,  1,  150000),
-- order 6: 최아름 (아디다스후드티)
(6,  7,  1,   80000),
-- order 7: 정우진 (유니클로청바지)
(7,  8,  1,   50000),
-- order 8: 강하늘 (갤럭시탭 + 요가매트)
(8,  4,  1,  900000),
(8, 16,  1,   45000),
-- order 9: 윤서준 (나이키 - 취소)
(9,  6,  1,  150000),
-- order 10: 임나연 (아이폰15 + 맥북)
(10, 2,  1, 1500000),
(10, 3,  1, 1800000),
-- order 11: 임나연 (파이썬머신러닝 + LangChain)
(11, 13, 1,   35000),
(11, 14, 1,   32000),
-- order 12: 오태양 (제주감귤)
(12, 10, 1,   25000),
-- order 13: 한지민 (소니헤드폰)
(13, 5,  1,  400000),
-- order 14: 김민준 (갤럭시탭)
(14, 4,  1,  900000),
-- order 15: 이서연 (LangChain책)
(15, 14, 1,   32000);

-- =============================================
-- 확인 쿼리
-- =============================================
SELECT '=== 테이블 생성 완료 ===' AS message;
SELECT table_name,
       (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = t.table_name AND table_schema = 'public') AS column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
ORDER BY table_name;
