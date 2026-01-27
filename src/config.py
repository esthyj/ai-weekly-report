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

# Specific file paths
AILAB_CONTENT_FILE = DATA_DIR / "ailab_content.txt"
SELECTED_NEWS_FILE = OUTPUT_DIR / "selected_news.xlsx"
PPT_TEMPLATE_FILE = TEMPLATES_DIR / "AIWeeklyReport_format.pptx"

# Ensure required directories exist
OUTPUT_DIR.mkdir(exist_ok=True)

# Validate critical directories exist
if not DATA_DIR.exists():
    print(f"❌ 오류: 필수 디렉토리가 없습니다: {DATA_DIR}")
    print(f"   '{DATA_DIR}' 디렉토리를 생성해주세요.")
    sys.exit(1)

if not TEMPLATES_DIR.exists():
    print(f"❌ 오류: 필수 디렉토리가 없습니다: {TEMPLATES_DIR}")
    print(f"   '{TEMPLATES_DIR}' 디렉토리를 생성해주세요.")
    sys.exit(1)
