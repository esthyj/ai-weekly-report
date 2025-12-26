import feedparser
import requests
import urllib3
from newspaper import Article, Config
from googlenewsdecoder import gnewsdecoder
import pandas as pd

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 전역적으로 SSL 검증 비활성화
old_request = requests.Session.request
def new_request(self, *args, **kwargs):
    kwargs['verify'] = False
    return old_request(self, *args, **kwargs)
requests.Session.request = new_request

def crawl_insurance_ai_news(max_articles=3, days=14):
    query = "신한라이프 AI when:{}d".format(days).replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # SSL 우회해서 RSS 가져오기
    response = requests.get(rss_url, headers=headers, verify=False)
    feed = feedparser.parse(response.text)
    
    print(f"뉴스 개수: {len(feed.entries)}")  # 디버깅
    
    config = Config()
    config.browser_user_agent = headers['User-Agent']
    config.request_timeout = 10

    results = []
    
    for entry in feed.entries:
        if len(results) >= max_articles:
            break
        
        print(f"처리 중: {entry.title}")  # 디버깅
        
        try:
            decoded_res = gnewsdecoder(entry.link)
            real_url = decoded_res.get('decoded_url', entry.link) if isinstance(decoded_res, dict) else decoded_res
        except Exception as e:
            print(f"URL 디코딩 실패: {e}")
            real_url = entry.link
        
        try:
            article = Article(real_url, language='ko', config=config)
            article.download()
            article.parse()
            
            if len(article.text.strip()) < 150:
                print(f"본문 너무 짧음: {len(article.text.strip())}자")
                continue
            
            results.append({
                "title": entry.title,
                "link": real_url,
                "content": article.text.strip()
            })
            print("→ 추가 완료")
        except Exception as e:
            print(f"기사 파싱 실패: {e}")
            continue
    
    return pd.DataFrame(results)


if __name__ == "__main__":
    df = crawl_insurance_ai_news(max_articles=3)
    print(df)