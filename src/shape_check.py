"""shape_check.py — templates/AIWeeklyReport_format.pptx 각 shape에 작성된 내용 출력.

실행:
    python -m src.shape_check
"""
from pptx import Presentation

from config import PPT_TEMPLATE_FILE


def main() -> None:
    prs = Presentation(str(PPT_TEMPLATE_FILE))
    for slide_idx, slide in enumerate(prs.slides):
        for shape_idx, shape in enumerate(slide.shapes):
            if not getattr(shape, "has_text_frame", False) or not shape.has_text_frame:
                continue
            text = shape.text_frame.text
            if not text.strip():
                continue
            print(f"[슬라이드 {slide_idx} / shape {shape_idx}] {shape.name}")
            for line in text.splitlines():
                print(f"  {line}")
            print()


if __name__ == "__main__":
    main()
