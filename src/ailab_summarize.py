from openai import OpenAI
import httpx
from dotenv import load_dotenv
import os

# API Key Settings
http_client = httpx.Client(verify=False)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), http_client=http_client)

# Return AI Lab news summarization results
def ailab_summarized():
    
    # Ailab Contents are saved in txt file
    with open("data/ailab_content.txt", "r", encoding="utf-8") as f:
        content = f.read()

    # OpenAI API call
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
    3. Be concise and factual. Do NOT add information not mentioned or logically implied in the article.
    4. Use professional Korean business tone.
    5. For [Title], Use noun-only endings
    6. For [Summary1], [Summary2], end sentences with noun-ending forms like "~임", "~함", "~있음" instead of formal endings like "~입니다", "~합니다", "~있습니다"
    8. Please write [Summary1] and [Summary2] each within 150 characters

    <output_format>
    [Title]
    Generate a title that summarizes the content of the news.

    [Summary1]
    Write one keypoint about the news article.

    [Summary2]
    Write another keypoint about the news article.

    <article>
    {content}
    """
            }
        ],
        temperature=0.3
    )
    
    result = response.choices[0].message.content.strip()
    return result


# Test (If needed)
if __name__ == "__main__":
    result = ailab_summarized()
    print(result)