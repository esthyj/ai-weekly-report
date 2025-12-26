import feedparser
from newspaper import Article, Config
from googlenewsdecoder import gnewsdecoder
import pandas as pd

def crawl_insurance_ai_news(max_articles=3, days=14):
    query = "신한라이프 AI when:{}d".format(days).replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    config = Config()
    config.browser_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    config.request_timeout = 10

    feed = feedparser.parse(rss_url)
    results = []
    
    for entry in feed.entries:
        if len(results) >= max_articles:
            break
        
        try:
            decoded_res = gnewsdecoder(entry.link)
            real_url = decoded_res.get('decoded_url', entry.link) if isinstance(decoded_res, dict) else decoded_res
        except:
            real_url = entry.link
        
        try:
            article = Article(real_url, language='ko', config=config)
            article.download()
            article.parse()
            
            if len(article.text.strip()) < 150:
                continue
            
            results.append({
                "title": entry.title,
                "link": real_url,
                "content": article.text.strip()
            })
        except:
            continue
    
    return pd.DataFrame(results)


if __name__ == "__main__":
    df = crawl_insurance_ai_news(max_articles=3)
    print(df)