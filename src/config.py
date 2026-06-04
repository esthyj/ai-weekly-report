"""
Configuration file for project paths and settings.
"""
from pathlib import Path
import sys

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
# 기사별 AI 생성 이미지 저장 위치
IMAGES_DIR = OUTPUT_DIR / "images"
# 한화고딕 폰트 파일 위치 (PPT 도형 높이 추정 시 실제 글자 metric 측정용)
FONTS_DIR = PROJECT_ROOT / "fonts"

# Specific file paths
SELECTED_NEWS_FILE = OUTPUT_DIR / "selected_news.xlsx"
PPT_TEMPLATE_FILE = TEMPLATES_DIR / "AIWeeklyReport_format.pptx"
# 본문 폭/줄높이 측정용 대표 폰트 — 한화고딕은 모든 굵기의 advance 폭과
# ascent/descent 가 동일하므로 한 개 파일만으로 측정이 정확하다.
FONT_METRIC_FILE = FONTS_DIR / "05HanwhaGothicR.ttf"

def ensure_directories() -> None:
    """필수 디렉토리 검증 + 출력 디렉토리 생성. 누락 시 sys.exit."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)

    if not DATA_DIR.exists():
        print(f"❌ 오류: 필수 디렉토리가 없습니다: {DATA_DIR}")
        print(f"   '{DATA_DIR}' 디렉토리를 생성해주세요.")
        sys.exit(1)

    if not TEMPLATES_DIR.exists():
        print(f"❌ 오류: 필수 디렉토리가 없습니다: {TEMPLATES_DIR}")
        print(f"   '{TEMPLATES_DIR}' 디렉토리를 생성해주세요.")
        sys.exit(1)
