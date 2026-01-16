import os
import httpx
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv


# Key Settings
load_dotenv()
http_client = httpx.Client(verify=False)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), http_client=http_client)


# Summarize Article Content
def summarize_article(content: str) -> str:
    if not content or len(content.strip()) < 50:
        return "Not enough content to summarize."

    response = client.chat.completions.create(
        model="gpt-5.1",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional AI analyst specializing in Insurance and AI services. "
                    "You write concise, structured, and business-oriented summaries in Korean."
                )
            },
            {
                "role": "user",
                "content": f"""
    <task>
    Analyze the following news article and produce a structured Korean output.

    <requirements>
    1. Generate [Summary1], [Summary2], ... [SummaryN] based on the article's content depth.
      - Do NOT attempt to summarize the entire article.
      - Focus on high-impact facts, decisions, or implications.
      - Minimum 2, Maximum 3 summaries
    2. Write ONE insight sentence for an insurance company use case.
    3. Be concise and factual. Do NOT add information not mentioned or logically implied in the article.
    4. Use professional Korean business tone.
    5. For [Title], use noun-only endings.
    6. For [Summary], [Insight], end sentences with noun-ending forms like "~임", "~함", "~있음" instead of formal endings like "~입니다", "~합니다", "~있습니다"
    7. In insight, when referring to "our company" in Korean, use "당사".
    8. Please write each [Summary] and [Insight] between 100 and 200 characters.
    9. Avoid redundancy: [Title], [Summary], and [Insight] must each contain unique information without overlapping content or repeating the same expressions.

    <output_format>
    [Title]
    Generate a title that summarizes the content of the news.

    [Summary1]
    First key point (e.g., new service/product and its features)

    [Summary2]
    Second key point (e.g., AI technologies applied) - if applicable

    [Summary3]
    - if applicable

    ... (continue as needed)

    [Insight]
    Suggest a concrete way this service or technology could be applied in our insurance company, along with expected benefits if applicable.
    (e.g., underwriting, claims, customer service, sales, marketing, risk management).

    <article>
    {content}
    """
            }
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()


# Summarize the articles in the DataFrame and return a combined string
def summarize_articles(df: pd.DataFrame) -> str:
    if df.empty:
        print("⚠️ 요약할 기사가 없습니다.")
        return ""
    
    results = []
    total = len(df)
    
    for idx, row in df.iterrows():
        print(f"  📝 요약 중... ({idx + 1}/{total}) {row.get('title', 'N/A')[:40]}...")
        summary = summarize_article(row["content"])
        results.append(summary)
    
    combined = "\n".join(results)
    print(f"  ✅ {total}개 기사 요약 완료!")
    
    return combined


# Test (If needed)
if __name__ == "__main__":

    df = pd.read_excel("../output/selected_news.xlsx", engine='openpyxl')
    if not df.empty:
        result = summarize_articles(df)
        print("\n" + "="*60)
        print("📋 요약 결과:")
        print("="*60)
        print(result)
