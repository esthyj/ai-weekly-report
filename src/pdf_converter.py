"""PPTX → PDF 변환 (LibreOffice headless).

`soffice --headless --convert-to pdf` 로 변환한다. 템플릿 레이아웃과 한화고딕
폰트를 그대로 유지하려면 LibreOffice 가 필요하며, 없으면 None 을 반환해
호출자가 친절한 오류 메시지를 내도록 한다(파이프라인은 멈추지 않음).
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

from .config import FONTS_DIR

# 변환 PDF 가 한화고딕으로 렌더되도록, 레포 fonts/ 를 fontconfig 가 보는 위치로 한 번 등록.
_USER_FONT_DIR = Path.home() / ".local" / "share" / "fonts" / "hanwha"
_fonts_registered = False


def _ensure_fonts_registered() -> None:
    """레포 fonts/ 의 한화고딕 ttf 를 사용자 폰트 디렉토리에 복사하고 fc-cache 갱신.
    LibreOffice 가 PPTX 의 '한화고딕' 글꼴명을 찾아 대체 없이 임베드하게 한다.
    폰트가 없거나 fontconfig 가 없으면 조용히 넘어간다(다른 글꼴로 대체될 뿐 변환은 됨)."""
    global _fonts_registered
    if _fonts_registered:
        return
    _fonts_registered = True  # 실패해도 매 변환마다 재시도하지 않음
    try:
        if not FONTS_DIR.exists():
            return
        ttfs = list(FONTS_DIR.glob("*.ttf"))
        if not ttfs:
            return
        _USER_FONT_DIR.mkdir(parents=True, exist_ok=True)
        copied = False
        for src in ttfs:
            dst = _USER_FONT_DIR / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                copied = True
        if copied and shutil.which("fc-cache"):
            subprocess.run(["fc-cache", "-f", str(_USER_FONT_DIR)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=60, check=False)
    except Exception:
        pass  # best-effort — 폰트 등록 실패해도 변환 자체는 진행


def _find_soffice() -> Optional[str]:
    """soffice/libreoffice 실행 파일 경로. 없으면 None."""
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    # PATH 에 없을 때 흔한 설치 경로 폴백
    for cand in (
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/opt/libreoffice/program/soffice",
        "/snap/bin/libreoffice",
    ):
        if Path(cand).exists():
            return cand
    return None


def convert_pptx_to_pdf(pptx_path: Union[str, Path], timeout: int = 120) -> Optional[Path]:
    """PPTX 를 같은 폴더에 동일 이름 .pdf 로 변환하고 경로를 반환. 실패 시 None.

    이미 PPTX 보다 최신인 PDF 가 있으면 재변환하지 않는다(다운로드 반복 시 캐시).
    동시 변환 시 LibreOffice 프로필 락 충돌을 피하려 호출마다 임시 UserInstallation 사용.
    """
    pptx = Path(pptx_path)
    if not pptx.exists():
        return None

    pdf = pptx.with_suffix(".pdf")
    if (pdf.exists() and pdf.stat().st_size > 0
            and pdf.stat().st_mtime >= pptx.stat().st_mtime):
        return pdf

    soffice = _find_soffice()
    if not soffice:
        print("  [PDF] ❌ LibreOffice(soffice) 가 설치되어 있지 않습니다.")
        return None

    _ensure_fonts_registered()  # 한화고딕이 PDF 에 임베드되도록 폰트 등록(최초 1회)

    with tempfile.TemporaryDirectory(prefix="lo_profile_") as profile:
        try:
            subprocess.run(
                [
                    soffice,
                    f"-env:UserInstallation=file://{profile}",
                    "--headless", "--norestore", "--nolockcheck",
                    "--convert-to", "pdf",
                    "--outdir", str(pptx.parent),
                    str(pptx),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            print("  [PDF] ❌ 변환 시간 초과")
            return None
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode(errors="ignore")[:300] if e.stderr else ""
            print(f"  [PDF] ❌ 변환 실패: {err}")
            return None

    if pdf.exists() and pdf.stat().st_size > 0:
        return pdf
    return None
