# MIS SQL Agent — Spyder 버전 설계 문서

> 작성일: 2026-04-25  
> 목적: Spyder IDE에서 셀 단위로 실행·실험할 수 있는 SQL Agent 구현  
> 스택: Python 3.9 · LangChain · LangGraph · OpenAI GPT-4o · PostgreSQL 15 · pandas

---

## 1. 개요

### 1.1 이 버전의 목적

모듈 분산 버전(`mis_sql_agent`)은 운영/배포에 적합한 구조지만,  
코드를 처음 이해하거나 SQL 생성 결과를 실험할 때는 파일을 여러 개 열어야 하는 불편함이 있다.

**Spyder 버전은 다음을 목표로 한다:**
- 파일 1개(`sql_agent_spyder.py`)에서 전체 흐름을 한눈에 파악
- 셀(`# %%`) 단위로 단계별 실행 및 중간 결과 확인
- 질문을 바꿔가며 빠르게 실험 가능
- 결과를 pandas DataFrame으로 Spyder Variable Explorer에서 확인

### 1.2 두 버전 비교

| 항목 | 모듈 버전 (`mis_sql_agent`) | Spyder 버전 (`mis_sql_agent_spyder`) |
|------|----------------------------|--------------------------------------|
| 목적 | 운영 배포, 팀별 확장 | 개발·실험·학습 |
| 파일 수 | 16개 (분산 모듈) | 2개 (단일 파일) |
| 실행 방식 | `python main.py` | Spyder `Ctrl+Enter` 셀 실행 |
| 결과 확인 | 터미널 출력 | pandas DataFrame + Variable Explorer |
| 실험 방법 | 코드 수정 후 전체 재실행 | Cell 6 `QUERY` 변수만 수정 |
| 노드 구조 | 파일별 분리 | 단일 파일 내 함수로 통합 |

---

## 2. 파일 구조

```
mis_sql_agent_spyder/
│
├── sql_agent_spyder.py       ← 메인 파일 (8개 셀, 모든 로직 포함)
├── domain_config_team_a.py   ← Team A 도메인 설정 (팀별 교체 대상)
├── init_db.sql               ← PostgreSQL 샘플 DB 초기화 스크립트
├── .env                      ← 환경변수 (API 키, DB 정보) — Git 제외
├── .env.example              ← 환경변수 작성 예시
└── PROJECT_SUMMARY_SPYDER.md ← 본 문서
```

---

## 3. 셀 구성 및 실행 순서

`sql_agent_spyder.py`는 8개의 셀로 구성되어 있다.  
**Spyder에서 위에서부터 순서대로 `Ctrl+Enter`로 실행한다.**

```
Cell 1  라이브러리 import + 환경 설정 확인
  │
Cell 2  DB 연결 테스트 (테이블 목록 출력)
  │
Cell 3  DB 스키마 자동 추출 및 확인
  │
Cell 4  GraphState + 7개 노드 함수 정의 (backbone 전체)
  │
Cell 5  LangGraph 그래프 조립 + 컴파일
  │
Cell 6  단일 질의 실행  ← QUERY 변수를 바꿔가며 실험
  │
Cell 7  여러 질의 일괄 실행
  │
Cell 8  pandas DataFrame으로 결과 확인 (Variable Explorer 연동)
```

### 셀별 상세 설명

#### Cell 1 — 환경 설정
```python
# 수행 내용
- dotenv로 .env 파일 로드
- 필요한 라이브러리 전체 import
- OpenAI API Key 설정 여부 자동 확인
- DB 연결 정보 출력

# 확인 포인트
✅ OpenAI API Key: 설정됨  → 정상
❌ OpenAI API Key: 없음    → .env 파일에 OPENAI_API_KEY 입력 필요
```

#### Cell 2 — DB 연결 테스트
```python
# 수행 내용
- PostgreSQL에 실제 접속
- public 스키마의 테이블 목록과 컬럼 수 출력

# 출력 예시
테이블명             컬럼 수
categories              3
customers               6
order_items             5
orders                  5
products                5
```

#### Cell 3 — 스키마 추출
```python
# 수행 내용
- information_schema에서 컬럼 정보 조회
- pg_constraint에서 PK/FK 관계 추출
- domain_config의 비즈니스 설명과 합쳐 텍스트 생성
- 전역 변수 DB_SCHEMA에 저장 (Cell 4 이후 재사용)

# 출력 예시
▶ customers  # 고객 정보 테이블
  비즈니스 의미: 쇼핑몰에 가입한 고객의 기본 정보 및 등급
  - customer_id [PK]: INTEGER NOT NULL  # 고객 고유 식별자
  - grade: CHARACTER VARYING  # NORMAL / VIP / VVIP
  ※ 주의: grade 값은 대문자로만 저장된다.
```

#### Cell 4 — 노드 함수 정의
```python
# 수행 내용
- GraphState TypedDict 정의
- initial_state() 헬퍼 함수
- 7개 노드 함수 모두 정의:
    domain_context_node  → 도메인 설정 주입
    schema_loader_node   → 스키마 로드 (DB_SCHEMA 재사용)
    sql_generator_node   → LLM → SQL 생성
    sql_validator_node   → 안전성·문법 검증
    sql_executor_node    → SQL 실행
    result_formatter_node → 자연어 답변 + JSON 조립
    error_handler_node   → 재시도 초과 에러 처리
```

#### Cell 5 — 그래프 조립
```python
# 수행 내용
- LangGraph StateGraph에 7개 노드 등록
- 엣지 연결 (선형 구간 + 조건 분기)
- agent = graph.compile()

# 조건 분기 (route_after_validation)
validation_error == None        → sql_executor     (성공)
validation_error + retry < 3    → sql_generator    (재시도)
validation_error + retry >= 3   → error_handler    (실패)
```

#### Cell 6 — 단일 질의 실험
```python
# 사용 방법
QUERY = "여기에 질문을 입력하세요"   # ← 이 줄만 수정

# 실험 예시
QUERY = "고객별 총 구매금액을 높은 순으로 보여줘"
QUERY = "카테고리별 매출을 알려줘"
QUERY = "2024년 1분기 VIP 고객의 구매 내역은?"
QUERY = "재고가 30개 미만인 상품은?"

# 출력 내용
[답변]   → LLM이 생성한 자연어 설명
[SQL]    → 실제 실행된 SQL 쿼리
[메타]   → 실행시간, 결과행수, 재시도횟수
```

#### Cell 7 — 일괄 실행
```python
# 수행 내용
- TEST_QUERIES 리스트의 질의를 순서대로 실행
- all_results 리스트에 전체 결과 저장

# TEST_QUERIES 수정 방법
TEST_QUERIES = [
    "질문1",
    "질문2",
    "질문3",
]
```

#### Cell 8 — DataFrame 확인
```python
# 생성되는 변수 (Variable Explorer에서 클릭해서 확인)
df_summary   → 전체 실행 요약 (질문·상태·행수·시간·재시도)
df_result    → 선택한 질의의 결과 테이블

# RESULT_IDX 수정으로 확인할 질의 선택
RESULT_IDX = 0   # 첫 번째 질의 결과
RESULT_IDX = 2   # 세 번째 질의 결과
```

---

## 4. LangGraph Workflow

```
START
  │
  ▼
[domain_context_node]
  │  domain_config_team_a.py를 읽어 domain_context, db_config 주입
  ▼
[schema_loader_node]
  │  Cell 3에서 미리 추출된 DB_SCHEMA를 state에 주입
  ▼
[sql_generator_node] ◄──────────────────────────────┐
  │  System: 스키마 + 용어사전 + 규칙 + 예시        │
  │  Human:  사용자 질의 (재시도 시: 실패 사유 포함) │
  ▼                                                  │ 재시도
[sql_validator_node]                                 │ (retry < 3)
  │  1단계: SELECT 문 확인, 금지 키워드 차단         │
  │  2단계: EXPLAIN으로 문법 오류 감지               │
  │                                                  │
  ├─ 통과 ──────────────────────────────────────────►│
  ├─ 실패 + retry < 3 ──────────────────────────────┘
  └─ 실패 + retry ≥ 3 ──► [error_handler_node] ──► END
  ▼ (통과)
[sql_executor_node]
  │  psycopg2 RealDictCursor로 실행 → {컬럼:값} dict 리스트 반환
  ▼
[result_formatter_node]
  │  LLM으로 자연어 답변 생성
  │  response JSON 조립 (answer / sql / result / metadata)
  ▼
END
```

---

## 5. GraphState 구조

```python
class GraphState(TypedDict):
    # 입력
    user_query:        str           # 사용자 자연어 질의
    team_id:           str           # 팀 식별자

    # 도메인 주입
    domain_context:    dict          # 용어사전, 비즈니스 규칙, 테이블 정의
    db_config:         dict          # DB 연결 정보

    # 중간 산출물
    db_schema:         str           # DB 스키마 요약 텍스트
    generated_sql:     str           # LLM이 생성한 SQL
    retry_count:       int           # 재시도 횟수 (0~3)
    validation_error:  Optional[str] # SQL 검증 실패 사유
    query_result:      list          # SQL 실행 결과
    execution_error:   Optional[str] # SQL 실행 실패 사유

    # 최종 출력
    response:          dict          # UI 연동용 JSON

    # 흐름 제어
    status:            str           # "running" | "success" | "error"
    error_message:     Optional[str]
```

---

## 6. 최종 응답(response) 구조

```json
{
  "status": "success",
  "answer": "고객별 총 구매금액 기준으로 김민준 고객이 3,600,000원으로 1위입니다.",
  "sql":    "SELECT c.name AS 고객명, SUM(oi.unit_price * oi.quantity) AS 총구매금액 ...",
  "result": [
    {"고객명": "김민준", "총구매금액": 3600000},
    {"고객명": "임나연", "총구매금액": 3300000}
  ],
  "metadata": {
    "row_count":          10,
    "execution_time_ms":  38,
    "retry_count":        0,
    "team_id":            "team_a"
  }
}
```

---

## 7. domain_config_team_a.py 구성

LLM이 DB를 이해하기 위한 5가지 정보를 담은 팀 설정 파일.  
**새 팀 추가 시 이 파일만 새로 작성하면 된다.**

| 항목 | 내용 | 효과 |
|------|------|------|
| `TABLE_DEFINITIONS` | 테이블·컬럼 비즈니스 설명, 허용값 | 잘못된 컬럼 사용 방지 |
| `TABLE_RELATIONSHIPS` | JOIN 경로 명시 | 정확한 JOIN 생성 |
| `GLOSSARY` | "매출" → SQL 표현 매핑 | 용어 오해 방지 |
| `BUSINESS_RULES` | 취소 주문 제외 등 암묵적 규칙 | 비즈니스 로직 자동 반영 |
| `QUERY_EXAMPLES` | 자주 묻는 질문 + 정답 SQL | SQL 생성 정확도 향상 |

---

## 8. 샘플 데이터베이스 구조

`init_db.sql`로 생성되는 5개 테이블 (4-JOIN 실험 가능):

```
categories (5건)
    └── products (18건)
                └── order_items (21건)
customers (10건)
    └── orders (15건)
              └── order_items (21건)
```

**4테이블 JOIN 예시:**
```sql
SELECT c.name AS 고객명, o.order_date AS 주문일,
       p.product_name AS 상품명, cat.category_name AS 카테고리
FROM customers   c
JOIN orders      o   ON c.customer_id  = o.customer_id
JOIN order_items oi  ON o.order_id     = oi.order_id
JOIN products    p   ON oi.product_id  = p.product_id
JOIN categories  cat ON p.category_id  = cat.category_id
WHERE o.status = 'completed';
```

---

## 9. 환경 설정 및 실행 방법

### 9-1. 설치

```bash
# 저장소 클론
git clone https://github.com/saigomad7/mis_sql_agent_spyder.git
cd mis_sql_agent_spyder

# 패키지 설치
pip install langchain langchain-community langchain-openai \
            langgraph psycopg2-binary python-dotenv openai pandas

# PostgreSQL 설치 및 시작 (Mac)
brew install postgresql@15
brew services start postgresql@15
```

### 9-2. DB 초기화

```bash
psql -U $(whoami) -d postgres -c "CREATE DATABASE sql_agent_db;"
psql -U $(whoami) -d sql_agent_db -f init_db.sql
```

### 9-3. 환경변수 설정

```bash
cp .env.example .env
# .env 파일 열어서 OPENAI_API_KEY와 DB_USER 입력
```

### 9-4. Spyder에서 실행

```
1. Spyder 실행
2. File → Open → sql_agent_spyder.py
3. Cell 1부터 순서대로 Ctrl+Enter
4. Cell 6의 QUERY = "..." 를 바꿔가며 실험
5. Cell 8 실행 후 Variable Explorer에서 df_result 클릭
```

---

## 10. 새 팀 적용 방법

```bash
# 1. 새 도메인 설정 파일 작성
cp domain_config_team_a.py domain_config_team_b.py
# → domain_config_team_b.py 내용 수정 (DB, 용어, 규칙 등)

# 2. sql_agent_spyder.py Cell 1 상단 한 줄 수정
import domain_config_team_b as config   # ← team_a → team_b

# 3. Cell 1부터 다시 실행
```

---

## 11. 향후 고도화 방향

| 항목 | 방법 |
|------|------|
| 질의 명확화 | 모호한 질문에 추가 질문하는 `clarifier_node` 삽입 |
| 결과 시각화 | Cell 8에 `matplotlib` / `plotly` 차트 추가 |
| 쿼리 이력 저장 | `all_results`를 CSV로 저장하는 셀 추가 |
| 다중 팀 실험 | Cell 6에서 `team_id` 파라미터만 바꿔 팀별 비교 |
| 운영 전환 | 검증 완료 후 모듈 버전(`mis_sql_agent`)으로 이관 |
