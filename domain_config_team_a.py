"""
Team A 도메인 설정 파일
이 파일만 팀별로 교체하면 다른 팀에서도 사용 가능하다.
"""

import os
from dotenv import load_dotenv
load_dotenv()

TEAM_ID          = "team_a"
TEAM_NAME        = "이커머스 운영팀"
TEAM_DESCRIPTION = "온라인 쇼핑몰 주문·상품·고객 데이터를 관리하는 팀"

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "sql_agent_db"),
    "user":     os.getenv("DB_USER", "jj"),
    "password": os.getenv("DB_PASSWORD", ""),
}

TABLE_DEFINITIONS = {
    "categories": {
        "description":      "상품 카테고리 분류 테이블",
        "business_meaning": "전자제품·의류·식품 등 상품을 분류하는 기준 코드 테이블",
        "primary_key":      "category_id",
        "columns": {
            "category_id":   "카테고리 고유 식별자 (PK)",
            "category_name": "카테고리 명칭 — 현재 값: 전자제품 / 의류 / 식품 / 도서 / 스포츠용품",
            "description":   "카테고리 상세 설명",
        },
        "notes": "마스터 데이터로, 변경 빈도가 낮다.",
    },
    "products": {
        "description":      "판매 상품 정보 테이블",
        "business_meaning": "현재 판매 중인 모든 상품의 기본 정보 (정가, 재고 포함)",
        "primary_key":      "product_id",
        "columns": {
            "product_id":   "상품 고유 식별자 (PK)",
            "category_id":  "카테고리 분류 — categories.category_id 참조 (FK)",
            "product_name": "상품 이름",
            "price":        "정가 (원 단위). 실제 판매가는 order_items.unit_price 참조",
            "stock":        "현재 재고 수량. 0이면 품절",
        },
        "notes": "매출 계산 시 반드시 order_items.unit_price를 사용해야 한다.",
    },
    "customers": {
        "description":      "고객 정보 테이블",
        "business_meaning": "쇼핑몰에 가입한 고객의 기본 정보 및 등급",
        "primary_key":      "customer_id",
        "columns": {
            "customer_id": "고객 고유 식별자 (PK)",
            "name":        "고객 실명",
            "email":       "고객 이메일 (UNIQUE)",
            "city":        "거주 도시 — 서울 / 부산 / 대구 / 인천 / 광주 / 대전",
            "grade":       "고객 등급 — NORMAL / VIP / VVIP",
            "join_date":   "가입일 (DATE)",
        },
        "notes": "grade 값은 대문자. 비교 시 'VIP'로 작성해야 한다.",
    },
    "orders": {
        "description":      "주문 헤더 테이블",
        "business_meaning": "고객이 생성한 주문 건수와 상태를 관리",
        "primary_key":      "order_id",
        "columns": {
            "order_id":     "주문 고유 식별자 (PK)",
            "customer_id":  "주문한 고객 — customers.customer_id 참조 (FK)",
            "order_date":   "주문 생성일 (DATE)",
            "status":       "주문 상태 — completed(완료) / pending(처리중) / cancelled(취소)",
            "total_amount": "주문 총액 요약값. 정확한 집계는 order_items에서 계산 권장",
        },
        "notes": "total_amount는 참고용. 정확한 매출은 order_items.unit_price * quantity를 SUM해야 한다.",
    },
    "order_items": {
        "description":      "주문 상세 항목 테이블",
        "business_meaning": "하나의 주문에 포함된 개별 상품 라인. 매출·수량 집계의 기준 테이블",
        "primary_key":      "item_id",
        "columns": {
            "item_id":    "주문 항목 고유 식별자 (PK)",
            "order_id":   "소속 주문 — orders.order_id 참조 (FK)",
            "product_id": "구매 상품 — products.product_id 참조 (FK)",
            "quantity":   "구매 수량",
            "unit_price": "실제 구매 단가 (원 단위). 할인·프로모션이 반영된 실거래가",
        },
        "notes": (
            "매출 = unit_price * quantity의 SUM. "
            "취소 주문 항목도 남아있으므로 orders.status='completed' 조건 필수."
        ),
    },
}

TABLE_RELATIONSHIPS = [
    "customers.customer_id  = orders.customer_id         (고객 → 주문)",
    "orders.order_id        = order_items.order_id       (주문 → 주문항목)",
    "order_items.product_id = products.product_id        (주문항목 → 상품)",
    "products.category_id   = categories.category_id     (상품 → 카테고리)",
]

FULL_JOIN_PATH = """
FROM customers c
JOIN orders      o   ON c.customer_id  = o.customer_id
JOIN order_items oi  ON o.order_id     = oi.order_id
JOIN products    p   ON oi.product_id  = p.product_id
JOIN categories  cat ON p.category_id  = cat.category_id
"""

GLOSSARY = {
    "매출":       "SUM(oi.unit_price * oi.quantity) — 완료 주문 기준",
    "주문금액":   "SUM(oi.unit_price * oi.quantity)",
    "구매금액":   "SUM(oi.unit_price * oi.quantity)",
    "총매출":     "SUM(oi.unit_price * oi.quantity) — 완료 주문 기준",
    "유효주문":   "orders.status = 'completed'",
    "취소주문":   "orders.status = 'cancelled'",
    "대기주문":   "orders.status = 'pending'",
    "우수고객":   "customers.grade IN ('VIP', 'VVIP')",
    "일반고객":   "customers.grade = 'NORMAL'",
    "판매량":     "SUM(oi.quantity)",
    "재고":       "products.stock",
    "정가":       "products.price",
    "실거래가":   "order_items.unit_price",
}

BUSINESS_RULES = [
    "매출·판매량 집계 시 status='cancelled'(취소) 주문은 반드시 제외한다.",
    "실제 판매 단가는 order_items.unit_price를 사용한다. products.price(정가)로 매출을 계산하지 않는다.",
    "고객 등급 우선순위: NORMAL < VIP < VVIP.",
    "한 주문(order_id)에 여러 상품(order_items)이 포함될 수 있다.",
    "날짜 필터는 order_date 컬럼을 기준으로 한다.",
]

QUERY_EXAMPLES = [
    {
        "question": "고객별 총 구매금액을 높은 순으로 보여줘",
        "sql": """SELECT c.name AS 고객명, SUM(oi.unit_price * oi.quantity) AS 총구매금액
FROM customers c
JOIN orders      o  ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id    = oi.order_id
WHERE o.status = 'completed'
GROUP BY c.name
ORDER BY 총구매금액 DESC;""",
    },
    {
        "question": "카테고리별 매출 합계를 알려줘",
        "sql": """SELECT cat.category_name AS 카테고리, SUM(oi.unit_price * oi.quantity) AS 총매출
FROM categories  cat
JOIN products    p   ON cat.category_id = p.category_id
JOIN order_items oi  ON p.product_id    = oi.product_id
JOIN orders      o   ON oi.order_id     = o.order_id
WHERE o.status = 'completed'
GROUP BY cat.category_name
ORDER BY 총매출 DESC;""",
    },
    {
        "question": "VIP 이상 고객이 구매한 상품과 카테고리를 보여줘",
        "sql": """SELECT c.name AS 고객명, c.grade AS 등급, p.product_name AS 상품명,
       cat.category_name AS 카테고리, oi.quantity AS 수량
FROM customers   c
JOIN orders      o   ON c.customer_id  = o.customer_id
JOIN order_items oi  ON o.order_id     = oi.order_id
JOIN products    p   ON oi.product_id  = p.product_id
JOIN categories  cat ON p.category_id  = cat.category_id
WHERE c.grade IN ('VIP', 'VVIP') AND o.status = 'completed'
ORDER BY c.grade DESC, c.name;""",
    },
]
