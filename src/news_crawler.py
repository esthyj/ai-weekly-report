import ssl
import urllib3
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import feedparser
import pandas as pd
import requests
from googlenewsdecoder import gnewsdecoder
from newspaper import Article, Config
from .config import SELECTED_NEWS_FILE

ProgressCb = Callable[[str], None]

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# Settings 
# ============================================================

# keywords that, if present in the title, will exclude the article
EXCLUDE_KEYWORDS = ["배타적", "영상", "종목", "주가", "급등", "급락", "매수", "매도"]

# keywords with associated priority scores
PRIORITY_KEYWORDS = {
    "출시": 10, "런칭": 10, "오픈": 8, "서비스": 12,
    "발표": 6, "도입": 6, "개발": 5, "자동": 10,
    "챗봇": 10, "GPT": 10, "생성형": 10, "LLM": 10,
    "플랫폼": 3, "솔루션": 3, "시스템": 2,
}

# To identify financial companies of a certain scale, the following companies were listed
# category: Industry of the company
# queries: List of company names to search for
SEARCH_CATEGORIES = [
    {
        "category": "보험사",
        "queries": [
            "삼성화재", "현대해상", "DB손해보험", "KB손해보험", "메리츠화재", "토스인슈어런스",
            "삼성생명", "교보생명", "한화생명", "신한라이프", "NH농협생명", "KB라이프", "NH농협생명"
        ]
    },
    # {
    #     "category": "은행",
    #     "queries": ["토스뱅크", "우리은행", "국민은행", "신한은행", "하나은행", "기업은행"]
    # },
    # {
    #     "category": "카드사",
    #     "queries": ["삼성카드", "신한카드", "KB국민카드", "현대카드", "롯데카드", "우리카드", "하나카드", "BC카드", "NH농협카드"]
    # },
    # {
    #     "category": "Tech",
    #     "queries": ["구글", "OpenAI", "마이크로소프트"]
    # },
    # {
    #     "category": "증권사",
    #     "queries": ["NH투자증권", "미래에셋증권", "한국투자증권", "삼성증권", "신한투자증권", "KB증권", "키움증권", "토스증권"]
    # },
    # {
    #     "category": "기타",
    #     "queries": ["금융", "인공지능", "기후", "자율주행", "보험"]
    # },
]

# Calculate total number of companies from SEARCH_CATEGORIES
TOTAL_COMPANIES = sum(len(cat["queries"]) for cat in SEARCH_CATEGORIES)
# TOTAL_COMPANIES = 3 # for testing, limit to 3 companies (Use only when to debug)

@dataclass
class CrawlerConfig:
    # 사용자 지정 기업 목록. 비어 있으면 SEARCH_CATEGORIES 사용 (웹 앱 호환).
    companies: list[str] = field(default_factory=list)
    # RSS 쿼리에 항상 포함되는 필수 키워드 (예: "AI"). 빈 문자열이면 추가 안함.
    required_keyword: str = "AI"
    max_total: int = TOTAL_COMPANIES # numbers of companies to crawl (auto-calculated when no user companies)
    days: int = 14 # days to look back
    candidates_per_query: int = 5 # candidates per company query
    min_content_length: int = 150 # minimum length of article content
    request_timeout: int = 15 # seconds
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ============================================================
# SSL Settings
# ============================================================
def setup_ssl():
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    original_request = requests.Session.request
    def patched_request(self, *args, **kwargs):
        kwargs['verify'] = False
        return original_request(self, *args, **kwargs)
    requests.Session.request = patched_request


# ============================================================
# Utility Functions
# ============================================================

# make rss url by company name, days to look for, and an optional required keyword
def get_rss_url(query: str, days: int, required_keyword: str = "AI") -> str:
    parts = [query]
    if required_keyword:
        parts.append(required_keyword)
    parts.append(f"when:{days}d")
    encoded_query = " ".join(parts).replace(" ", "+")
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

# calculate article score based on presence of priority keywords
def calculate_score(title: str, content: str) -> int:
    text = f"{title} {content}"
    score = 0
    for keyword, weight in PRIORITY_KEYWORDS.items():
        if keyword in text:
            score += weight * 2 if keyword in title else weight
    return score

# RSS URLs are decoded into the original article URLs
def decode_url(link: str) -> str:
    try:
        result = gnewsdecoder(link)
        return result.get('decoded_url', link) if isinstance(result, dict) else result
    except Exception as e:
        logger.warning(f"Failed to decode URL {link}: {e}")
        return link

# Fetch Article Content
def fetch_article(url: str, config: Config) -> Optional[str]:
    try:
        article = Article(url, language='ko', config=config)
        article.download()
        article.parse()
        content = article.text.strip()
        return content if len(content) >= CrawlerConfig.min_content_length else None
    except Exception as e:
        logger.debug(f"Failed to fetch article {url}: {e}")
        return None


# ============================================================
# Interactive Settings Prompt (CLI)
# ============================================================
def prompt_crawler_settings() -> CrawlerConfig:
    """CLI에서 검색 필수 키워드 / 기업 목록 / 검색 기간을 사용자 입력으로 받아 CrawlerConfig 생성."""
    print("\n" + "=" * 60)
    print("⚙️  크롤링 설정 입력")
    print("=" * 60)

    # 1) 검색 필수 키워드
    required_keyword = input("검색 필수 키워드 (Enter 시 기본값 'AI'): ").strip() or "AI"

    # 2) 검색 기업 키워드 — 태그 형식으로 추가/삭제
    companies: list[str] = []
    print("\n검색 기업 키워드 (태그 방식 — 무제한 추가/삭제 가능)")
    print("명령:")
    print("  • 기업명 입력         → 태그 추가  (예: 삼성화재)")
    print("  • -<번호> 또는 del <번호> → 해당 태그 삭제  (예: -2)")
    print("  • clear              → 전체 삭제")
    print("  • done 또는 Enter    → 입력 완료")

    def render_tags() -> None:
        if not companies:
            print("\n  [현재 태그] (없음)")
        else:
            tags = "  ".join(f"[{i+1}: {c}]" for i, c in enumerate(companies))
            print(f"\n  [현재 태그 — {len(companies)}개]\n  {tags}")

    while True:
        render_tags()
        raw = input("\n>>> ").strip()

        # 완료
        if raw == "" or raw.lower() == "done":
            if companies:
                break
            print("❌ 최소 1개 이상의 기업을 입력해야 합니다.")
            continue

        # 전체 삭제
        if raw.lower() == "clear":
            companies.clear()
            print("🧹 전체 태그 삭제됨")
            continue

        # 삭제: "-3" 또는 "del 3"
        target_idx: Optional[int] = None
        if raw.startswith("-") and raw[1:].strip().isdigit():
            target_idx = int(raw[1:].strip())
        elif raw.lower().startswith("del "):
            tail = raw[4:].strip()
            if tail.isdigit():
                target_idx = int(tail)
        if target_idx is not None:
            if 1 <= target_idx <= len(companies):
                removed = companies.pop(target_idx - 1)
                print(f"❎ 삭제됨: {removed}")
            else:
                print(f"❌ 잘못된 번호입니다. (유효 범위: 1 ~ {len(companies)})")
            continue

        # 추가
        if raw in companies:
            print(f"⚠️  이미 추가된 기업입니다: {raw}")
            continue
        companies.append(raw)
        print(f"➕ 추가됨: {raw}")

    # 3) 검색 기간 (days)
    while True:
        raw = input("\n검색 기간 (며칠 전까지, Enter 시 기본값 14): ").strip()
        if not raw:
            days = 14
            break
        try:
            days = int(raw)
            if days < 1:
                print("❌ 1 이상의 정수를 입력하세요.")
                continue
            break
        except ValueError:
            print("❌ 숫자만 입력해주세요.")

    print(f"\n✅ 설정 완료 — 키워드: '{required_keyword}', 기업 {len(companies)}개, 기간 {days}일")
    return CrawlerConfig(
        companies=companies,
        required_keyword=required_keyword,
        days=days,
    )


# ============================================================
# Select Articles
# ============================================================
def select_articles_by_indices(
    df: pd.DataFrame,
    indices: list[int],
    save_excel: bool = False,
) -> pd.DataFrame:
    """선택된 1-based 인덱스에 해당하는 기사들로 DataFrame 생성.

    `save_excel=True`일 때만 SELECTED_NEWS_FILE에 저장 (CLI 전용 사이드이펙트).
    웹 사용 시에는 False로 호출 — 세션 상태에만 보관.
    """
    if df.empty:
        return df

    selected_df = df.iloc[[i - 1 for i in indices]].reset_index(drop=True)

    if save_excel:
        try:
            selected_df.to_excel(SELECTED_NEWS_FILE, index=False, engine="openpyxl")
            print(f"📁 Excel 저장 완료: {SELECTED_NEWS_FILE}")
        except Exception as e:
            print(f"❌ Excel 파일 저장 실패: {e}")
            print("   선택한 데이터는 메모리에 유지되지만 파일로 저장되지 않았습니다.")

    return selected_df


def select_articles(df: pd.DataFrame) -> pd.DataFrame:
    """CLI wrapper — 사용자 입력으로 인덱스를 받아 select_articles_by_indices 호출."""
    if df.empty:
        print("선택할 기사가 없습니다.")
        return df

    print(f"\n{'='*60}")
    print(f"📰 총 {len(df)}개 기사 수집 완료")
    print(f"{'='*60}\n")

    display_df = df[["category", "company", "score", "title"]].copy()
    display_df.index = range(1, len(df) + 1)
    print(display_df.to_string())

    print(f"\n[SELECT] 보고서에 포함할 기사 번호를 공백으로 구분하여 입력하세요 (1 ~ {len(df)}, 예: 5 6 3 15):")

    while True:
        try:
            user_input = input(">>> ").strip()

            if not user_input:
                print("❌ 입력이 비어있습니다. 다시 입력해주세요.")
                continue

            selected_indices = [int(x) for x in user_input.split()]

            invalid_indices = [idx for idx in selected_indices if idx < 1 or idx > len(df)]
            if invalid_indices:
                print(f"❌ 잘못된 번호가 포함되어 있습니다: {invalid_indices}")
                print(f"   유효한 범위: 1 ~ {len(df)}")
                continue

            if not selected_indices:
                print("❌ 최소 1개 이상의 기사를 선택해야 합니다.")
                continue

            break

        except ValueError:
            print("❌ 잘못된 입력입니다. 숫자만 입력해주세요. (예: 1 3 5)")
            continue

    selected_df = select_articles_by_indices(df, selected_indices, save_excel=True)
    print(f"\n✅ {len(selected_indices)}개 기사가 선택되었습니다!")
    return selected_df


# ============================================================
# Main Crawler
# ============================================================
def crawl_news(
    cfg: CrawlerConfig = CrawlerConfig(),
    progress_cb: ProgressCb = print,
) -> pd.DataFrame:
    """뉴스 크롤링. `progress_cb`로 진행 로그를 라우팅 (기본 print → CLI 호환).
    웹에서는 SSE 스트림 콜백을 주입하여 실시간 로그 표시.
    """
    setup_ssl()

    article_config = Config()
    article_config.browser_user_agent = cfg.user_agent
    article_config.request_timeout = cfg.request_timeout

    results, seen_urls = [], set()

    # 사용자가 companies를 명시하면 단일 "사용자 지정" 카테고리로 처리.
    # 비어 있으면 기존 SEARCH_CATEGORIES 그대로 사용 (웹 앱 호환).
    if cfg.companies:
        categories = [{"category": "사용자 지정", "queries": cfg.companies}]
        max_total = len(cfg.companies)
    else:
        categories = SEARCH_CATEGORIES
        max_total = cfg.max_total

    progress_cb(f"📅 최근 {cfg.days}일 이내 뉴스 수집")
    if cfg.required_keyword:
        progress_cb(f"🔑 필수 키워드: {cfg.required_keyword}")
    progress_cb(f"📌 기업당 1개, 총 {max_total}개 목표")

    for cat in categories:
        if len(results) >= max_total:
            break

        progress_cb(f"📌 [{cat['category']}] 검색 중...")
        category_count = 0

        for company in cat["queries"]:
            if len(results) >= max_total:
                break

            progress_cb(f"  🔍 {company}")
            feed = feedparser.parse(get_rss_url(company, cfg.days, cfg.required_keyword))

            candidates = []
            for entry in feed.entries:
                if len(candidates) >= cfg.candidates_per_query:
                    break
                if any(kw in entry.title for kw in EXCLUDE_KEYWORDS):
                    continue

                url = decode_url(entry.link)
                if url in seen_urls:
                    continue

                content = fetch_article(url, article_config)
                if not content:
                    continue

                score = calculate_score(entry.title, content)
                candidates.append({
                    "category": cat["category"],
                    "company": company,
                    "title": entry.title,
                    "published": entry.published,
                    "link": url,
                    "content": content,
                    "score": score
                })
                progress_cb(f"    📰 {entry.title[:35]}... (점수: {score})")

            if candidates:
                best = max(candidates, key=lambda x: x["score"])
                seen_urls.add(best["link"])
                results.append(best)
                category_count += 1
                progress_cb(f"    ✅ 선택: {best['title'][:35]}...")
            else:
                progress_cb(f"    ⚠️ 뉴스 없음")

        progress_cb(f"  📊 {cat['category']}: {category_count}개")

    return pd.DataFrame(results)

# Test (If needed)
if __name__ == "__main__":
    df = crawl_news()
    if df.empty:
        print("크롤링 결과가 비어있습니다.")
    else:
        final_df = select_articles(df)
        if not final_df.empty:
            print(f"\n{'='*60}")
            print("📋 최종 선택된 기사:")
            print(f"{'='*60}\n")
            print(final_df[["category", "company", "score", "title"]].to_string())
