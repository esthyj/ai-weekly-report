# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI-powered weekly news report generator** for a Korean insurance company. It automates the process of crawling financial news about major companies (banks, insurers, tech firms, securities), summarizing them with OpenAI GPT, and generating a PowerPoint presentation with a corporate template.

**Key Workflow**: News Crawling → Human Selection → AI Summarization → Human Selection → PPT Generation

**Human-in-the-Loop Design**: Users manually select which crawled articles to summarize (Step 1) and which summaries to include in the final report (Step 2). This is intentional for quality control.

## Running the Application

### Basic Usage
```bash
python main.py
```

The script runs interactively with Korean prompts:
1. Enter report number (발행 호수)
2. Enter report date (발행 날짜)
3. Enter number of news articles to select
4. Select articles by index numbers
5. Select summaries to include in final report

### Prerequisites
- `.env` file with `OPENAI_API_KEY=your_key_here`
- `data/ailab_content.txt` must exist with AI Lab content
- `templates/AIWeeklyReport_format.pptx` must exist (corporate template)

### Output
Generated PPTX files are saved to `output/AIWeeklyReport_{timestamp}.pptx`

## Architecture

### Pipeline Stages (4 steps in main.py)

**Stage 0: User Input**
- Report metadata (number, date, news count)

**Stage 1: News Crawling** (`src/news_crawler.py`)
- Searches Google News RSS for each company in `SEARCH_CATEGORIES`
- Fetches article content via `newspaper3k`
- Scores articles based on `PRIORITY_KEYWORDS` (title = 2x weight, content = 1x weight)
- Selects top-scored article per company
- User manually selects final N articles → saved to `output/selected_news.xlsx`

**Stage 2: News Summarization** (`src/news_summarize.py`)
- Calls OpenAI API for each selected article
- Generates structured Korean summaries: `[Title]`, `[Summary1-N]`, `[Insight]`
- User manually selects which summaries to include in report

**Stage 3: AI Lab Summarization** (`src/ailab_summarize.py`)
- Reads `data/ailab_content.txt` (internal AI Lab updates)
- Calls OpenAI API to generate 2 summaries
- Separate from news crawling (different content source)

**Stage 4: PPT Generation** (`src/ppt_maker.py`)
- Loads template from `templates/AIWeeklyReport_format.pptx`
- Writes to specific shape indices (hardcoded: 4, 13, 14)
- Parses `[Tag]` sections and applies Korean font styles
- Saves final PPTX with timestamp

### Key Design Patterns

**Singleton OpenAI Client** (`src/openai_client.py`)
- `get_shared_client()` returns global `_client_instance`
- Initialized once with SSL verification disabled (intentional for internal network)
- Client shared across `news_summarize.py` and `ailab_summarize.py`

**Configuration Module** (`src/config.py`)
- Validates required directories on import (exits if missing)
- All file paths use `pathlib.Path`
- Creates `output/` directory automatically

**Error Handling Strategy**
- API errors: Print Korean error message, return `None`, allow pipeline to continue
- File errors: Validate existence before operations
- User input: Retry loops with validation (no upper bounds on news count)

## Code Conventions

### Language
- **User-facing messages**: Korean (업무 특성상 한글 사용)
- **Code/comments**: English preferred for consistency
- **Variable names**: English

### Error Handling Pattern
```python
try:
    # OpenAI API call
    response = client.chat.completions.create(...)
    if not response.choices:
        print("❌ Korean error message")
        return None
    return response.choices[0].message.content.strip()
except RateLimitError as e:
    print(f"❌ 요청 한도 초과: {e}")
    return None
except APIConnectionError as e:
    print(f"❌ 연결 실패: {e}")
    return None
# ... other specific exceptions
except Exception as e:
    print(f"❌ 예상치 못한 오류: {e}")
    return None
```

### Return Types
- Error cases return `None` (not empty strings)
- Functions that can fail use `Optional[str]` type hints
- Main pipeline checks `if not result:` before proceeding

### Korean Text Processing
- Summaries use noun-ending forms: `~임`, `~함`, `~있음` (not `~입니다`, `~합니다`)
- Character limits: Summaries 100-200 chars, each piece
- Tags for structure: `[Title]`, `[Summary1]`, `[Summary2]`, `[Insight]`

## Critical Files and Their Purpose

**`src/news_crawler.py`**
- `SEARCH_CATEGORIES`: List of companies by category (보험사, 은행, Tech, 증권사)
- `TOTAL_COMPANIES`: Auto-calculated from SEARCH_CATEGORIES (DO NOT hardcode to 3 for production)
- `PRIORITY_KEYWORDS`: Keywords that increase article scoring
- `EXCLUDE_KEYWORDS`: Filter out irrelevant articles
- `CrawlerConfig`: Dataclass with `days=14`, `candidates_per_query=5`, `min_content_length=150`

**`src/ppt_maker.py`**
- `TAG_STYLES`: Font styles for each tag type (title, summary, insight)
- Shape indices are hardcoded (4=metadata, 13=news, 14=ailab) - matches template structure
- `parse_sections()`: Regex extracts `[Tag]` sections from text
- Korean fonts: "한화고딕 B", "한화고딕 EL", "한화고딕 L"

**`main.py`**
- Sequential pipeline with error checks between stages
- Exits gracefully if any stage returns None/empty
- No retry logic for failed stages (user must restart)

## Known Issues and Limitations

### Security Concerns
- SSL verification disabled globally in `news_crawler.py` (monkey-patches `requests`)
- SSL disabled for OpenAI client in `openai_client.py`
- Necessary for internal corporate network, but avoid in public deployments

### Input Validation Gaps
- No upper bound on news count (user could enter 10000)
- No validation on report number/date metadata
- Could cause resource exhaustion

### Template Dependency
- PPT shape indices are magic numbers (4, 13, 14)
- If template changes structure, code breaks
- `list_all_shapes()` utility exists for debugging shape indices

### Model Configuration
- Uses `MODEL_NAME = "gpt-5.1"` (verify this is correct model name)
- Model name not configurable without code change

## Testing

**No test suite exists.** Test code is mixed in production files:
- `news_crawler.py` lines 252-260 (commented out)
- `news_summarize.py` lines 169-177 (in `if __name__ == "__main__"`)
- `ppt_maker.py` lines 166-180 (in `if __name__ == "__main__"`)

To manually test modules:
```bash
python -m src.news_crawler
python -m src.news_summarize
python -m src.ppt_maker
```

## Common Modification Patterns

### Adding a New Company to Crawl
Edit `SEARCH_CATEGORIES` in `src/news_crawler.py`:
```python
SEARCH_CATEGORIES = [
    {
        "category": "보험사",
        "queries": ["삼성화재", "현대해상", "NEW_COMPANY"]
    },
    # ...
]
```

### Adjusting Crawling Parameters
Edit `CrawlerConfig` defaults in `src/news_crawler.py`:
- `days`: How far back to search (default: 14 days)
- `candidates_per_query`: Max articles per company (default: 5)
- `min_content_length`: Minimum article length (default: 150 chars)

### Changing Summary Prompt
Edit `USER_PROMPT_TEMPLATE` in `src/news_summarize.py` or `src/ailab_summarize.py`

### Modifying PPT Styles
Edit `TAG_STYLES` in `src/ppt_maker.py`:
```python
TAG_STYLES = {
    "title":   (prefix, font_name, font_size, underline, split_lines),
    # ...
}
```

### Finding PPT Shape Indices
```python
from src.ppt_maker import list_all_shapes
from src.config import PPT_TEMPLATE_FILE
list_all_shapes(str(PPT_TEMPLATE_FILE))
```

## Dependencies

Key libraries and their purposes:
- `feedparser`: Parse Google News RSS feeds
- `googlenewsdecoder`: Decode Google News redirect URLs
- `newspaper3k`: Extract article content from web pages
- `openai`: GPT API for summarization
- `python-pptx`: Generate PowerPoint files
- `pandas`: Intermediate data storage (Excel)

## Environment Setup

Required directories (validated on startup):
- `data/` - Must contain `ailab_content.txt`
- `templates/` - Must contain `AIWeeklyReport_format.pptx`
- `output/` - Created automatically

Required environment variables:
- `OPENAI_API_KEY` in `.env` file

## Debugging Tips

### If No Articles Found
- Check `SEARCH_CATEGORIES` company names match news coverage
- Adjust `days` parameter (default 14 days may be too recent)
- Check `EXCLUDE_KEYWORDS` isn't filtering too aggressively

### If API Calls Fail
- Verify `OPENAI_API_KEY` in `.env`
- Check `MODEL_NAME` is valid OpenAI model
- Rate limit handling is automatic (prints error, returns None)

### If PPT Generation Fails
- Verify `templates/AIWeeklyReport_format.pptx` exists
- Check shape indices with `list_all_shapes()` utility
- Ensure template has shapes at indices 4, 13, 14

### If Summary Format is Wrong
- Check `[Tag]` sections are present in API response
- Validate regex pattern `TAG_RE` in `ppt_maker.py`
- Review `parse_sections()` logic
