import feedparser
from newspaper import Article, Config
from datetime import datetime, timedelta
import pandas as pd
from googlenewsdecoder import gnewsdecoder
import nltk

# download nltk data
# nltk.download('punkt')

def get_google_news_rss(query, lang="ko", country="KR"):
    # news in 2 weeks
    query = f"{query} when:14d".replace(" ", "+")
    return f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={country}&ceid={country}:{lang}"

def crawl_insurance_ai_news(max_articles=3):
    rss_url = get_google_news_rss("보험 AI")
    feed = feedparser.parse(rss_url)
    
    config = Config()
    config.browser_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    config.request_timeout = 15

    results = []
    
    for entry in feed.entries:
        if len(results) >= max_articles:
            break
            
        try:
            decoded_res = gnewsdecoder(entry.link)
            if isinstance(decoded_res, dict):
                real_url = decoded_res.get('decoded_url', entry.link)
            else:
                real_url = decoded_res
        except Exception as e:
            print(f"Impossible to read URL: {e}")
            real_url = entry.link

        # Read the content of the news
        try:
            article = Article(real_url, language='ko', config=config)
            article.download()
            article.parse()
            
            content = article.text.strip()
            
            if len(content) < 150:
                continue
                
            results.append({
                "title": entry.title,
                "published": entry.published,
                "link": real_url,
                "content": content
            })
            print(f"News crawl success!: {entry.title[:30]}...")
            
        except Exception as e:
            print(f"News crawl failed: {entry.title[:15]}... (error: {e})")
            continue

    return pd.DataFrame(results)

if __name__ == "__main__":
    print("News Crawling Start!...")
    df = crawl_insurance_ai_news(max_articles=3)
    
    if not df.empty:
        print("\n" + "="*50)
        print(df[["title", "published", "content"]])
    else:
        print("[END] News crawl failed")