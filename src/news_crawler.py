import ssl
import urllib3
import logging
from dataclasses import dataclass
from typing import Optional

import feedparser
import pandas as pd
import requests
from googlenewsdecoder import gnewsdecoder
from newspaper import Article, Config
from .config import SELECTED_NEWS_FILE

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
    {
        "category": "은행",
        "queries": ["토스뱅크", "우리은행", "국민은행", "신한은행", "하나은행", "기업은행"]
    },
    {
        "category": "카드사",
        "queries": ["삼성카드", "신한카드", "KB국민카드", "현대카드", "롯데카드", "우리카드", "하나카드", "BC카드", "NH농협카드"]
    },
    {
        "category": "Tech",
        "queries": ["구글", "OpenAI", "마이크로소프트"]
    },
    {
        "category": "증권사",
        "queries": ["NH투자증권", "미래에셋증권", "한국투자증권", "삼성증권", "신한투자증권", "KB증권", "키움증권", "토스증권"]
    },
    {
        "category": "기타",
        "queries": ["금융", "인공지능", "기후", "자율주행", "보험"]
    },
]

# Calculate total number of companies from SEARCH_CATEGORIES
TOTAL_COMPANIES = sum(len(cat["queries"]) for cat in SEARCH_CATEGORIES)
# TOTAL_COMPANIES = 3 # for testing, limit to 3 companies (Use only when to debug)

@dataclass
class CrawlerConfig:
    max_total: int = TOTAL_COMPANIES # numbers of companies to crawl (auto-calculated from SEARCH_CATEGORIES)
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

# make rss url by company name and days to look for
def get_rss_url(query: str, days: int) -> str:
    encoded_query = f"{query} AI when:{days}d".replace(" ", "+")
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
# Select Articles (Human in the loop)
# ============================================================
def select_articles(df: pd.DataFrame, num_select: int = 4) -> pd.DataFrame:
    if df.empty:
        print("선택할 기사가 없습니다.")
        return df
    
    print(f"\n{'='*60}")
    print(f"📰 총 {len(df)}개 기사 수집 완료 - {num_select}개를 선택하세요")
    print(f"{'='*60}\n")
    
    display_df = df[["category", "company", "score", "title"]].copy()
    display_df.index = range(1, len(df) + 1)
    print(display_df.to_string())

    print(f"\n[SELECT] 선택할 기사 번호 {num_select}개를 입력하세요 (공백으로 구분, 예: 5 6 3 15):")

    while True:
        try:
            user_input = input(">>> ").strip()

            if not user_input:
                print("❌ 입력이 비어있습니다. 다시 입력해주세요.")
                continue

            selected_indices = [int(x) for x in user_input.split()]

            # Validate that all indices are within valid range
            invalid_indices = [idx for idx in selected_indices if idx < 1 or idx > len(df)]
            if invalid_indices:
                print(f"❌ 잘못된 번호가 포함되어 있습니다: {invalid_indices}")
                print(f"   유효한 범위: 1 ~ {len(df)}")
                continue

            if not selected_indices:
                print("❌ 최소 1개 이상의 기사를 선택해야 합니다.")
                continue

            # Validate number of selections
            if len(selected_indices) != num_select:
                print(f"❌ {num_select}개를 선택해야 하지만 {len(selected_indices)}개가 선택되었습니다.")
                response = input(f"   계속 진행하시겠습니까? (y/n): ").strip().lower()
                if response != 'y':
                    continue

            break

        except ValueError:
            print("❌ 잘못된 입력입니다. 숫자만 입력해주세요. (예: 1 3 5)")
            continue

    selected_df = df.iloc[[i - 1 for i in selected_indices]].reset_index(drop=True)

    print(f"\n✅ 선택 완료!")

    try:
        selected_df.to_excel(
            SELECTED_NEWS_FILE,
            index=False,
            engine='openpyxl'
        )
        print(f"📁 Excel 저장 완료: {SELECTED_NEWS_FILE}")
    except Exception as e:
        print(f"❌ Excel 파일 저장 실패: {e}")
        print("   선택한 데이터는 메모리에 유지되지만 파일로 저장되지 않았습니다.")

    return selected_df


# ============================================================
# Main Crawler
# ============================================================
def crawl_news(cfg: CrawlerConfig = CrawlerConfig()) -> pd.DataFrame:
    setup_ssl()
    
    article_config = Config()
    article_config.browser_user_agent = cfg.user_agent
    article_config.request_timeout = cfg.request_timeout

    results, seen_urls = [], set()
    
    print(f"📅 최근 {cfg.days}일 이내 뉴스 수집")
    print(f"📌 기업당 1개, 총 {cfg.max_total}개 목표\n")
    
    for cat in SEARCH_CATEGORIES:
        if len(results) >= cfg.max_total:
            break
            
        print(f"\n{'='*50}\n📌 [{cat['category']}] 검색 중...")
        category_count = 0
        
        for company in cat["queries"]:
            if len(results) >= cfg.max_total:
                break
            
            print(f"\n  🔍 {company}")
            # Article List Extraction
            feed = feedparser.parse(get_rss_url(company, cfg.days))
            
            candidates = []
            for entry in feed.entries:
                if len(candidates) >= cfg.candidates_per_query:
                    break
                # Articles are excluded if the title contains any EXCLUDE KEYWORDS
                if any(kw in entry.title for kw in EXCLUDE_KEYWORDS):
                    continue
                
                # Decode URL (RSS URL -> Original URL)
                url = decode_url(entry.link)
                if url in seen_urls:
                    continue
                
                # Fetch Article Content
                content = fetch_article(url, article_config)
                if not content:
                    continue
                
                #Calculate Score of Article
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
                print(f"    📰 {entry.title[:35]}... (점수: {score})")
            
            # Select the highest scored article among candidates
            if candidates:
                best = max(candidates, key=lambda x: x["score"])
                seen_urls.add(best["link"])
                results.append(best)
                category_count += 1
                print(f"    ✅ 선택: {best['title'][:35]}...")
            else:
                print(f"    ⚠️ 뉴스 없음")
        
        print(f"\n  📊 {cat['category']}: {category_count}개")
    
    return pd.DataFrame(results)

# After crawling, return the articles selected by the user
def get_selected_news(num_select: int = 4) -> pd.DataFrame:
    df = crawl_news()
    
    if df.empty:
        return df
    
    return select_articles(df, num_select=num_select)


# Test (If needed)
if __name__ == "__main__":
    final_df = get_selected_news(num_select=4)
    
    if not final_df.empty:
        print(f"\n{'='*60}")
        print("📋 최종 선택된 기사:")
        print(f"{'='*60}\n")
        print(final_df[["category", "company", "score", "title"]].to_string())
