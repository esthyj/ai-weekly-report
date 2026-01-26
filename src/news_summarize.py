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
def summarize_article(title: str, content: str) -> str:
    if not content or len(content.strip()) < 50:
        return "Not enough content to summarize."

    if " - " in title:
        title = title.split(" - ")[0].strip()
        
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
      - Default to 2 summaries, extend to 3 only if essential. 
    2. Write ONE insight sentence for an insurance company use case.
    3. Be concise and factual. Do NOT add information not mentioned or logically implied in the article.
    4. Use professional Korean business tone.
    5. For [Title], use the original title provided below EXACTLY as-is. Do NOT modify, translate, or rephrase it.
    6. For [Summary], [Insight], end sentences with noun-ending forms like "~임", "~함", "~있음" instead of formal endings like "~입니다", "~합니다", "~있습니다"
    7. In insight, when referring to "our company" in Korean, use "당사".
    8. Please write each [Summary] and [Insight] between 100 and 200 characters.
    9. Avoid redundancy: [Title], [Summary], and [Insight] must each contain unique information without overlapping content or repeating the same expressions.

    <original_title>
    {title}

    <output_format>
    [Title]
    (Copy the original title exactly as provided above. Do not change anything.)

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
    
    all_summaries = []
    total = len(df)
    
    # 1단계: 모든 기사 요약
    for idx, row in df.iterrows():
        print(f"  📝 요약 중... ({idx + 1}/{total}) {row.get('title', 'N/A')[:40]}...")
        summary = summarize_article(row["title"], row["content"])
        all_summaries.append({
            "index": idx + 1,
            "title": row.get("title", "N/A"),
            "summary": summary
        })
    
    # 2단계: 전체 결과 출력
    print("\n" + "="*60)
    print("📋 전체 요약 결과")
    print("="*60)
    
    for item in all_summaries:
        print(f"\n[{item['index']}] {item['title'][:50]}...")
        print("-"*40)
        print(item['summary'])
        print()
    
    # 3단계: 사용자 선택 (띄어쓰기 기반)
    print("="*60)
    print("1개 이상의 포함할 요약 번호를 띄어쓰기로 구분하여 입력하세요. (예: 1 3 5)")
    print("="*60)
    
    selection = input("선택: ").strip()
    selected_indices = {int(x) for x in selection.split()}
    
    # 4단계: 선택된 것만 결합
    results = [
        item['summary'] 
        for item in all_summaries 
        if item['index'] in selected_indices
    ]
    
    combined = "\n\n".join(results)
    print(f"\n✅ {len(results)}개 요약이 선택되었습니다!")
    
    return combined


# Test (If needed)
if __name__ == "__main__":

    df = pd.read_excel("../output/selected_news.xlsx", engine='openpyxl')
    if not df.empty:
        result = summarize_articles(df)
        print("\n" + "="*60)
        print("📋 최종 선택된 요약:")
        print("="*60)
        print(result)