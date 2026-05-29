"""FastAPI entrypoint for the local AI Weekly Report web demo.

Run with:
    uvicorn app:app --reload --port 8000

Then visit http://localhost:8000
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.ailab_summarize import ailab_summarized
from src.config import OUTPUT_DIR, PPT_TEMPLATE_FILE, ensure_directories
from src.news_crawler import CrawlerConfig, crawl_news, select_articles_by_indices
from src.news_summarize import combine_summaries, generate_summaries
from src.ppt_maker import create_report
from src.session_store import SessionState, StageState, store

load_dotenv()
ensure_directories()

STATIC_DIR = Path(__file__).parent / "web" / "static"

app = FastAPI(title="AI Weekly Report — Web Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.getenv("ANTHROPIC_API_KEY"):
    @app.middleware("http")
    async def missing_api_key(request, call_next):  # pragma: no cover
        return await _503("ANTHROPIC_API_KEY 환경변수가 설정되어 있지 않습니다.")


async def _503(message: str):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={"detail": message})


# ============================================================
# Helpers
# ============================================================

def _make_progress_cb(stage: StageState):
    def cb(message: str) -> None:
        stage.progress_log.append(message)
    return cb


def _run_stage(stage: StageState, fn) -> None:
    """Wrap a background task so exceptions land in stage.error_msg
    rather than leaving status stuck at 'running'."""
    stage.status = "running"
    stage.error_msg = None
    try:
        fn()
        stage.status = "done"
    except Exception as e:  # noqa: BLE001
        stage.status = "error"
        stage.error_msg = str(e)
        stage.progress_log.append(f"❌ 오류 발생: {e}")


async def _sse_stream(stage: StageState):
    """Yield progress_log entries as Server-Sent Events until the stage finishes."""
    sent = 0
    # Yield existing buffered lines first (handles late subscribers).
    while True:
        # Snapshot current log length
        log_len = len(stage.progress_log)
        while sent < log_len:
            line = stage.progress_log[sent]
            sent += 1
            yield f"event: log\ndata: {json.dumps(line, ensure_ascii=False)}\n\n"

        if stage.status in ("done", "error"):
            payload = {"status": stage.status, "error": stage.error_msg}
            yield f"event: end\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            return

        await asyncio.sleep(0.5)


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """기사 표시용으로 안전한 컬럼만 직렬화."""
    if df is None or df.empty:
        return []
    cols = ["category", "company", "search_keyword", "score", "title", "link", "published"]
    return [
        {col: row.get(col, "") for col in cols}
        for _, row in df.reset_index(drop=True).iterrows()
    ]


# ============================================================
# Schemas
# ============================================================

class SessionCreateBody(BaseModel):
    companies: list[str]
    required_keyword: str = "AI"
    days: int = 14


class SelectBody(BaseModel):
    indices: list[int]
    number: str
    date: str


class FinalizeBody(BaseModel):
    include_indices: list[int]


class AilabBody(BaseModel):
    ailab_content: str


class PptBody(BaseModel):
    combined_summary: str
    ailab_text: str


# ============================================================
# Routes
# ============================================================

@app.post("/api/session")
def create_session(body: SessionCreateBody):
    """새 세션 생성 + 즉시 크롤링 백그라운드 시작."""
    companies = [c.strip() for c in body.companies if c and c.strip()]
    if not companies:
        raise HTTPException(400, detail="최소 1개 이상의 기업을 입력해야 합니다.")
    if body.days < 1:
        raise HTTPException(400, detail="검색 기간은 1일 이상이어야 합니다.")

    cfg = CrawlerConfig(
        companies=companies,
        required_keyword=body.required_keyword.strip(),
        days=body.days,
    )

    session = store.create()
    session.crawl_companies = companies
    cb = _make_progress_cb(session.crawl)

    def task():
        df = crawl_news(cfg=cfg, progress_cb=cb)
        session.crawled_df = df

    threading.Thread(
        target=_run_stage, args=(session.crawl, task), daemon=True
    ).start()
    return {"session_id": session.session_id, "companies": companies}


@app.get("/api/{sid}/crawl/stream")
async def crawl_stream(sid: str):
    session = _require(sid)
    return StreamingResponse(_sse_stream(session.crawl), media_type="text/event-stream")


@app.get("/api/{sid}/articles")
def get_articles(sid: str):
    session = _require(sid)
    if session.crawl.status == "error":
        raise HTTPException(500, detail=session.crawl.error_msg or "crawl error")
    if session.crawl.status != "done":
        raise HTTPException(409, detail="크롤링이 아직 완료되지 않았습니다.")
    return {"articles": _df_to_records(session.crawled_df)}


@app.post("/api/{sid}/select")
def select_articles_endpoint(sid: str, body: SelectBody):
    session = _require(sid)
    if session.crawled_df is None:
        raise HTTPException(409, detail="크롤링 결과가 없습니다.")

    bad = [i for i in body.indices if i < 1 or i > len(session.crawled_df)]
    if bad or not body.indices:
        raise HTTPException(400, detail=f"잘못된 인덱스: {bad or 'empty'}")

    session.selected_df = select_articles_by_indices(
        session.crawled_df, body.indices, save_excel=False
    )
    session.number = body.number
    session.date = body.date
    # 재선택 시 이후 단계 상태 초기화
    session.summarize = StageState()
    session.ailab = StageState()
    session.summaries = []
    session.combined_summary = None
    session.ailab_text = None
    session.ppt_path = None
    return {"selected": len(session.selected_df)}


@app.post("/api/{sid}/summarize")
def start_summarize(sid: str):
    session = _require(sid)
    if session.selected_df is None or session.selected_df.empty:
        raise HTTPException(409, detail="먼저 기사를 선택하세요.")

    # 재요약 호출이면 이전 상태 초기화
    session.summarize = StageState()
    session.summaries = []
    session.combined_summary = None
    cb = _make_progress_cb(session.summarize)

    def task():
        result = generate_summaries(session.selected_df, progress_cb=cb)
        if not result:
            raise RuntimeError("모든 기사 요약에 실패했습니다.")
        session.summaries = result

    threading.Thread(
        target=_run_stage, args=(session.summarize, task), daemon=True
    ).start()
    return {"status": "started"}


@app.get("/api/{sid}/summarize/stream")
async def summarize_stream(sid: str):
    session = _require(sid)
    return StreamingResponse(
        _sse_stream(session.summarize), media_type="text/event-stream"
    )


@app.get("/api/{sid}/summaries")
def get_summaries(sid: str):
    session = _require(sid)
    if session.summarize.status == "error":
        raise HTTPException(500, detail=session.summarize.error_msg or "summarize error")
    if session.summarize.status != "done":
        raise HTTPException(409, detail="요약이 아직 완료되지 않았습니다.")
    return {"summaries": session.summaries}


@app.post("/api/{sid}/finalize")
def finalize(sid: str, body: FinalizeBody):
    session = _require(sid)
    if not session.summaries:
        raise HTTPException(409, detail="요약 결과가 없습니다.")
    bad = [i for i in body.include_indices if not any(s["index"] == i for s in session.summaries)]
    if bad or not body.include_indices:
        raise HTTPException(400, detail=f"잘못된 인덱스: {bad or 'empty'}")
    session.combined_summary = combine_summaries(session.summaries, body.include_indices)
    return {"combined_summary": session.combined_summary}


@app.post("/api/{sid}/ailab")
def start_ailab(sid: str, body: AilabBody):
    session = _require(sid)
    if not session.combined_summary:
        raise HTTPException(409, detail="먼저 요약을 확정하세요 (/finalize).")
    if not session.number or not session.date:
        raise HTTPException(409, detail="메타데이터(호수/날짜)가 없습니다.")

    ailab_content = body.ailab_content.strip()
    if len(ailab_content) < 10:
        raise HTTPException(400, detail="부서 내 진행상황을 10자 이상 입력하세요.")

    session.ailab = StageState()
    session.ailab_text = None
    session.ppt_path = None
    cb = _make_progress_cb(session.ailab)

    def task():
        cb("🔬 부서 내용 요약 중...")
        ailab_text = ailab_summarized(ailab_content)
        if not ailab_text:
            raise RuntimeError("부서 내용 요약 생성에 실패했습니다.")
        session.ailab_text = ailab_text
        cb("✅ 부서 내용 요약 완료")

    threading.Thread(
        target=_run_stage, args=(session.ailab, task), daemon=True
    ).start()
    return {"status": "started"}


@app.get("/api/{sid}/ailab/stream")
async def ailab_stream(sid: str):
    session = _require(sid)
    return StreamingResponse(
        _sse_stream(session.ailab), media_type="text/event-stream"
    )


@app.get("/api/{sid}/final-content")
def get_final_content(sid: str):
    """최종 확인 페이지에 표시할 뉴스 요약 + 부서 내용 요약을 반환."""
    session = _require(sid)
    if not session.combined_summary:
        raise HTTPException(409, detail="뉴스 요약이 아직 확정되지 않았습니다.")
    if session.ailab.status != "done" or not session.ailab_text:
        raise HTTPException(409, detail="부서 내용 요약이 아직 완료되지 않았습니다.")
    return {
        "combined_summary": session.combined_summary,
        "ailab_text": session.ailab_text,
    }


@app.post("/api/{sid}/ppt")
def generate_ppt(sid: str, body: PptBody):
    """최종 확인 페이지에서 사용자가 (편집한) 본문을 보내면 그대로 PPT에 반영."""
    session = _require(sid)
    if not session.number or not session.date:
        raise HTTPException(409, detail="메타데이터(호수/날짜)가 없습니다.")

    combined = body.combined_summary.strip()
    ailab = body.ailab_text.strip()
    if not combined or not ailab:
        raise HTTPException(400, detail="뉴스 요약과 부서 내용 요약 모두 비어있지 않아야 합니다.")

    # 사용자가 편집한 최종본을 세션에도 반영 (재요청·다운로드 일관성)
    session.combined_summary = combined
    session.ailab_text = ailab

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"AIWeeklyReport_{timestamp}.pptx"
    create_report(
        pptx_in=str(PPT_TEMPLATE_FILE),
        pptx_out=str(output_path),
        number=session.number,
        date=session.date,
        text1=combined,
        text2=ailab,
    )
    session.ppt_path = str(output_path)
    return {"filename": output_path.name}


@app.get("/api/{sid}/download")
def download(sid: str):
    session = _require(sid)
    if not session.ppt_path or not Path(session.ppt_path).exists():
        raise HTTPException(404, detail="PPT 파일을 찾을 수 없습니다.")
    return FileResponse(
        session.ppt_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=Path(session.ppt_path).name,
    )


def _require(sid: str) -> SessionState:
    session = store.get(sid)
    if session is None:
        raise HTTPException(404, detail="세션을 찾을 수 없습니다. (TTL 30분 초과)")
    return session


# ============================================================
# Static
# ============================================================

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
