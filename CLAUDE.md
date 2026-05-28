# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI-powered weekly news report generator** for a Korean insurance company. It automates the process of crawling financial news about major companies (banks, insurers, tech firms, securities), summarizing them with the Anthropic Claude API, and generating a PowerPoint presentation with a corporate template.

**Key Workflow** (sequential pipeline in `main.py`): Metadata → News Crawling → Human Selection → AI Summarization → Human Selection (which summaries) → Review (accept / re-summarize / re-select) → AI Lab Summary → PPT Generation

**Human-in-the-Loop Design**: Users select which crawled articles to summarize, which summaries to include, and finally review the combined result with the option to loop back (re-summarize the same articles, or go back to article re-selection — without re-crawling).

## Running the Application

### Basic Usage
```bash
python main.py
```

The script runs interactively with Korean prompts:
1. Enter report number (발행 호수) and date (발행 날짜)
2. After crawling, select articles by index numbers (choose as many as you want)
3. Pick which generated summaries to include in the combined output
4. Review combined summary — accept (`a`/Enter), re-summarize (`r`), or re-select articles (`s`)
5. AI Lab summary is generated and the final PPT is written

### Prerequisites
- `.env` file with `ANTHROPIC_API_KEY=your_key_here`
- `templates/AIWeeklyReport_format.pptx` must exist (corporate template)
- AI Lab content is provided interactively by the user (CLI multi-line prompt or web textarea) — no file needed

### Output
Generated PPTX files are saved to `output/AIWeeklyReport_{timestamp}.pptx`

## Architecture

### Pipeline (sequential, `main.py`)

`main.py` runs the pipeline in plain Python. The review/redo branch is a single `while True` loop around the summarize step:

```
metadata → crawl → select → ┌→ summarize → review ─accept─→ ailab → ppt → done
                            │     ↑          │
                            │     └─ r ──────┤  (resummarize: loop with same selected_df)
                            └────────────────┘  (s reselect: re-pick from same crawled_df, no recrawl)
```

**State is just local variables** in `main()` — `crawled_df`, `selected_df`, `summary_text`, `ailab_text`. The re-select branch reuses the in-scope `crawled_df` so the (multi-minute) crawl is never repeated within a session.

**Pipeline steps** (all module functions called directly):

- **0. Metadata** — `input()` for report number and date.
- **1. Crawl** (`crawl_news` in `src/news_crawler.py`) — Google News RSS per company in `SEARCH_CATEGORIES`, `newspaper3k` for content, scores via `PRIORITY_KEYWORDS` (title = 2x weight). Top-scored article per company. Runs once per session.
- **1.5. Select** (`select_articles` in `src/news_crawler.py`) — shows DF, user picks any number of articles; writes `output/selected_news.xlsx` as audit trail.
- **2. Summarize** (`summarize_articles` in `src/news_summarize.py`) — Claude call per article via `call_llm()` in `src/llm_client.py`, generates `[Title]`/`[Summary1-N]`/`[Insight]`; inner step asks user which summaries to include in the combined output.
- **2.5. Review** (`prompt_review_decision()` in `main.py`) — shows combined summary, prompts `a` (accept) / `r` (re-summarize) / `s` (re-select).
- **3. AI Lab** (`ailab_summarized(content)` in `src/ailab_summarize.py`) — takes a `content` string supplied by the caller (CLI prompt via `prompt_ailab_content()` in `main.py`, or `ailab_content` field in the `/api/{sid}/ailab` body for the web). Claude call to generate 2 summaries. No review loop.
- **4. PPT** (`create_report` in `src/ppt_maker.py`) — fills `templates/AIWeeklyReport_format.pptx` shapes (META=4, NEWS=13, AILAB=14), saves to `output/AIWeeklyReport_{timestamp}.pptx`.

**Re-loop semantics**:
- `r` (resummarize) — `while` loops back to `summarize_articles(selected_df)` with the same articles. Claude `TEMPERATURE=0.3` so output varies between runs.
- `s` (reselect) — `selected_df = select_articles(crawled_df)` re-runs the picker against the cached crawl; crawling is NOT repeated.
- AI Lab summary intentionally has no review loop.

### Key Design Patterns

**Singleton Anthropic Client** (`src/llm_client.py`)
- `get_shared_client()` returns global `_client_instance`
- Initialized once with SSL verification disabled (intentional for internal network)
- `call_llm(system_prompt, user_prompt, model, max_tokens, log_prefix="")` wraps `messages.create` with the standard 5-block error handling. Both summarize modules go through this helper — add new LLM call policies here.

**Configuration Module** (`src/config.py`)
- `ensure_directories()` validates required directories and creates `output/` (call it once from `main.py`)
- All file paths use `pathlib.Path`
- Importing the module has no side effects — safe for module-level tests/tools

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
    # Claude API call
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
- Sequential pipeline orchestrator. `ensure_directories()` then the linear `metadata → crawl → select → (summarize → review)* → ailab → ppt` flow
- `prompt_review_decision()` helper handles the `a`/`r`/`s` input; the surrounding `while True` loop in `main()` implements re-summarize and re-select
- `crawled_df` lives in `main()` scope so reselect never triggers a fresh crawl
- Top-level try/except handles KeyboardInterrupt, FileNotFoundError, and unexpected errors with Korean messages + sys.exit codes

## Known Issues and Limitations

### Security Concerns
- SSL verification disabled globally in `news_crawler.py` (monkey-patches `requests`)
- SSL disabled for Anthropic client in `llm_client.py`
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
- Uses `MODEL_NAME = "claude-sonnet-4-6"` in both summarize modules
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
- `anthropic`: Claude API for summarization
- `python-pptx`: Generate PowerPoint files
- `pandas`: Intermediate data storage (Excel)

## Environment Setup

Required directories (validated on startup):
- `data/` - Must contain `ailab_content.txt`
- `templates/` - Must contain `AIWeeklyReport_format.pptx`
- `output/` - Created automatically

Required environment variables:
- `ANTHROPIC_API_KEY` in `.env` file

## Debugging Tips

### If No Articles Found
- Check `SEARCH_CATEGORIES` company names match news coverage
- Adjust `days` parameter (default 14 days may be too recent)
- Check `EXCLUDE_KEYWORDS` isn't filtering too aggressively

### If API Calls Fail
- Verify `ANTHROPIC_API_KEY` in `.env`
- Check `MODEL_NAME` is a valid Anthropic Claude model
- Rate limit handling is automatic (prints error, returns None)

### If PPT Generation Fails
- Verify `templates/AIWeeklyReport_format.pptx` exists
- Check shape indices with `list_all_shapes()` utility
- Ensure template has shapes at indices 4, 13, 14

### If Summary Format is Wrong
- Check `[Tag]` sections are present in API response
- Validate regex pattern `TAG_RE` in `ppt_maker.py`
- Review `parse_sections()` logic
