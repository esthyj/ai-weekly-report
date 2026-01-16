from src.news_crawler import get_selected_news
from src.news_summarize import summarize_articles
from src.ppt_maker import create_report
from src.ailab_summarize import ailab_summarized
from datetime import datetime

def main():

    # 0단계: 보고서 정보 입력
    print("\n" + "="*60)
    print("📝 0단계: 보고서 정보 입력")
    print("="*60)
    number = input("리포트 발행 호수를 입력하세요 (예: 25): ")
    date = input("리포트 발행 날짜를 입력하세요 (예: 2025년 12월 26일): ")

    ### 1단계: 뉴스 크롤링
    print("\n" + "="*60)
    print("📰 STEP 1: News Crawling")
    print("="*60)
    num_input = input("선택할 뉴스 개수를 입력하세요 (기본값: 4): ").strip()
    num_news = int(num_input) if num_input else 4
    selected_news_df = get_selected_news(num_select=num_news)
    # 사람이 개입해서 num_news 개수만큼 뉴스를 선택
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
    
    # 4단계: PPT 생성
    print("\n" + "="*60)
    print("📊 단계: PPT 보고서 생성")
    print("="*60)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"output/AIWeeklyReport_{timestamp}.pptx"

    create_report(
        pptx_in="templates/AIWeeklyReport_format.pptx",
        pptx_out=output_filename,
        number=number,
        date=date,
        text1=summarized_text,
        text2=summarized_text2
    )

    print("\n" + "="*60)
    print("✅ 모든 프로세스 완료!")
    print("output/output.pptx 파일 생성까지 최대 5분정도 소요될 수 있습니다.")
    print("조금만 기다려주세요... 감사합니다!")
    print("="*60)


if __name__ == "__main__":
    main()
