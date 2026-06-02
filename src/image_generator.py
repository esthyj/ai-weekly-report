"""
기사별 AI 이미지 생성 모듈.

`.env`의 GOOGLE_API_KEY로 Google Gemini 이미지 모델(Generative Language API)을
호출해 기사 내용에 어울리는 일러스트를 생성한다. 보고서 특성상 **이미지 안에는
어떠한 글자도 들어가지 않도록** 프롬프트에 강하게 지시한다.

llm_client.py 와 동일한 정책:
- load_dotenv() 로 키 로드, SSL 검증 비활성(사내망)
- 실패 시 Korean 에러 메시지 출력 후 None 반환 (파이프라인은 계속 진행)
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

import requests
import urllib3
from dotenv import load_dotenv

from .llm_client import call_llm

# 이미지 모델 (필요 시 교체). gemini-3-pro-image = Nano Banana Pro, 현존 최상위 품질.
# generateContent 엔드포인트를 사용한다(Imagen :predict 와 형식이 다름).
# API 키 프로젝트에 Generative Language API(과금) 활성화가 되어 있어야 하며,
# 미활성/오류 시 generate_image() 는 None 을 반환한다.
IMAGE_MODEL = "gemini-3-pro-image"
IMAGE_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{IMAGE_MODEL}:generateContent"
)
ASPECT_RATIO = "1:1"
REQUEST_TIMEOUT = 120  # seconds

# 프롬프트 생성에 쓰는 Claude 모델 (요약 모듈과 동일 계열)
PROMPT_MODEL = "claude-opus-4-8"

# 사실적인(realistic) 이미지를 강제하는 규칙. 글자 금지 규칙과 함께 항상 덧붙인다.
STYLE_RULE = (
    "Render in a realistic, photorealistic style — natural lighting, real-world "
    "settings and materials, true-to-life detail, like a professional "
    "photograph. Avoid abstract, conceptual, cartoonish, low-poly, "
    "neon-glow, holographic or surreal/sci-fi looks."
)

# 이미지에 글자가 들어가지 않도록 하는 필수 규칙. 항상 프롬프트 끝에 덧붙인다.
NO_TEXT_RULE = (
    "ABSOLUTELY CRITICAL: Do NOT render any text, letters, numbers, words, "
    "captions, labels, titles, logos, watermarks, signage, UI text, or "
    "typography anywhere in the image. The image must contain zero readable "
    "characters. Pure wordless image only."
)

_PROMPT_SYSTEM = (
    "You are an art director selecting editorial photography concepts for a "
    "Korean insurance company's weekly AI/finance newsletter. Given a Korean "
    "news article, write ONE concise English image-generation prompt (2-4 "
    "sentences) describing a realistic, professional, photographic image that "
    "visually represents the article's theme. Describe a believable real-world "
    "scene, the setting, mood, composition and a corporate color palette "
    "(blues, teals, warm accents). Use a realistic, photorealistic style with "
    "natural lighting — avoid abstract, conceptual or surreal elements. Do not "
    "include real brand logos or identifiable real people. "
    "Never include any words, letters or text in the described scene. "
    "Output ONLY the prompt text, nothing else."
)

# SSL 검증을 끄므로 경고만 한 번 억제 (llm_client 의 httpx verify=False 와 동일 취지)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def build_visual_prompt(article_text: str) -> Optional[str]:
    """한글 기사 블록을 영문 editorial 일러스트 묘사로 변환. 실패 시 None."""
    visual = call_llm(
        system_prompt=_PROMPT_SYSTEM,
        user_prompt=article_text,
        model=PROMPT_MODEL,
        max_tokens=400,
        log_prefix="  [이미지] ",
    )
    return visual


def generate_image(article_text: str, out_path: Path) -> Optional[Path]:
    """기사 텍스트로 이미지를 생성해 out_path(PNG)에 저장. 성공 시 경로, 실패 시 None."""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("  [이미지] ❌ GOOGLE_API_KEY 가 .env 에 없습니다.")
        return None

    visual = build_visual_prompt(article_text)
    if not visual:
        print("  [이미지] ❌ 이미지 프롬프트 생성 실패.")
        return None

    full_prompt = f"{visual}\n\n{STYLE_RULE}\n\n{NO_TEXT_RULE}"

    try:
        resp = requests.post(
            IMAGE_ENDPOINT,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                    "imageConfig": {"aspectRatio": ASPECT_RATIO},
                },
            },
            timeout=REQUEST_TIMEOUT,
            verify=False,  # 사내망 정책 일관성
        )
    except requests.exceptions.RequestException as e:
        print(f"  [이미지] ❌ 이미지 요청 실패(네트워크): {e}")
        return None

    if resp.status_code != 200:
        print(f"  [이미지] ❌ 이미지 응답 오류 {resp.status_code}: {resp.text[:300]}")
        return None

    try:
        candidates = resp.json().get("candidates") or []
        if not candidates:
            print(f"  [이미지] ❌ 이미지 결과가 비어있습니다: {resp.text[:300]}")
            return None
        # parts 중 inlineData(이미지) 를 찾는다. 텍스트 part 가 함께 올 수 있음.
        parts = candidates[0].get("content", {}).get("parts", []) or []
        b64 = None
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                b64 = inline["data"]
                break
        if not b64:
            print(f"  [이미지] ❌ 응답에 이미지 데이터가 없습니다: {resp.text[:300]}")
            return None
        image_bytes = base64.b64decode(b64)
    except (ValueError, KeyError) as e:
        print(f"  [이미지] ❌ 이미지 응답 파싱 실패: {e}")
        return None

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(image_bytes)
    print(f"  [이미지] 💾 저장 완료: {out_path}")
    return out_path


# 단독 실행 테스트
if __name__ == "__main__":
    sample = (
        "[Title] 삼성화재, AI 기반 보험금 자동심사 시스템 도입 "
        "[Summary1] 머신러닝으로 보험금 청구 서류를 자동 분석함 "
        "[Insight] 보험사 업무 자동화로 처리 속도 향상 기대"
    )
    from .config import IMAGES_DIR
    result = generate_image(sample, IMAGES_DIR / "test_sample.png")
    print("결과:", result)
