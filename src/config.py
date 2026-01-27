"""
Configuration file for project paths and settings.
"""
from pathlib import Path

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

# Ensure output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)
