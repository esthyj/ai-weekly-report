from openai import OpenAI
import httpx
from dotenv import load_dotenv
import os

# API 키 설정
http_client = httpx.Client(verify=False)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), http_client=http_client)


def ailab_summarized():
    """AI Lab 뉴스 요약 결과를 반환하는 함수"""
    
    # txt 파일 읽기
    with open("data/ailab_content.txt", "r", encoding="utf-8") as f:
        content = f.read()

    # OpenAI API 호출
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


# 직접 실행할 때만 출력
if __name__ == "__main__":
    result = ailab_summarized()
    print(result)