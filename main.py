import sys
from datetime import datetime

from src.ailab_summarize import ailab_summarized
from src.config import OUTPUT_DIR, PPT_TEMPLATE_FILE, ensure_directories
from src.news_crawler import crawl_news, prompt_crawler_settings, select_articles
from src.news_summarize import summarize_articles
from src.ppt_maker import create_report


def prompt_ailab_content() -> str:
    """AI Lab 콘텐츠를 사용자로부터 직접 입력 받기 (여러 줄).

    빈 줄에서 'END'를 입력하면 입력 종료. Ctrl-D(EOF)도 종료 신호로 처리.
    """
    print("\n" + "=" * 60)
    print("📥 AI Lab 콘텐츠 입력")
    print("=" * 60)
    print("AI Lab 요약 대상 내용을 붙여넣으세요. (여러 줄 가능)")
    print("입력을 마치려면 빈 줄에서 'END' 입력 (또는 Ctrl-D).")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def prompt_review_decision() -> str:
    """검토 단계 사용자 입력. 'accept' | 'resummarize' | 'reselect' 반환."""
    print("이 요약으로 진행할까요?")
    print("  a (또는 Enter): 진행 → AI Lab 요약 + PPT 생성")
    print("  r: 다시 요약 (선택한 기사 동일, 요약만 재생성)")
    print("  s: 기사 다시 선택 (크롤링 결과로 돌아가기)")
    while True:
        choice = input("선택 [a/r/s]: ").strip().lower()
        if choice in ("", "a"):
            return "accept"
        if choice == "r":
            return "resummarize"
        if choice == "s":
            return "reselect"
        print("❌ a, r, s 중 하나를 입력해주세요.")


def main():
    try:
        ensure_directories()

        # 0단계: 보고서 정보 입력
        print("\n" + "=" * 60)
        print("📝 0단계: 보고서 정보 입력")
        print("=" * 60)
        number = input("리포트 발행 호수를 입력하세요 (예: 25): ")
        date = input("리포트 발행 날짜를 입력하세요 (예: 2025년 12월 26일): ")

        # 1단계: 뉴스 크롤링 (한 번만 수행 — 재선택 시에도 재크롤링 X)
        crawler_cfg = prompt_crawler_settings()
        print("\n" + "=" * 60)
        print("📰 1단계: News Crawling")
        print("=" * 60)
        crawled_df = crawl_news(crawler_cfg)
        if crawled_df.empty:
            print("❌ 크롤링 결과가 비어있습니다. 종료합니다.")
            return

        # 1.5단계: 첫 기사 선택
        selected_df = select_articles(crawled_df)
        if selected_df is None or selected_df.empty:
            print("❌ No news selected. END.")
            return

        # 2단계: 요약 + 검토 루프
        while True:
            print("\n" + "=" * 60)
            print("🤖 2단계: AI 뉴스 요약")
            print("=" * 60)
            summary_text = summarize_articles(selected_df)
            if not summary_text:
                print("❌ 요약 생성 실패. 프로세스를 종료합니다.")
                return

            print("\n" + "=" * 60)
            print("🔎 요약 검토")
            print("=" * 60)
            print(summary_text)
            print("=" * 60)
            decision = prompt_review_decision()

            if decision == "accept":
                break
            if decision == "reselect":
                # crawled_df는 스코프에 살아있어 재크롤링 없이 같은 후보 목록으로 다시 선택
                selected_df = select_articles(crawled_df)
                if selected_df is None or selected_df.empty:
                    print("❌ No news selected. END.")
                    return
            # "resummarize"는 while 한 바퀴 돌며 summarize_articles 재호출

        # 3단계: AI Lab 콘텐츠 입력 + 요약
        ailab_content = prompt_ailab_content()

        print("\n" + "=" * 60)
        print("🔬 3단계: AI Lab 뉴스 요약")
        print("=" * 60)
        ailab_text = ailab_summarized(ailab_content)
        if not ailab_text:
            print("❌ AI Lab 요약 생성 실패. 프로세스를 종료합니다.")
            return

        # 4단계: PPT 생성
        print("\n" + "=" * 60)
        print("📊 4단계: PPT 보고서 생성")
        print("=" * 60)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"AIWeeklyReport_{timestamp}.pptx"
        create_report(
            pptx_in=str(PPT_TEMPLATE_FILE),
            pptx_out=str(output_path),
            number=number,
            date=date,
            text1=summary_text,
            text2=ailab_text,
        )

        print("\n" + "=" * 60)
        print("✅ 모든 프로세스 완료!")
        print(f"{output_path} 파일 생성까지 최대 5분정도 소요될 수 있습니다.")
        print("조금만 기다려주세요... 감사합니다!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n❌ 사용자에 의해 프로세스가 중단되었습니다.")
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"\n❌ 파일을 찾을 수 없습니다: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류가 발생했습니다: {e}")
        print("프로세스를 종료합니다.")
        sys.exit(1)


if __name__ == "__main__":
    main()
