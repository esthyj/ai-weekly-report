# Weekly Report AI Agent

- automates web news crawling
- automatically summarizes news articles
- generates PowerPoint (PPTX) slides with customized styling.

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
   python newppt_final.py
```

3. Follow the prompts
```
   Enter report issue number (e.g., 25): 26
   Enter report date (e.g., 2025년 12월 26일): 2025년 12월 30일
```

4. `output.pptx` will be generated

