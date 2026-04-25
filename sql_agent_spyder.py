"""
MIS SQL Agent — Spyder 실행 버전
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
각 셀(# %%)을 Spyder에서 Ctrl+Enter로 순서대로 실행하세요.

실행 순서:
  Cell 1  → 라이브러리 import
  Cell 2  → DB 연결 테스트
  Cell 3  → 스키마 로드 확인
  Cell 4  → 노드 함수 정의 (backbone)
  Cell 5  → LangGraph 그래프 조립
  Cell 6  → 단일 질의 실행
  Cell 7  → 여러 질의 일괄 실행
  Cell 8  → 결과를 pandas DataFrame으로 확인
"""

# %%
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cell 1 : 라이브러리 import + 환경 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from dotenv import load_dotenv
load_dotenv()

import os
import time
import psycopg2
import psycopg2.extras
import pandas as pd
from typing import TypedDict, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

import domain_config_team_a as config   # 팀 설정 파일

print("✅ 라이브러리 import 완료")
print(f"   팀: {config.TEAM_NAME}")
print(f"   DB: {config.DB_CONFIG['user']}@{config.DB_CONFIG['host']}:{config.DB_CONFIG['port']}/{config.DB_CONFIG['dbname']}")
print(f"   OpenAI API Key: {'설정됨 ✅' if os.getenv('OPENAI_API_KEY') else '없음 ❌ → .env 파일 확인 필요'}")


# %%
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cell 2 : DB 연결 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_conn():
    return psycopg2.connect(
        host     = config.DB_CONFIG["host"],
        port     = config.DB_CONFIG["port"],
        dbname   = config.DB_CONFIG["dbname"],
        user     = config.DB_CONFIG["user"],
        password = config.DB_CONFIG["password"],
    )

try:
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT table_name,
               (SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name = t.table_name AND table_schema = 'public') AS cols
        FROM information_schema.tables t
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    print("✅ DB 연결 성공\n")
    print(f"{'테이블명':<20} {'컬럼 수':>6}")
    print("-" * 28)
    for table, cols in rows:
        print(f"{table:<20} {cols:>6}")
except Exception as e:
    print(f"❌ DB 연결 실패: {e}")


# %%
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cell 3 : DB 스키마 추출 및 확인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def load_schema() -> str:
    """DB에서 스키마를 추출하고 domain_config의 비즈니스 설명을 합쳐 텍스트로 반환."""
    conn   = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE'
        ORDER BY table_name
    """)
    tables = [r[0] for r in cursor.fetchall()]

    lines = ["[데이터베이스 스키마]", ""]
    for table in tables:
        # 컬럼 정보
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
        """, (table,))
        columns = cursor.fetchall()

        # PK
        cursor.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
            WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_name=%s
        """, (table,))
        pks = {r[0] for r in cursor.fetchall()}

        # FK
        cursor.execute("""
            SELECT kcu.column_name, ccu.table_name, ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name=tc.constraint_name AND ccu.table_schema=tc.table_schema
            WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_name=%s
        """, (table,))
        fks = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}

        tbl_def = config.TABLE_DEFINITIONS.get(table, {})
        desc    = tbl_def.get("description", "")
        lines.append(f"▶ {table}" + (f"  # {desc}" if desc else ""))

        biz = tbl_def.get("business_meaning", "")
        if biz:
            lines.append(f"  비즈니스 의미: {biz}")

        col_defs = tbl_def.get("columns", {})
        for col_name, data_type, nullable in columns:
            markers = []
            if col_name in pks:
                markers.append("PK")
            if col_name in fks:
                ref_t, ref_c = fks[col_name]
                markers.append(f"FK→{ref_t}.{ref_c}")
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            col_desc   = col_defs.get(col_name, "")
            desc_str   = f"  # {col_desc}" if col_desc else ""
            null_str   = "" if nullable == "YES" else " NOT NULL"
            lines.append(f"  - {col_name}{marker_str}: {data_type.upper()}{null_str}{desc_str}")

        notes = tbl_def.get("notes", "")
        if notes:
            lines.append(f"  ※ 주의: {notes}")
        lines.append("")

    cursor.close()
    conn.close()
    return "\n".join(lines)

# 스키마 로드 및 출력
DB_SCHEMA = load_schema()
print(DB_SCHEMA)


# %%
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cell 4 : GraphState + 노드 함수 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── GraphState ────────────────────────────────────
class GraphState(TypedDict):
    user_query:        str
    team_id:           str
    domain_context:    dict
    db_config:         dict
    db_schema:         str
    generated_sql:     str
    retry_count:       int
    validation_error:  Optional[str]
    query_result:      list
    execution_error:   Optional[str]
    response:          dict
    status:            str
    error_message:     Optional[str]

def initial_state(user_query: str, team_id: str = "team_a") -> GraphState:
    return GraphState(
        user_query=user_query, team_id=team_id,
        domain_context={}, db_config={}, db_schema="",
        generated_sql="", retry_count=0,
        validation_error=None, query_result=[],
        execution_error=None, response={},
        status="running", error_message=None,
    )

# ── Node 1 : domain_context_node ─────────────────
def domain_context_node(state: GraphState) -> dict:
    """팀 도메인 설정을 state에 주입한다."""
    domain_context = {
        "team_name":           config.TEAM_NAME,
        "team_description":    config.TEAM_DESCRIPTION,
        "table_definitions":   config.TABLE_DEFINITIONS,
        "table_relationships": config.TABLE_RELATIONSHIPS,
        "full_join_path":      config.FULL_JOIN_PATH,
        "glossary":            config.GLOSSARY,
        "business_rules":      config.BUSINESS_RULES,
        "query_examples":      config.QUERY_EXAMPLES,
    }
    return {"domain_context": domain_context, "db_config": config.DB_CONFIG}

# ── Node 2 : schema_loader_node ──────────────────
def schema_loader_node(state: GraphState) -> dict:
    """DB 스키마를 로드한다 (Cell 3에서 미리 로드된 DB_SCHEMA 재사용)."""
    return {"db_schema": DB_SCHEMA}

# ── Node 3 : sql_generator_node ──────────────────
FORBIDDEN_KEYWORDS = ["INSERT","UPDATE","DELETE","DROP","TRUNCATE","ALTER","CREATE"]
MAX_RETRY = 3

def _build_system_prompt(ctx: dict, schema: str) -> str:
    glossary_lines = "\n".join(f'  "{k}" → {v}' for k, v in ctx.get("glossary", {}).items())
    rules_lines    = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(ctx.get("business_rules", [])))
    rel_lines      = "\n".join(f"  - {r}" for r in ctx.get("table_relationships", []))
    examples       = ctx.get("query_examples", [])
    ex_text        = ""
    for i, ex in enumerate(examples, 1):
        ex_text += f"\n예시 {i})\n질문: {ex['question']}\nSQL:\n{ex['sql']}\n"

    return f"""당신은 PostgreSQL 전문가입니다. 사용자의 자연어 질문을 분석하여 정확한 SELECT SQL을 생성하세요.

[팀 정보]
팀 이름: {ctx.get('team_name','')}
팀 설명: {ctx.get('team_description','')}

{schema}

[테이블 관계]
{rel_lines}

[도메인 용어 사전]
{glossary_lines}

[비즈니스 규칙]
{rules_lines}

[SQL 생성 규칙]
1. SELECT 문만 생성한다.
2. 컬럼 이름은 반드시 스키마에 존재하는 이름만 사용한다.
3. 결과 컬럼에는 한국어 alias를 사용한다 (예: AS 고객명, AS 총매출).
4. SQL 코드 블록(```sql```) 없이 순수 SQL 텍스트만 반환한다.

[참고 예시]
{ex_text}"""

def sql_generator_node(state: GraphState) -> dict:
    """LLM으로 SQL을 생성한다. 재시도 시 실패 사유를 포함한다."""
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    sys_msg = SystemMessage(content=_build_system_prompt(
        state.get("domain_context", {}), state.get("db_schema", "")
    ))
    val_err = state.get("validation_error")
    if val_err:
        human_content = (
            f"질문: {state['user_query']}\n\n"
            f"[이전 실패 사유]\n{val_err}\n\n"
            "위 실패 사유를 수정하여 올바른 SQL을 다시 생성하라."
        )
    else:
        human_content = f"질문: {state['user_query']}"

    response = llm.invoke([sys_msg, HumanMessage(content=human_content)])
    sql = response.content.strip()
    if sql.startswith("```"):
        sql = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("```")).strip()

    return {"generated_sql": sql, "retry_count": state.get("retry_count", 0) + 1, "validation_error": None}

# ── Node 4 : sql_validator_node ──────────────────
def sql_validator_node(state: GraphState) -> dict:
    """SQL 안전성(키워드 차단)과 문법(EXPLAIN)을 검증한다."""
    sql = state.get("generated_sql", "")
    sql_upper = sql.upper()

    if not sql_upper.lstrip().startswith("SELECT"):
        return {"validation_error": "SELECT 문으로 시작하지 않습니다."}
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_upper:
            return {"validation_error": f"허용되지 않는 키워드: {kw}"}

    conn = None
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(f"EXPLAIN {sql}")
        cur.close()
        return {"validation_error": None}
    except psycopg2.Error as e:
        return {"validation_error": f"SQL 문법 오류: {e.pgerror or str(e)}"}
    finally:
        if conn:
            conn.close()

# ── Node 5 : sql_executor_node ───────────────────
def sql_executor_node(state: GraphState) -> dict:
    """검증된 SQL을 실행하고 결과를 반환한다."""
    conn = None
    try:
        conn   = get_conn()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        t0     = time.time()
        cursor.execute(state["generated_sql"])
        elapsed = round((time.time() - t0) * 1000, 2)
        rows    = [dict(r) for r in cursor.fetchmany(500)]
        cursor.close()
        return {"query_result": rows, "execution_error": None, "_exec_time_ms": elapsed}
    except psycopg2.Error as e:
        return {"query_result": [], "execution_error": str(e), "_exec_time_ms": 0}
    finally:
        if conn:
            conn.close()

# ── Node 6 : result_formatter_node ───────────────
def result_formatter_node(state: GraphState) -> dict:
    """결과를 자연어 답변으로 변환하고 최종 JSON을 조립한다."""
    rows = state.get("query_result", [])
    if rows:
        headers  = list(rows[0].keys())
        tbl_text = " | ".join(headers) + "\n"
        tbl_text += "\n".join(" | ".join(str(r.get(h,"")) for h in headers) for r in rows[:20])
        if len(rows) > 20:
            tbl_text += f"\n... (총 {len(rows)}행 중 20행 표시)"
    else:
        tbl_text = "결과 없음"

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    answer = llm.invoke([
        SystemMessage(content=(
            "데이터 분석 결과를 비즈니스 담당자에게 간결하게 한국어로 설명하세요. "
            "숫자는 천 단위 구분 기호(,)를 사용하고 금액은 '원' 단위로 표기하세요."
        )),
        HumanMessage(content=f"질문: {state['user_query']}\n\n결과:\n{tbl_text}\n\n위 결과를 답변해 주세요.")
    ]).content.strip()

    response = {
        "status":  "success",
        "answer":  answer,
        "sql":     state.get("generated_sql", ""),
        "result":  rows,
        "metadata": {
            "row_count":         len(rows),
            "execution_time_ms": state.get("_exec_time_ms", 0),
            "retry_count":       state.get("retry_count", 0),
            "team_id":           state.get("team_id", ""),
        },
    }
    return {"response": response, "status": "success"}

# ── Node 7 : error_handler_node ──────────────────
def error_handler_node(state: GraphState) -> dict:
    """재시도 초과 시 에러 응답을 반환한다."""
    val_err   = state.get("validation_error", "알 수 없는 오류")
    retry_cnt = state.get("retry_count", 0)
    response  = {
        "status": "error",
        "answer": f"'{state.get('user_query','')}' 에 대한 SQL을 생성하지 못했습니다. 질문을 더 구체적으로 입력해 주세요.",
        "sql":    state.get("generated_sql", ""),
        "result": [],
        "metadata": {
            "row_count": 0, "execution_time_ms": 0,
            "retry_count": retry_cnt, "team_id": state.get("team_id", ""),
            "error_detail": val_err,
        },
    }
    return {"response": response, "status": "error", "error_message": f"{retry_cnt}회 시도 실패: {val_err}"}

print("✅ 모든 노드 함수 정의 완료")
print("   정의된 노드: domain_context / schema_loader / sql_generator")
print("               sql_validator / sql_executor / result_formatter / error_handler")


# %%
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cell 5 : LangGraph 그래프 조립
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def route_after_validation(state: GraphState) -> str:
    if state.get("validation_error") is None:
        return "sql_executor"
    if state.get("retry_count", 0) < MAX_RETRY:
        return "sql_generator"
    return "error_handler"

graph = StateGraph(GraphState)
graph.add_node("domain_context",   domain_context_node)
graph.add_node("schema_loader",    schema_loader_node)
graph.add_node("sql_generator",    sql_generator_node)
graph.add_node("sql_validator",    sql_validator_node)
graph.add_node("sql_executor",     sql_executor_node)
graph.add_node("result_formatter", result_formatter_node)
graph.add_node("error_handler",    error_handler_node)

graph.add_edge(START,            "domain_context")
graph.add_edge("domain_context", "schema_loader")
graph.add_edge("schema_loader",  "sql_generator")
graph.add_edge("sql_generator",  "sql_validator")
graph.add_conditional_edges(
    "sql_validator", route_after_validation,
    {"sql_executor": "sql_executor", "sql_generator": "sql_generator", "error_handler": "error_handler"},
)
graph.add_edge("sql_executor",    "result_formatter")
graph.add_edge("result_formatter", END)
graph.add_edge("error_handler",   END)

agent = graph.compile()
print("✅ LangGraph 그래프 조립 완료")
print(f"   등록된 노드: {list(agent.nodes.keys())}")


# %%
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cell 6 : 단일 질의 실행 — 여기서 질문을 바꿔가며 실험
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUERY = "고객별 총 구매금액을 높은 순으로 보여줘"   # ← 이 부분을 바꿔서 실험

state  = initial_state(QUERY, team_id="team_a")
result = agent.invoke(state)
resp   = result["response"]

print("=" * 60)
print(f"[질문] {QUERY}")
print("=" * 60)
print(f"\n[답변]\n{resp['answer']}")
print(f"\n[실행된 SQL]\n{resp['sql']}")
print(f"\n[메타데이터]")
m = resp["metadata"]
print(f"  실행시간: {m['execution_time_ms']}ms | 결과: {m['row_count']}행 | 재시도: {m['retry_count']}회")


# %%
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cell 7 : 여러 질의 일괄 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TEST_QUERIES = [
    "고객별 총 구매금액을 높은 순으로 보여줘",
    "카테고리별 매출 합계를 알려줘",
    "VIP 이상 고객이 구매한 상품과 카테고리를 보여줘",
    "가장 많이 팔린 상품 TOP 3은?",
]

all_results = []
for q in TEST_QUERIES:
    print(f"\n실행 중: {q}")
    r = agent.invoke(initial_state(q, "team_a"))["response"]
    all_results.append({
        "질문":    q,
        "상태":    r["status"],
        "답변":    r["answer"],
        "SQL":     r["sql"],
        "결과행수": r["metadata"]["row_count"],
        "실행시간(ms)": r["metadata"]["execution_time_ms"],
        "재시도":  r["metadata"]["retry_count"],
        "result":  r["result"],
    })
    print(f"  → {r['status']} | {r['metadata']['row_count']}행 | {r['metadata']['execution_time_ms']}ms")

print(f"\n✅ {len(all_results)}개 질의 완료")


# %%
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cell 8 : 결과를 pandas DataFrame으로 확인
#          Spyder Variable Explorer에서 클릭해서 볼 수 있음
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 실행 요약 DataFrame (Variable Explorer에서 확인 가능)
df_summary = pd.DataFrame([{
    "질문":       r["질문"],
    "상태":       r["상태"],
    "결과행수":   r["결과행수"],
    "실행시간(ms)": r["실행시간(ms)"],
    "재시도":     r["재시도"],
} for r in all_results])

print("=== 실행 요약 ===")
print(df_summary.to_string(index=False))

# 개별 쿼리 결과 DataFrame (질의 인덱스로 선택)
RESULT_IDX = 0   # ← 0~3 중 확인하고 싶은 질의 번호
df_result = pd.DataFrame(all_results[RESULT_IDX]["result"])

print(f"\n=== 질의 {RESULT_IDX}: '{all_results[RESULT_IDX]['질문']}' 결과 ===")
print(df_result.to_string(index=False) if not df_result.empty else "결과 없음")
print(f"\n[실행된 SQL]\n{all_results[RESULT_IDX]['SQL']}")
print(f"\n[답변]\n{all_results[RESULT_IDX]['답변']}")

# Variable Explorer에서 확인할 변수들:
#   df_summary  → 전체 실행 요약
#   df_result   → 선택한 질의의 결과 테이블
