## 🛠️ Algorithm

## news_crawler.py
### 1단계: 검색 대상 정의
- SEARCH_CATEGORIES에 검색하고 싶은 기업명이 나열되어 있음.
- 당사 AI 위클리 리포트에 작성하는 주요 내용은 타 금융 대기업 내 진행되고 있는 AI 사업들이기 때문 (스타트업 X)
- 관리의 편의성을 위해 보험사, 은행, Tech, 증권사 등 카테고리를 나눔
### 2단계: 구글 뉴스 RSS URL 만들기 (get_rss_url())
- encoded_query = "{query} AI when:{days}d" 와 같이 작성하여 기업명(query)와 기간(days)를 기준으로 작성
### 3단계: 뉴스 크롤링 (crawl_news())
- feedparser.parse()를 통해 RSS를 읽고 feed.entries라는 기사 목록 변환 (이 과정에서 기사 목록(제목, 링크, 날짜 등)을 가져옴)
- 이 과정에서 각 기업 당 최대 candidates_per_query 개의 기사만큼 추출 (단, 제목에 EXCLUDE_KEYWORDS가 있으면 제외)
- deocde_url()을 통해 암호화된 구글 뉴스 RSS 링크를 원문 URL로 디코딩
- fetch_aricle()을 통해 실제 웹페이지에 접속해서 본문 텍스트 추출 (본문 길이가 min_content_length 이상이여야만 뉴스로 인정)
- calculated_score()을 통해 뉴스 점수 계산 (PRIORITY KEYWORDS가 제목에 있으면 점수*2, 본문에 있으면 점수*1을 부여)
- 각 기업마다 점수가 가장 높은 1개 기사의 메타데이터(기업, 제목, 발행일, url, 본문, 점수 등)를 candidates 리스트에 저장
