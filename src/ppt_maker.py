import re
from pathlib import Path
from typing import Union, Sequence
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_AUTO_SIZE, MSO_ANCHOR
from pptx.oxml.ns import qn
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

# ── 실제 폰트 metric 측정 (Pillow) ──────────────────────────────
# 한화고딕 .ttf 를 한 번 로드해 글자 advance 폭·줄높이를 직접 잰다.
# 한화고딕은 모든 굵기(EL/L/R/B/T)의 advance 폭과 ascent/descent 가 동일하므로
# 대표 폰트(R) 한 개로 모든 스타일의 폭/높이를 정확히 추정할 수 있다.
# 폰트 파일이 없으면 _char_width_em 근사로 자동 폴백한다.
_FONT_REF_PX = 1000  # 측정 기준 크기(클수록 반올림 오차↓). 결과는 font_pt 비율로 환산.
_font_metric_cache = {}

# CJK(한글/한자/전각)·CJK 문장부호 — 글자 사이 어디서나 줄바꿈 가능
_CJK_RE = re.compile(r'[가-힣㄰-㆏一-鿿　-〿＀-￯]')
# 줄바꿈 토큰: CJK 한 글자 | 공백 묶음 | 그 외(영문·숫자 단어) 묶음
_TOKEN_RE = re.compile(
    r'[가-힣㄰-㆏一-鿿　-〿＀-￯]'
    r'|\s+'
    r'|[^\s가-힣㄰-㆏一-鿿　-〿＀-￯]+'
)


def _char_width_em(ch: str) -> float:
    """폰트 파일이 없을 때 쓰는 근사 폭(em). CJK 1.0, 그 외 0.55."""
    o = ord(ch)
    if (0xAC00 <= o <= 0xD7A3       # 한글 음절
            or 0x3130 <= o <= 0x318F    # 한글 자모
            or 0x4E00 <= o <= 0x9FFF    # 한자
            or 0x3000 <= o <= 0x303F    # CJK 문장부호
            or 0xFF00 <= o <= 0xFFEF):  # 전각 영숫자/기호
        return 1.0
    return 0.55


def _get_metric_font():
    """대표 폰트를 _FONT_REF_PX 로 로드해 캐시. 실패 시 None(→ 근사 폴백)."""
    if "font" not in _font_metric_cache:
        try:
            from PIL import ImageFont
            from .config import FONT_METRIC_FILE
            _font_metric_cache["font"] = ImageFont.truetype(str(FONT_METRIC_FILE), _FONT_REF_PX)
        except Exception:
            _font_metric_cache["font"] = None
    return _font_metric_cache["font"]


def _line_height_em(font) -> float:
    """폰트의 ascent+descent 로 단일 줄간격 배율(em)을 도출."""
    asc, desc = font.getmetrics()
    return (asc + desc) / _FONT_REF_PX


# ── prefix(•/➔) 내어쓰기(hanging indent) 헬퍼 ────────────────────
# prefix 가 붙은 줄이 wrap 되면 둘째 줄부터 prefix 폭만큼 들여써서
# 첫 줄의 첫 글자 위치에 맞춘다. 폭 계산은 _wrap_line_count/_wrap_around 와
# 동일 규칙(실측 또는 _char_width_em 근사)이라 줄바꿈·높이와 정확히 일치한다.
def _prefix_width_pt(prefix: str, font_pt: float, font) -> float:
    """prefix('• '/'➔ ')의 advance 폭(pt). prefix 가 없으면 0."""
    if not prefix:
        return 0.0
    if font is not None:
        return font.getlength(prefix) * (font_pt / _FONT_REF_PX)
    return sum(_char_width_em(c) for c in prefix) * font_pt


def _prefix_width_emu(prefix: str, font_pt: float, font) -> int:
    return int(round(_prefix_width_pt(prefix, font_pt, font) * EMU_PER_PT))


def _set_hanging_indent(p, marL_emu: int, indent_emu: int = None):
    """문단에 marL/indent(EMU)를 직접 설정.
    indent_emu=None 이면 -marL_emu(prefix 가 줄에 포함된 native 경로용 진짜 내어쓰기).
    indent_emu=0 이면 문단 전체를 marL 만큼 오른쪽으로(이미지 경로의 continuation 문단용)."""
    if marL_emu <= 0:
        return
    pPr = p._p.get_or_add_pPr()
    pPr.set('marL', str(marL_emu))
    pPr.set('indent', str(-marL_emu if indent_emu is None else indent_emu))


def _read_marL_pt(para) -> float:
    """문단에 설정된 marL(EMU)을 pt 로 읽어온다(없으면 0). 읽기 전용."""
    pPr = para._p.find(qn('a:pPr'))
    if pPr is None:
        return 0.0
    marL = pPr.get('marL')
    return (int(marL) / EMU_PER_PT) if marL else 0.0


def _wrap_line_count(text: str, avail_pt: float, font_pt: float, font, hang_pt: float = 0.0) -> int:
    """그리디 줄바꿈으로 줄 수 계산. font 가 있으면 실제 advance 폭, 없으면 근사.
    hang_pt>0 이면 내어쓰기 — 첫 줄은 avail_pt, 둘째 줄부터 avail_pt-hang_pt 가용."""
    if not text.strip():
        return 1

    # 현재 줄 번호(lines)에 따른 가용폭. 둘째 줄부터 hang_pt 차감(최소 font_pt 로 clamp).
    def limit(line_no):
        return avail_pt if line_no == 1 else max(avail_pt - hang_pt, font_pt)

    scale = font_pt / _FONT_REF_PX if font is not None else None
    lines, cur = 1, 0.0
    for tok in _TOKEN_RE.findall(text):
        if font is not None:
            w = font.getlength(tok) * scale
        else:
            w = sum(_char_width_em(c) for c in tok) * font_pt

        if tok.isspace():
            # 줄 끝의 공백은 다음 줄로 넘기지 않고 흡수(줄 폭에 영향 X)
            if cur + w > limit(lines) and cur > 0:
                lines, cur = lines + 1, 0.0
            else:
                cur += w
            continue

        # 단어/글자가 현재 줄을 넘기면 새 줄로
        if cur + w > limit(lines) and cur > 0:
            lines, cur = lines + 1, w
        else:
            cur += w
    return lines


# 채워진 텍스트 프레임이 실제로 차지할 세로 높이를 추정(EMU).
# word_wrap=True 기준으로 박스 폭에 맞춰 줄바꿈되는 줄 수를 실제 폰트 폭으로 잰다.
# line_factor 를 주면 그 값을, None 이면 폰트 metric(ascent+descent)에서 도출.
def _estimate_text_frame_height(shape, line_factor: float = None) -> int:
    tf = shape.text_frame
    avail_pt = (shape.width - tf.margin_left - tf.margin_right) / EMU_PER_PT
    if avail_pt <= 0:
        avail_pt = shape.width / EMU_PER_PT

    font = _get_metric_font()
    lf = line_factor if line_factor is not None else (_line_height_em(font) if font else 1.2)

    total_pt = 0.0
    for para in tf.paragraphs:
        sizes = [r.font.size.pt for r in para.runs if r.font.size is not None]
        font_pt = max(sizes) if sizes else 12.0
        text = "".join(r.text for r in para.runs)
        # 내어쓰기(marL)가 설정된 문단은 continuation 줄이 좁아지므로 줄 수 추정에 반영
        hang_pt = _read_marL_pt(para)
        lines = _wrap_line_count(text, avail_pt, font_pt, font, hang_pt)
        total_pt += lines * font_pt * lf

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

            # 줄간격을 _render_visual_lines(이미지 경로)와 동일하게 고정.
            # PowerPoint 기본/테마 줄간격이 적용되면 실제 렌더가 _estimate_text_frame_height
            # 추정보다 커져 이미지 없는 기사 아래 간격이 잠식된다(기사 간 간격 불균등의 원인).
            try:
                p.line_spacing = 1.0
                p.space_before = Pt(0)
                p.space_after = Pt(0)
            except Exception:
                pass

            # prefix(•, ➔)는 인라인 서식과 무관하게 항상 태그 기본 스타일로 출력.
            # 단 밑줄은 빼서(➔ 뒤 본문 첫 글자부터 밑줄) prefix 아래엔 줄이 안 그려진다.
            if prefix:
                add_styled_run(p, prefix, font_name, font_size, False)
                # 내어쓰기: wrap 시 둘째 줄부터 prefix 폭만큼 들여써 첫 글자에 맞춘다.
                w = _prefix_width_emu(prefix, font_size, _get_metric_font())
                _set_hanging_indent(p, w)

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

# 줄바꿈을 직접 계산할 때 가용폭에서 빼는 안전 여백(pt).
# metric 추정과 PowerPoint 실제 렌더의 미세 오차로 그림 옆줄이 재줄바꿈되어
# 어긋나는 것을 방지한다(좌측 정렬이라 줄이 살짝 짧아지는 건 무해).
_WRAP_SAFETY_PT = 1.0


# 기사 블록을 '논리 줄'(제목/불릿/insight 한 줄) 리스트로 분해한다.
# 각 논리 줄 = (hang_pt, [(token_text, style), ...]). style = (font_name, size_pt, underline, italic, bold, color).
# _fill_text_frame 과 동일하게 parse_sections/get_tag_style/parse_inline 을 재사용하되,
# run 을 바로 쓰지 않고 이미지 둘러싸기 줄 계산에 쓸 토큰 목록을 만든다.
def _article_logical_lines(block: str):
    sections = parse_sections(block)
    if not sections:
        text = block.strip()
        return [_tokens_for_line(text, "한화고딕 EL", 12, False, "")] if text else []

    logical = []
    for tag, content in sections:
        prefix, font_name, font_size, underline, split = get_tag_style(tag)
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()] if split else [content.strip()]
        for line in filter(None, lines):
            logical.append(_tokens_for_line(line, font_name, font_size, underline, prefix))
    return logical


# 한 논리 줄을 (hang_pt, [(token, style), ...]) 로. prefix(•, ➔)는 태그 기본 스타일의 선두 토큰으로 포함.
# hang_pt 는 prefix advance 폭(pt) — wrap 시 continuation 시각 줄을 그만큼 들여쓰는 데 쓴다.
# 본문은 parse_inline 으로 인라인 서식을 반영하고 _TOKEN_RE 로 줄바꿈 단위 토큰으로 쪼갠다.
def _tokens_for_line(line: str, font_name: str, base_size: int, base_underline: bool, prefix: str):
    hang_pt = _prefix_width_pt(prefix, base_size, _get_metric_font())
    tokens = []
    if prefix:
        # prefix(•, ➔)에는 밑줄을 빼서 ➔ 뒤 본문 첫 글자부터 밑줄이 시작되게 한다.
        base_style = (font_name, base_size, False, False, False, None)
        for tok in _TOKEN_RE.findall(prefix):
            tokens.append((tok, base_style))
    for seg, ov in parse_inline(line):
        style = (
            font_name,
            ov.get("size", base_size),
            ov.get("underline", base_underline),
            ov.get("italic", False),
            bool(ov.get("bold", False)),
            ov.get("color"),
        )
        for tok in _TOKEN_RE.findall(seg):
            tokens.append((tok, style))
    return (hang_pt, tokens)


# 논리 줄들을 '이미지 둘러싸기'로 시각 줄(visual line)들로 분해한다.
# 현재 줄 상단 y < img_bottom_pt 이면 narrow_pt(그림 옆), 아니면 full_pt(그림 아래) 폭으로 줄바꿈.
# 논리 줄에 hang_pt(prefix 폭)가 있으면 그 줄의 둘째 시각 줄부터 가용폭을 hang_pt 만큼 줄이고
# marL 로 들여써 첫 글자에 맞춘다. _wrap_line_count·_estimate_text_frame_height 와 동일 규칙.
# 반환: (visual_lines, total_height_pt). visual_lines 의 각 원소 = (marL_emu, [(token, style), ...]).
def _wrap_around(logical_lines, narrow_pt: float, full_pt: float, img_bottom_pt: float, font):
    lf = _line_height_em(font) if font else 1.2
    visual = []
    y = 0.0

    def avail_at(top):
        return (narrow_pt if top < img_bottom_pt else full_pt) - _WRAP_SAFETY_PT

    for hang_pt, line_tokens in logical_lines:
        hang_emu = int(round(hang_pt * EMU_PER_PT))
        cur, cur_w, cur_size = [], 0.0, 0.0
        first_visual = True  # 이 논리 줄의 첫 시각 줄(=prefix 포함, 들여쓰기 없음)인가
        # 첫 줄은 hang 미반영, continuation 은 hang_pt 차감(폭이 비정상으로 작아지지 않게 1pt clamp).
        def avail_now(top, is_first):
            a = avail_at(top)
            return a if is_first else max(a - hang_pt, 1.0)
        avail = avail_now(y, first_visual)
        for tok, style in line_tokens:
            size = style[1]
            if font is not None:
                w = font.getlength(tok) * (size / _FONT_REF_PX)
            else:
                w = sum(_char_width_em(c) for c in tok) * size
            is_space = tok.isspace()
            if is_space and cur_w == 0:
                continue  # 줄 맨 앞 공백은 버린다
            if cur_w + w > avail and cur_w > 0:
                while cur and cur[-1][0].isspace():
                    cur.pop()
                if cur:
                    visual.append((0 if first_visual else hang_emu, cur))
                    y += cur_size * lf
                    first_visual = False
                    avail = avail_now(y, first_visual)
                cur, cur_w, cur_size = [], 0.0, 0.0
                if is_space:
                    continue
                cur, cur_w, cur_size = [(tok, style)], w, size
            else:
                cur.append((tok, style))
                cur_w += w
                cur_size = max(cur_size, size)
        # 논리 줄 끝 — 남은 토큰을 한 시각 줄로 확정(강제 줄바꿈)
        while cur and cur[-1][0].isspace():
            cur.pop()
        if cur:
            visual.append((0 if first_visual else hang_emu, cur))
            y += cur_size * lf
    return visual, y


# 시각 줄들을 텍스트 프레임에 1줄=1문단으로 그린다(연속 동일 style 토큰은 한 run 으로 병합).
# 줄높이를 metric(lf)과 일치시키기 위해 문단 간격을 0, 줄간격을 1.0 으로 고정.
def _render_visual_lines(tf, visual_lines):
    for i, (marL_emu, line) in enumerate(visual_lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        try:
            p.line_spacing = 1.0
            p.space_before = Pt(0)
            p.space_after = Pt(0)
        except Exception:
            pass
        # continuation 시각 줄은 marL 만큼 들여써 첫 글자에 맞춘다(prefix 미반복 → indent=0).
        if marL_emu > 0:
            _set_hanging_indent(p, marL_emu, indent_emu=0)
        merged = []
        for tok, style in line:
            if merged and merged[-1][1] == style:
                merged[-1] = (merged[-1][0] + tok, style)
            else:
                merged.append([tok, style])
        for text, style in merged:
            _add_styled_token_run(p, text, style)


def _add_styled_token_run(p, text: str, style):
    name, size, underline, italic, bold, color = style
    r = p.add_run()
    r.text = text
    r.font.name = name
    r.font.size = Pt(size)
    r.font.underline = underline
    r.font.italic = italic
    if bold:
        r.font.bold = True
    if color:
        r.font.color.rgb = RGBColor.from_string(color.lstrip("#"))


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

    # 줄바꿈 직접 계산용 — 폰트 metric, 영역 폭(pt), 좁은 폭(그림 옆), 이미지 폭(pt)
    font = _get_metric_font()
    full_pt = region_width / EMU_PER_PT
    narrow_pt = full_pt - (NEWS_IMG_WIDTH + NEWS_IMG_GAP) / EMU_PER_PT
    img_w_pt = NEWS_IMG_WIDTH / EMU_PER_PT

    cur_top = region_top
    for idx, block in enumerate(blocks):
        img_path = images[idx] if idx < len(images) else None
        has_img = bool(img_path)

        tb = slide.shapes.add_textbox(int(region_left), int(cur_top), int(region_width), Pt(20))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.TOP
        # 슬라이드 텍스트박스 기본 여백 제거 → region_left 에 본문이 밀착, 높이 추정도 폭과 일치
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        tf.margin_bottom = 0

        if not has_img:
            # 이미지 없는 기사 — 전체 폭, PowerPoint 네이티브 줄바꿈(기존 동작 유지).
            tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
            _fill_text_frame(tf, block, add_inter_article_gap=False)
            text_h = _estimate_text_frame_height(tb)
            tb.height = text_h
            cur_top += text_h + NEWS_ROW_GAP
            continue

        # 이미지 있는 기사 — 그림을 둘러싸도록 줄을 직접 계산.
        # 그림과 세로로 겹치는 줄만 좁게, 그림 아래 줄은 영역 전체 폭으로 흐른다.
        logical = _article_logical_lines(block)

        # 짧은 기사(그림보다 본문이 짧음) 판별: 전체 폭 기준 높이가 그림보다 작으면
        # 둘러쌀 아래 영역이 없으므로 전체를 좁게 두고 그림을 본문 높이로 캡(기존 동작).
        _, h_full_pt = _wrap_around(logical, full_pt, full_pt, 0.0, font)
        if h_full_pt < img_w_pt:
            visual, h_pt = _wrap_around(logical, narrow_pt, narrow_pt, float("inf"), font)
            text_h = int(h_pt * EMU_PER_PT)
            img_size = min(int(NEWS_IMG_WIDTH), text_h)
        else:
            visual, h_pt = _wrap_around(logical, narrow_pt, full_pt, img_w_pt, font)
            text_h = int(h_pt * EMU_PER_PT)
            img_size = int(NEWS_IMG_WIDTH)

        # 줄을 미리 끊었으므로 PowerPoint 가 다시 맞추지 않도록 auto_size 끔.
        tf.auto_size = MSO_AUTO_SIZE.NONE
        _render_visual_lines(tf, visual)
        tb.height = text_h

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