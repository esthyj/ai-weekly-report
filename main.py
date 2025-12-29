from news_crawler import get_selected_news
from news_summarize import summarize_articles
from ppt_maker import create_report
from ailab_summarize import ailab_summarized

def main():
    ### STEP 1: News Crawling
    print("\n" + "="*60)
    print("📰 STEP 1: News Crawling")
    print("="*60)
    selected_news_df = get_selected_news(num_select=4)
    
    if selected_news_df.empty:
        print("❌ No news selected. END.")
        return
    
    # 2단계: 뉴스 요약 (뉴스 크롤링 결과를 전달받아 요약)
    print("\n" + "="*60)
    print("🤖 2단계: AI 뉴스 요약")
    print("="*60)
    summarized_text = summarize_articles(selected_news_df)
    
    # 3단계: AI Lab 요약 (별도 소스)
    print("\n" + "="*60)
    print("🔬 3단계: AI Lab 뉴스 요약")
    print("="*60)
    summarized_text2 = ailab_summarized()
    
    # 4단계: 사용자 입력
    print("\n" + "="*60)
    print("📝 4단계: 보고서 정보 입력")
    print("="*60)
    number = input("리포트 발행 호수를 입력하세요 (예: 25): ")
    date = input("리포트 발행 날짜를 입력하세요 (예: 2025년 12월 26일): ")
    
    # 5단계: PPT 생성
    print("\n" + "="*60)
    print("📊 5단계: PPT 보고서 생성")
    print("="*60)
    create_report(
        pptx_in="AIWeeklyReport_format.pptx",
        pptx_out="output.pptx",
        number=number,
        date=date,
        text1=summarized_text,
        text2=summarized_text2
    )

    print("\n" + "="*60)
    print("✅ 완료! output.pptx가 생성되었습니다.")
    print("="*60)


if __name__ == "__main__":
    main()
