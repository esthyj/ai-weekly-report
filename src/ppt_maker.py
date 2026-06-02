import re
import math
from pathlib import Path
from typing import Union, Sequence
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_AUTO_SIZE, MSO_ANCHOR
from .config import PPT_TEMPLATE_FILE

ShapePath = Union[int, Sequence[int]]

# ============================================================
# Settings
# ============================================================
TAG_RE = re.compile(r'\[(Title|Summary\d*|Insight)\]\s*', re.IGNORECASE)

# 인라인 서식 마크업 — 웹 final-review 에디터에서 직렬화한 형태
#   {b}…{/b}  {i}…{/i}  {u}…{/u}  {size=14}…{/size}  {color=#c00000}…{/color}
# 열림 태그는 value 포함, 닫힘 태그는 value 없음을 모두 매칭.
INLINE_RE = re.compile(
    r"\{(/?)(b|i|u|size(?:=\d+)?|color(?:=#[0-9a-fA-F]{6})?)\}"
)

# 태그별 스타일 설정 (prefix, font_name, font_size, underline, split_lines)
TAG_STYLES = {
    "title":   ("",   "한화고딕 B",  12, False, False),
    "summary": ("• ", "한화고딕 EL", 12, False, True),
    "insight": ("➔ ", "한화고딕 B",  12, True,  True),
}
DEFAULT_STYLE = ("", "한화고딕 EL", 12, False, True)

# Slide 0 shape indices — matches templates/AIWeeklyReport_format.pptx structure.
# If the template is restructured, re-check with list_all_shapes() and update here.
META_SHAPE_INDEX: ShapePath = 4         # 호수 + 날짜
NEWS_SHAPE_INDEX: ShapePath = (10, 0)   # 그룹 10 안의 자식 0 — 뉴스 요약 본문
AILAB_SHAPE_INDEX: ShapePath = (9, 0)   # 그룹 9 안의 자식 0 — AI Lab 요약 본문


# ============================================================
# Utility Functions
# ============================================================

# 태그에 맞는 스타일 반환 (Summary1, Summary2 등 모두 summary 스타일 적용)
def get_tag_style(tag: str):
    tag = tag.lower()
    if tag.startswith("summary"):
        return TAG_STYLES["summary"]
    return TAG_STYLES.get(tag, DEFAULT_STYLE)


# Split a long text by tag (header) and extract each tag's section content into a list
def parse_sections(text: str):
    matches = list(TAG_RE.finditer(text))
    return [
        (m.group(1).lower(), text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip())
        for i, m in enumerate(matches)
        if text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()
    ]


# Return specific shape. shape_index can be:
#   - int            : top-level shape index on the slide
#   - sequence[int]  : path descending into group shapes (e.g. (10, 0) → slide.shapes[10].shapes[0])
def find_shape_by_index(prs: Presentation, shape_index: ShapePath, slide_index: int = 0):
    if slide_index >= len(prs.slides):
        return None, None

    slide = prs.slides[slide_index]
    path = (shape_index,) if isinstance(shape_index, int) else tuple(shape_index)
    if not path:
        return None, None

    shapes = list(slide.shapes)
    shape = None
    for depth, idx in enumerate(path):
        if idx >= len(shapes):
            return None, None
        shape = shapes[idx]
        if depth < len(path) - 1:
            # Need to descend — current shape must be a group
            if not hasattr(shape, "shapes"):
                return None, None
            shapes = list(shape.shapes)

    return slide, shape


# Add a styled text run
def add_styled_run(paragraph, text, font_name, font_size, underline=False, color=None):
    r = paragraph.add_run()
    r.text = text
    r.font.name = font_name
    r.font.size = Pt(font_size)
    r.font.underline = underline
    if color:
        r.font.color.rgb = color


# Parse inline markup into a list of (text_segment, overrides) pairs.
# overrides may contain keys: bold, italic, underline, size (int), color ('#rrggbb').
# 마크업이 전혀 없으면 [(text, {})] 한 개 — 기존 평문 입력과 결과 동일.
def parse_inline(text: str):
    segments = []
    stack = []  # [("b", True) | ("i", True) | ("u", True) | ("size", 14) | ("color", "#c00000")]

    def current_overrides():
        ov = {}
        for typ, val in stack:
            if typ == "b":
                ov["bold"] = True
            elif typ == "i":
                ov["italic"] = True
            elif typ == "u":
                ov["underline"] = True
            elif typ == "size":
                ov["size"] = val
            elif typ == "color":
                ov["color"] = val
        return ov

    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            segments.append((text[pos:m.start()], current_overrides()))

        closing = m.group(1) == "/"
        body = m.group(2)

        if body in ("b", "i", "u"):
            typ, val = body, True
        elif body == "size":  # 닫힘 태그: 가장 최근 size를 닫음
            typ, val = "size", None
        elif body.startswith("size="):
            typ, val = "size", int(body[len("size="):])
        elif body == "color":
            typ, val = "color", None
        elif body.startswith("color=#"):
            typ, val = "color", body[len("color="):]
        else:
            typ, val = None, None  # 정규식상 도달 불가

        if closing:
            # 같은 타입 중 가장 최근 항목을 제거 (관대 파싱)
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == typ:
                    stack.pop(i)
                    break
        else:
            stack.append((typ, val))

        pos = m.end()

    if pos < len(text):
        segments.append((text[pos:], current_overrides()))

    return segments


# Add one run with optional per-run style overrides on top of tag base style.
def add_run_with_overrides(paragraph, text, font_name, font_size, base_underline=False, overrides=None):
    if not text:
        return
    r = paragraph.add_run()
    r.text = text
    r.font.name = font_name
    ov = overrides or {}
    r.font.size = Pt(ov.get("size", font_size))
    r.font.underline = ov.get("underline", base_underline)
    r.font.italic = ov.get("italic", False)
    if ov.get("bold"):
        r.font.bold = True
    if "color" in ov:
        r.font.color.rgb = RGBColor.from_string(ov["color"].lstrip("#"))


# ============================================================
# Dynamic shape height
# ============================================================

EMU_PER_PT = 12700  # 1pt = 12700 EMU

# 한 글자의 가로 폭을 폰트 크기(em) 기준 단위로 환산.
# 한글/한자/전각 문자는 1.0em, 그 외(영문·숫자·기호·공백)는 약 0.55em 로 근사.
def _char_width_em(ch: str) -> float:
    o = ord(ch)
    if (0xAC00 <= o <= 0xD7A3       # 한글 음절
            or 0x3130 <= o <= 0x318F    # 한글 자모
            or 0x4E00 <= o <= 0x9FFF    # 한자
            or 0x3000 <= o <= 0x303F    # CJK 문장부호
            or 0xFF00 <= o <= 0xFFEF):  # 전각 영숫자/기호
        return 1.0
    return 0.55


# 채워진 텍스트 프레임이 실제로 차지할 세로 높이를 추정(EMU).
# word_wrap=True 기준으로 박스 폭에 맞춰 줄바꿈되는 줄 수를 문자 폭 합으로 근사한다.
# line_factor: 폰트 크기 대비 줄 높이 배율(단일 줄간격 ≈ 1.2~1.25).
def _estimate_text_frame_height(shape, line_factor: float = 1.2) -> int:
    tf = shape.text_frame
    avail_pt = (shape.width - tf.margin_left - tf.margin_right) / EMU_PER_PT
    if avail_pt <= 0:
        avail_pt = shape.width / EMU_PER_PT

    total_pt = 0.0
    for para in tf.paragraphs:
        sizes = [r.font.size.pt for r in para.runs if r.font.size is not None]
        font_pt = max(sizes) if sizes else 12.0
        score = sum(_char_width_em(ch) for r in para.runs for ch in r.text)

        units_per_line = max(avail_pt / font_pt, 1.0)
        lines = max(1, math.ceil(score / units_per_line)) if score else 1
        total_pt += lines * font_pt * line_factor

    return int(total_pt * EMU_PER_PT)


# 도형 높이를 텍스트 양에 맞춰 동적으로 조절한다.
# 본문 정렬이 MIDDLE 이므로 위·아래로 대칭적인 약간의 여유(padding)가 생긴다.
# (그룹 자식이라도 chExt==ext 라 cy 가 곧 렌더링 높이.)
def autosize_shape_height(shape, padding=Pt(0)):
    tf = shape.text_frame
    content = _estimate_text_frame_height(shape)
    shape.height = int(content + tf.margin_top + tf.margin_bottom + padding)


# ============================================================
# Write PPT
# ============================================================

# Add report number and date
def set_number_and_date(prs: Presentation, number: str, date: str,
                        shape_index: ShapePath = META_SHAPE_INDEX, slide_index: int = 0):
    """숫자와 날짜를 특정 TextBox에 입력"""
    _, shape = find_shape_by_index(prs, shape_index, slide_index)
    
    if not shape:
        raise ValueError(f'슬라이드 {slide_index}의 {shape_index}번째 shape을 찾지 못했습니다.')
    if not shape.has_text_frame:
        raise ValueError(f'{shape_index}번째 shape에 text_frame이 없습니다.')

    tf = shape.text_frame
    tf.clear()
    
    combined_text = f"제{number}호 | {date}"
    
    p = tf.paragraphs[0]
    add_styled_run(p, combined_text, "한화고딕 L", 11, color=RGBColor(0x6C, 0x6A, 0x67))


# 태그 섹션([Title]/[Summary]/[Insight])을 text_frame 에 렌더링한다.
# tf.clear()/word_wrap/auto_size/vertical_anchor 설정과 높이 autosize 는 호출자 책임.
# add_inter_article_gap: insight 뒤(마지막 섹션 제외)에 기사 간격용 빈 줄을 넣을지.
def _fill_text_frame(tf, text: str, add_inter_article_gap: bool = True):
    sections = parse_sections(text)

    if not sections:
        add_styled_run(tf.paragraphs[0], text.strip(), "한화고딕 EL", 12)
        return

    first_para_used = False
    for i, (tag, content) in enumerate(sections):
        # Find the style for the tag
        prefix, font_name, font_size, underline, split = get_tag_style(tag)
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()] if split else [content.strip()]

        for line in filter(None, lines):
            p = tf.paragraphs[0] if not first_para_used and not tf.paragraphs[0].text else tf.add_paragraph()
            first_para_used = True

            # prefix(•, ➔)는 인라인 서식과 무관하게 항상 태그 기본 스타일로 출력
            if prefix:
                add_styled_run(p, prefix, font_name, font_size, underline)

            # 본문은 인라인 마크업을 파싱해 run 분할 — 마크업 없으면 한 개 run
            for seg, overrides in parse_inline(line):
                add_run_with_overrides(p, seg, font_name, font_size, underline, overrides)

        # insight 뒤 간격용 빈 줄 — 기사 사이 간격용이므로 마지막 섹션에는 넣지 않음
        # (끝 빈 줄이 MIDDLE 정렬에서 아래쪽 여백처럼 보이는 것을 방지)
        if add_inter_article_gap and tag == "insight" and i < len(sections) - 1:
            add_styled_run(tf.add_paragraph(), " ", "한화고딕 EL", 9)


# Insert summarized text structured with tag-specific styles
def set_textbox_from_summarizedtxt(prs: Presentation, text: str,
                                    shape_index: ShapePath = NEWS_SHAPE_INDEX, slide_index: int = 0):
    # Find specific index shape
    _, shape = find_shape_by_index(prs, shape_index, slide_index)

    if not shape:
        raise ValueError(f'슬라이드 {slide_index}의 {shape_index}번째 shape을 찾지 못했습니다.')
    if not shape.has_text_frame:
        raise ValueError(f'{shape_index}번째 shape에 text_frame이 없습니다.')

    # Clear existing text frame
    tf = shape.text_frame
    tf.clear()

    # PowerPoint 네이티브 auto-fit: 카드가 텍스트 높이에 정확히 밀착되도록(spAutoFit).
    # 두 본문 박스가 동일 엔진으로 크기 조정되어 내부 여백이 통일된다.
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
    # 세로 정렬을 TOP으로: 추정 높이가 실제 렌더보다 조금 커도 그 여유가 위·아래로
    # 나뉘지 않고 아래쪽으로만 가게 해, 본문이 항상 카드 상단(상여백 3.6pt)에 밀착된다.
    tf.vertical_anchor = MSO_ANCHOR.TOP

    _fill_text_frame(tf, text)
    autosize_shape_height(shape)


# 뉴스 본문을 [Title] 기준으로 기사 블록 단위로 분리한다(앞 태그 포함).
# CLI·웹 백엔드 공통 사용. [Title] 이 없으면 전체를 한 블록으로 취급.
def split_articles(news_text: str):
    matches = list(re.finditer(r'\[Title\]', news_text, re.IGNORECASE))
    if not matches:
        stripped = news_text.strip()
        return [stripped] if stripped else []
    blocks = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(news_text)
        block = news_text[m.start():end].strip()
        if block:
            blocks.append(block)
    return blocks


# 뉴스 본문을 기사별 행으로 렌더링하고, 이미지가 지정된 기사는 우측에 그림을 배치한다.
# images: 기사 순서에 맞춘 (경로 또는 None) 시퀀스. 카드 배경 도형은 그대로 두고
# 그 위에 슬라이드 레벨 텍스트박스/그림을 겹쳐 그린다.
NEWS_IMG_WIDTH = Inches(1.6)   # 우측 이미지 칼럼 폭
NEWS_IMG_GAP = Inches(0.12)    # 텍스트와 이미지 사이 간격
NEWS_ROW_GAP = Pt(12)          # 기사(행) 사이 세로 간격 ≈ 엔터 한 칸(한 줄)
NEWS_CARD_BOTTOM_PAD = Pt(6)   # 뉴스 카드 하단 여백(콘텐츠에 맞춰 축소할 때)
AILAB_GAP = Pt(10)             # 뉴스 카드 아래 ~ AI Lab 시작 사이 간격(작게)


def set_news_articles_with_images(prs: Presentation, news_text: str, images,
                                  shape_index: ShapePath = NEWS_SHAPE_INDEX, slide_index: int = 0):
    slide, card = find_shape_by_index(prs, shape_index, slide_index)
    if not card:
        raise ValueError(f'슬라이드 {slide_index}의 {shape_index}번째 shape을 찾지 못했습니다.')
    if not card.has_text_frame:
        raise ValueError(f'{shape_index}번째 shape에 text_frame이 없습니다.')

    # 카드 텍스트는 비우고 배경(카드 fill)만 남긴다.
    # auto_size 를 NONE 으로 고정 — 빈 텍스트로 인해 카드(배경)가 줄어드는 것 방지.
    card.text_frame.clear()
    card.text_frame.auto_size = MSO_AUTO_SIZE.NONE

    blocks = split_articles(news_text)
    images = list(images or [])

    # 레이아웃 영역 — 카드의 내부 여백을 그대로 사용해 기존 본문과 좌측 정렬을 맞춘다.
    ctf = card.text_frame
    region_left = card.left + ctf.margin_left
    region_top = card.top + ctf.margin_top
    region_width = card.width - ctf.margin_left - ctf.margin_right
    card_bottom = card.top + card.height

    cur_top = region_top
    for idx, block in enumerate(blocks):
        img_path = images[idx] if idx < len(images) else None
        has_img = bool(img_path)
        text_w = region_width - (NEWS_IMG_WIDTH + NEWS_IMG_GAP) if has_img else region_width

        tb = slide.shapes.add_textbox(int(region_left), int(cur_top), int(text_w), Pt(20))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
        tf.vertical_anchor = MSO_ANCHOR.TOP
        # 슬라이드 텍스트박스 기본 여백 제거 → region_left 에 본문이 밀착, 높이 추정도 폭과 일치
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        tf.margin_bottom = 0

        # 기사 단위 렌더 — 기사 내부엔 기사 간격 빈 줄이 필요 없다.
        _fill_text_frame(tf, block, add_inter_article_gap=False)
        text_h = _estimate_text_frame_height(tb)
        tb.height = text_h

        if has_img:
            # 이미지를 기사 본문 높이에 맞춘 정사각형으로(우측 정렬) 배치.
            # 고정 높이(1.6in)로 두면 짧은 본문에서 이미지가 본문보다 커져 다음 기사가
            # 밀려나며 간격이 크게 벌어지므로, 본문 높이로 캡을 씌워 행 높이를 본문 기준으로 유지.
            img_size = min(int(NEWS_IMG_WIDTH), int(text_h))
            slide.shapes.add_picture(
                str(img_path),
                int(region_left + region_width - img_size),
                int(cur_top),
                width=img_size,
                height=img_size,
            )

        # 다음 기사는 본문 높이 + 한 줄 간격만큼 아래에서 시작 (기사 간격 ≈ 엔터 한 칸)
        cur_top += text_h + NEWS_ROW_GAP

    # 카드(배경) 높이를 실제 콘텐츠에 맞춰 축소 → AI Lab 이 바로 아래에 붙을 수 있게 한다.
    content_bottom = cur_top - NEWS_ROW_GAP  # 마지막 기사 뒤 간격은 제외
    new_card_h = int(content_bottom + NEWS_CARD_BOTTOM_PAD - card.top)
    if new_card_h > 0:
        card.height = new_card_h

    if content_bottom > card_bottom:
        print(f"  ⚠️ 뉴스 본문이 템플릿 카드 영역을 초과했습니다(기사 수/이미지 과다). "
              f"넘침: {(content_bottom - card_bottom) / EMU_PER_PT:.0f}pt")


# AI Lab 그룹(헤더 'AI Lab' + 본문 카드)을 뉴스 카드 바로 아래로 이동시킨다.
# 뉴스 콘텐츠가 짧아 카드가 줄어든 만큼 AI Lab 도 위로 끌어올려 빈 공간을 없앤다.
def position_ailab_below_news(prs: Presentation, slide_index: int = 0, gap=AILAB_GAP):
    _, news_card = find_shape_by_index(prs, NEWS_SHAPE_INDEX, slide_index)
    if not news_card:
        return
    news_bottom = news_card.top + news_card.height

    # AILAB_SHAPE_INDEX 의 최상위 인덱스가 AI Lab 그룹(=이동 대상).
    group_idx = AILAB_SHAPE_INDEX[0] if not isinstance(AILAB_SHAPE_INDEX, int) else AILAB_SHAPE_INDEX
    _, ailab_group = find_shape_by_index(prs, group_idx, slide_index)
    if not ailab_group:
        return
    # 그룹 top 을 옮기면 자식(헤더+본문)이 함께 이동한다.
    ailab_group.top = int(news_bottom + gap)


# ============================================================
# Main Function
# ============================================================
# Create Report PPTX
def create_report(pptx_in: str, pptx_out: str, number: str, date: str,
                  text1: str, text2: str, news_images=None):

    # Check if template file exists
    if not Path(pptx_in).exists():
        raise FileNotFoundError(f"❌ PPT 템플릿 파일을 찾을 수 없습니다: {pptx_in}")

    prs = Presentation(pptx_in)

    # Step 1: Enter number of the report and date.
    set_number_and_date(prs, number, date, shape_index=META_SHAPE_INDEX, slide_index=0)

    # Step 2: Enter first summary text
    # 기사별 이미지가 하나라도 있으면 기사 행 단위로 렌더(텍스트=좌/이미지=우),
    # 없으면 기존 단일 텍스트박스 경로 그대로(하위 호환).
    if news_images and any(news_images):
        set_news_articles_with_images(prs, text1, news_images, shape_index=NEWS_SHAPE_INDEX, slide_index=0)
    else:
        set_textbox_from_summarizedtxt(prs, text1, shape_index=NEWS_SHAPE_INDEX, slide_index=0)

    # Step 3: Enter second summary text
    set_textbox_from_summarizedtxt(prs, text2, shape_index=AILAB_SHAPE_INDEX, slide_index=0)

    # Step 4: AI Lab 을 '국내외 AI 동향' 카드 바로 아래로 이동 (빈 공간 최소화)
    position_ailab_below_news(prs, slide_index=0)

    # Save
    prs.save(pptx_out)
    print(f"  💾 {pptx_out} 저장 완료!")


# For debugging: output shape information for all slides
def list_all_shapes(pptx_path: str):
    prs = Presentation(pptx_path)
    for slide_idx, slide in enumerate(prs.slides):
        print(f"\n=== 슬라이드 {slide_idx} ===")
        for i, shape in enumerate(slide.shapes):
            name = getattr(shape, "name", "N/A")
            has_tf = hasattr(shape, "has_text_frame") and shape.has_text_frame
            text_preview = ""
            if has_tf and shape.text_frame.text:
                text_preview = shape.text_frame.text[:30].replace('\n', ' ') + "..."
            print(f"  [{i}] {name} (text_frame: {has_tf}) {text_preview}")


# Test (If needed)
if __name__ == "__main__":

    list_all_shapes(str(PPT_TEMPLATE_FILE))

    test_text1 = (
        "[Title] 삼성화재 AI 보험금 자동심사 도입 "
        "[Summary1] 머신러닝으로 청구 서류를 자동 분석해 처리 시간을 단축함 "
        "[Summary2] 사기 청구 탐지 정확도도 향상됨 "
        "[Insight] 보험사 업무 자동화로 운영 효율 개선 기대\n\n"
        "[Title] 현대해상, 생성형 AI 상담 챗봇 출시 "
        "[Summary1] 고객 문의를 24시간 응대하는 챗봇을 도입함 "
        "[Insight] 상담 인력 부담 완화 및 응대 품질 표준화"
    )
    test_text2 = '''[Title] AI Lab 테스트 [Summary1] AI Lab 요약1 [Summary2] AI Lab 요약2 [Insight] AI Lab 인사이트'''

    # 첫 기사에만 샘플 이미지를 넣어 기사 행 단위 + 우측 이미지 배치를 검증
    from .config import IMAGES_DIR
    sample_img = IMAGES_DIR / "test_sample.png"
    news_images = [str(sample_img) if sample_img.exists() else None, None]

    create_report(
        pptx_in=str(PPT_TEMPLATE_FILE),
        pptx_out="test_output.pptx",
        number="테스트",
        date="2025년 1월 1일",
        text1=test_text1,
        text2=test_text2,
        news_images=news_images,
    )