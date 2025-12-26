import feedparser
from newspaper import Article, Config
import pandas as pd
from googlenewsdecoder import gnewsdecoder

def get_google_news_rss(query, days=14, lang="ko", country="KR"):
    query = f"{query} when:{days}d".replace(" ", "+")
    return f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={country}&ceid={country}:{lang}"

def contains_exclude_keywords(text, exclude_keywords):
    """텍스트에 제외 키워드가 포함되어 있는지 확인"""
    return any(keyword in text for keyword in exclude_keywords)

def calculate_priority_score(title, content):
    """기사의 우선순위 점수 계산"""
    
    # 우선순위 키워드와 가중치
    priority_keywords = {
        # 새로운 서비스 출시 관련 (높은 점수)
        "출시": 10,
        "런칭": 10,
        "오픈": 8,
        "서비스": 12,
        "발표": 6,
        "도입": 6,
        "개발": 5,
        "자동": 5,
        # AI 서비스 관련 (중간 점수)
        "챗봇": 10,
        "GPT": 10,
        "생성형": 10,
        "LLM": 10,
        "플랫폼": 3,
        "솔루션": 3,
        "시스템": 2,
    }
    
    score = 0
    text = title + " " + content
    
    for keyword, weight in priority_keywords.items():
        if keyword in text:
            # 제목에 있으면 가중치 2배
            if keyword in title:
                score += weight * 2
            else:
                score += weight
    
    return score

def crawl_finance_ai_news(max_total=20, days=14, candidates_per_query=5):
    
    exclude_keywords = ["배타적", "영상", "종목", "주가", "급등", "급락", "매수", "매도"]
    
    search_categories = [
        {
            "category": "보험사",
            "priority": 1,
            "queries": [
                "삼성화재 AI",
                "삼성생명 AI",
                "현대해상 AI",
                "DB손해보험 AI",
                "KB손해보험 AI",
                "한화생명 AI",
                "신한라이프 AI",
            ]
        },
        {
            "category": "은행",
            "priority": 2,
            "queries": [
                "우리은행 AI",
                "국민은행 AI",
                "신한은행 AI",
                "하나은행 AI",
            ]
        },
        {
            "category": "테크",
            "priority": 3,
            "queries": [
                "구글 AI",
                "OpenAI AI",
                "마이크로소프트 AI",
            ]
        },
        {
            "category": "증권사",
            "priority": 4,
            "queries": [
                "미래에셋증권 AI",
                "한국투자증권 AI",
                "삼성증권 AI",
            ]
        },
    ]
    
    config = Config()
    config.browser_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    config.request_timeout = 15

    all_results = []
    seen_urls = set()
    
    print(f"📅 최근 {days}일 이내 뉴스만 수집합니다.")
    print(f"📌 기업당 1개 뉴스만 수집합니다.")
    print(f"⭐ 새로운 AI 서비스 출시 기사 우선 선택\n")
    
    for cat in search_categories:
        if len(all_results) >= max_total:
            break
            
        print(f"\n{'='*50}")
        print(f"📌 [{cat['category']}] 검색 중... (우선순위 {cat['priority']})")
        
        category_count = 0
        
        for query in cat["queries"]:
            if len(all_results) >= max_total:
                break
            
            print(f"\n  🔍 검색: {query}")
            rss_url = get_google_news_rss(query, days=days)
            feed = feedparser.parse(rss_url)
            
            # 후보 기사들을 모아서 점수 비교
            candidates = []
            
            for entry in feed.entries:
                if len(candidates) >= candidates_per_query:
                    break
                
                # 제목에서 제외 키워드 체크
                if contains_exclude_keywords(entry.title, exclude_keywords):
                    continue
                
                # URL 디코딩
                try:
                    decoded_res = gnewsdecoder(entry.link)
                    real_url = decoded_res.get('decoded_url', entry.link) if isinstance(decoded_res, dict) else decoded_res
                except:
                    real_url = entry.link
                
                if real_url in seen_urls:
                    continue
                
                # 기사 크롤링
                try:
                    article = Article(real_url, language='ko', config=config)
                    article.download()
                    article.parse()
                    
                    content = article.text.strip()
                    if len(content) < 150:
                        continue
                    
                    # 우선순위 점수 계산
                    score = calculate_priority_score(entry.title, content)
                    
                    candidates.append({
                        "category": cat["category"],
                        "company": query.replace(" AI", ""),
                        "title": entry.title,
                        "published": entry.published,
                        "link": real_url,
                        "content": content,
                        "score": score
                    })
                    print(f"    📰 후보: {entry.title[:35]}... (점수: {score})")
                    
                except:
                    continue
            
            # 점수가 가장 높은 기사 선택
            if candidates:
                best_article = max(candidates, key=lambda x: x["score"])
                seen_urls.add(best_article["link"])
                all_results.append(best_article)
                category_count += 1
                print(f"    ✅ 선택: {best_article['title'][:35]}... (점수: {best_article['score']})")
            else:
                print(f"    ⚠️ 뉴스를 찾지 못함")
        
        print(f"\n  📊 {cat['category']} 수집: {category_count}개")
    
    return pd.DataFrame(all_results)


if __name__ == "__main__":
    df = crawl_finance_ai_news(max_total=20, days=14, candidates_per_query=5)
    
    if not df.empty:
        print(f"\n{'='*50}")
        print(f"총 {len(df)}개 수집 완료\n")
        
        # 점수순 정렬해서 출력
        df_sorted = df.sort_values("score", ascending=False)
        print(df_sorted[["category", "company", "score", "title"]])