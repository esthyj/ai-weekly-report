# Weekly Report AI Agent

## 🗝️ Key Features
- automates web news crawling
- automatically summarizes news articles
- generates PowerPoint (PPTX) slides with customized styling.
![Workflow](diagram.png)

## ⚙️ Installation

1. Clone the repository
```bash
   git clone https://github.com/esthyj/ai-weekly-report.git
   cd ai-weekly-report
```

2. Install dependencies
```bash
   pip install -r requirements.txt
```

3. Set up environment variables
```bash
   # Create .env file
   OPENAI_API_KEY=your_api_key_here
```

## 🚀 Usage

1. Add ailab content to `ailab_content.txt`

2. Run the script
```bash
   python main.py
```

3. Follow the prompts
```
   리포트 발행 호수를 입력하세요 (예: 25): 26
   리포트 발행 날짜를 입력하세요 (예: 2025년 12월 26일): 2025년 12월 30일
   선택할 뉴스 개수를 입력하세요 (기본값: 4): 3
   선택할 기사 번호를 입력하세요 (공백으로 구분, 예: 5 6 3 15): 7 2 10 8
```

4. `output.pptx` will be generated

