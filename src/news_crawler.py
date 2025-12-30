import ssl
import urllib3
from dataclasses import dataclass
from typing import Optional

import feedparser
import pandas as pd
import requests
from googlenewsdecoder import gnewsdecoder
from newspaper import Article, Config

# ============================================================
# 설정
# ============================================================
@dataclass
class CrawlerConfig:
    max_total: int = 30
    days: int = 14
    candidates_per_query: int = 5
    min_content_length: int = 150
    request_timeout: int = 15
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EXCLUDE_KEYWORDS = ["배타적", "영상", "종목", "주가", "급등", "급락", "매수", "매도"]

PRIORITY_KEYWORDS = {
    "출시": 10, "런칭": 10, "오픈": 8, "서비스": 12,
    "발표": 6, "도입": 6, "개발": 5, "자동": 10,
    "챗봇": 10, "GPT": 10, "생성형": 10, "LLM": 10,
    "플랫폼": 3, "솔루션": 3, "시스템": 2,
}

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
        "category": "Tech",
        "queries": ["구글", "OpenAI", "마이크로소프트"]
    },
    {
        "category": "증권사",
        "queries": ["NH투자증권", "미래에셋증권", "한국투자증권", "삼성증권", "신한투자증권", "KB증권", "키움증권", "토스증권"]
    },
]


# ============================================================
# SSL 설정
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
# 유틸리티 함수
# ============================================================
def get_rss_url(query: str, days: int) -> str:
    encoded_query = f"{query} AI when:{days}d".replace(" ", "+")
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"


def calculate_score(title: str, content: str) -> int:
    text = f"{title} {content}"
    score = 0
    for keyword, weight in PRIORITY_KEYWORDS.items():
        if keyword in text:
            score += weight * 2 if keyword in title else weight
    return score


def decode_url(link: str) -> str:
    try:
        result = gnewsdecoder(link)
        return result.get('decoded_url', link) if isinstance(result, dict) else result
    except Exception:
        return link


def fetch_article(url: str, config: Config) -> Optional[str]:
    """기사 내용을 가져옴. 실패시 None 반환"""
    try:
        article = Article(url, language='ko', config=config)
        article.download()
        article.parse()
        content = article.text.strip()
        return content if len(content) >= CrawlerConfig.min_content_length else None
    except Exception:
        return None


# ============================================================
# 기사 선택 함수
# ============================================================
def select_articles(df: pd.DataFrame, num_select: int = 4) -> pd.DataFrame:
    """사용자가 기사를 선택할 수 있게 함"""
    if df.empty:
        print("선택할 기사가 없습니다.")
        return df
    
    print(f"\n{'='*60}")
    print(f"📰 총 {len(df)}개 기사 수집 완료 - {num_select}개를 선택하세요")
    print(f"{'='*60}\n")
    
    display_df = df[["category", "company", "score", "title"]].copy()
    display_df.index = range(1, len(df) + 1)
    print(display_df.to_string())
    
    print(f"\n선택할 기사 번호 {num_select}개를 입력하세요 (공백으로 구분, 예: 5 6 3 15):")
    user_input = input(">>> ").strip()
    
    selected_indices = [int(x) for x in user_input.split()]
    selected_df = df.iloc[[i - 1 for i in selected_indices]].reset_index(drop=True)
    
    print(f"\n✅ 선택 완료!")
    
    return selected_df


# ============================================================
# 메인 크롤러
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
            feed = feedparser.parse(get_rss_url(company, cfg.days))
            
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
                print(f"    📰 {entry.title[:35]}... (점수: {score})")
            
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


def get_selected_news(num_select: int = 4) -> pd.DataFrame:
    """크롤링 후 사용자가 선택한 기사 반환"""
    df = crawl_news()
    
    if df.empty:
        return df
    
    return select_articles(df, num_select=num_select)


# 테스트용 (직접 실행 시)
if __name__ == "__main__":
    final_df = get_selected_news(num_select=4)
    
    if not final_df.empty:
        print(f"\n{'='*60}")
        print("📋 최종 선택된 기사:")
        print(f"{'='*60}\n")
        print(final_df[["category", "company", "score", "title"]].to_string())
