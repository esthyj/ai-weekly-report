import os
from openai import OpenAI
from news_crawler import get_selected_news
from dotenv import load_dotenv
import httpx

http_client=httpx.Client(verify=False)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), http_client=http_client)

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
    1. Please generate exactly one sentence each after [Summary1] and [Summary2].
    2. Write ONE insight sentence for an insurance company use case.
    3. Be concise and factual. Do NOT add information not mentioned or logically implied in the article.
    4. Use professional Korean business tone.
    5. For [Title], Use noun-only endings
    6. For [Summary1], [Summary2], [Insight], end sentences with noun-ending forms like "~임", "~함", "~있음" instead of formal endings like "~입니다", "~합니다", "~있습니다"
    7. In insight, When referring to "our company" in Korean, use "당사".
    8. Please write [Summary1], [Summary2], and [Insight] each within 100 characters

    <output_format>
    [Title]
    Generate a title that summarizes the content of the news.

    [Summary1]
    Describe the new service or product and its key technical features.

    [Summary2]
    Describe the AI technologies or AI methodologies applied in the service.

    [Insight]
    Suggest a concrete way this service or technology could be applied in our insurance company
    (e.g., underwriting, claims, customer service, sales, risk management).

    <article>
    {content}
    """
            }
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

def get_summarized_news():
    df = get_selected_news(num_select=4)
    print("Crawl Success!")
    results = ''

    for _, row in df.iterrows():
        summary = summarize_article(row["content"])
        results+=summary+"\n"
    print("Summary END:", results)
    print("Summarize End")

    return results

if __name__ == "__main__":
    results = get_summarized_news()
