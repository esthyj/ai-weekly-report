"""In-memory session store for the local FastAPI web demo.

단일 사용자 로컬 실행 가정. 여러 세션이 동시에 진행되더라도 in-memory dict로 충분.
다중 워커/배포 환경으로 옮길 경우 Redis 등 외부 저장소로 교체 필요.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

SESSION_TTL_SECONDS = 60 * 30  # 30분


@dataclass
class StageState:
    """단계별(크롤링/요약/AI Lab) 상태와 진행 로그."""
    status: str = "idle"  # idle | running | done | error
    progress_log: list[str] = field(default_factory=list)
    error_msg: Optional[str] = None


@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=time.time)

    # 메타데이터 (호수, 날짜)
    number: Optional[str] = None
    date: Optional[str] = None

    # 단계별 상태
    crawl: StageState = field(default_factory=StageState)
    summarize: StageState = field(default_factory=StageState)
    ailab: StageState = field(default_factory=StageState)

    # 사용자가 입력한 크롤링 대상 기업 목록 (프론트의 진행 카드 표시에 사용)
    crawl_companies: list[str] = field(default_factory=list)

    # 데이터
    crawled_df: Optional[pd.DataFrame] = None
    selected_df: Optional[pd.DataFrame] = None
    summaries: list[dict] = field(default_factory=list)
    combined_summary: Optional[str] = None
    ailab_text: Optional[str] = None
    ppt_path: Optional[str] = None


class SessionStore:
    """동시 접근을 lock으로 보호하는 세션 저장소."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def create(self) -> SessionState:
        self._gc()
        sid = uuid.uuid4().hex
        session = SessionState(session_id=sid)
        with self._lock:
            self._sessions[sid] = session
        return session

    def get(self, sid: str) -> Optional[SessionState]:
        with self._lock:
            return self._sessions.get(sid)

    def require(self, sid: str) -> SessionState:
        session = self.get(sid)
        if session is None:
            raise KeyError(f"unknown session: {sid}")
        return session

    def _gc(self) -> None:
        now = time.time()
        with self._lock:
            stale = [
                sid for sid, s in self._sessions.items()
                if now - s.created_at > SESSION_TTL_SECONDS
            ]
            for sid in stale:
                self._sessions.pop(sid, None)


# 모듈 레벨 싱글톤
store = SessionStore()


def append_log(stage: StageState, message: str) -> None:
    """progress_cb로 주입할 헬퍼. 백그라운드 스레드에서 호출됨."""
    stage.progress_log.append(message)
