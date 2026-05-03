"""
표준 좌표평면 그래프 빌더
- 좌표평면 위에 함수 곡선, 점, 점선 보조선, 라벨, 눈금을 추가하여 SVG 생성

사용 예시:
    from graph_builder import Graph

    g = Graph(width=300, height=200, scale=20)
    g.plot(lambda x: -x**3 + 3*x**2, x_range=(-1, 4), color='#231815')
    g.point(2, 4, label='A', label_pos='above')
    g.dashed_v(2, 0, 4)        # x=2 수직 점선 (y=0~4)
    g.dashed_h(4, 0, 2)        # y=4 수평 점선 (x=0~2)
    svg = g.render()
"""

import math
import re
# backend의 sys.path 루트가 backend/ 이므로 `services.X` 형태로 import.
# (CLI 단독 실행 시 fallback — `python backend/services/graph_builder.py`에서도 작동)
try:
    from services.standard_axes import (
        STROKE_COLOR, STROKE_WIDTH, ARROW_HALF_W, ARROW_LEN, ARROW_INDENT,
        ARROW_LINE_GAP, FONT_SIZE, ORIGIN_LABEL_DX, ORIGIN_LABEL_DY,
        arrow_up, arrow_right, hwp_var, hwp_point, hwp_text,
        ITALIC_LOWER_BASE, ROMAN_UPPER_BASE, ROMAN_LOWER_BASE,
        GREEK_LOWER_ITALIC, GREEK_UPPER_ITALIC,
    )
except ImportError:
    from standard_axes import (
        STROKE_COLOR, STROKE_WIDTH, ARROW_HALF_W, ARROW_LEN, ARROW_INDENT,
        ARROW_LINE_GAP, FONT_SIZE, ORIGIN_LABEL_DX, ORIGIN_LABEL_DY,
        arrow_up, arrow_right, hwp_var, hwp_point, hwp_text,
        ITALIC_LOWER_BASE, ROMAN_UPPER_BASE, ROMAN_LOWER_BASE,
        GREEK_LOWER_ITALIC, GREEK_UPPER_ITALIC,
    )


# ──────────────────────────────────────────────────────────────────────
# 라벨 텍스트 → SVG (PUA + <tspan>) 변환
# 한글 수식입력기 표기 규칙(graph_style_guide.md, 한글 수식입력기_260425.txt)에
# 따라 함수명·그리스·위/아래첨자를 정확히 표현.
# ──────────────────────────────────────────────────────────────────────

_FUNC_NAMES = ('sin', 'cos', 'tan', 'sec', 'csc', 'cot', 'log', 'ln', 'exp')

_GREEK_WORDS = tuple(sorted(
    set(GREEK_LOWER_ITALIC.keys()) | set(GREEK_UPPER_ITALIC.keys()),
    key=len, reverse=True,
))

_THIN_SPACE = ' '  # 한글 수식입력기 백틱 작은 공백 ≒ thin space


def _find_close_brace(text: str, start: int) -> int:
    """text[start] = '{' 가정. 매치되는 '}' 위치. 없으면 -1."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _find_close_paren(text: str, start: int) -> int:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _roman_word(s: str) -> str:
    """소문자 단어 → 한글 수식입력기 로마체 PUA 코드 시퀀스."""
    out = []
    for c in s:
        if 'a' <= c <= 'z':
            out.append(chr(ROMAN_LOWER_BASE + ord(c) - ord('a')))
        elif 'A' <= c <= 'Z':
            out.append(chr(ROMAN_UPPER_BASE + ord(c) - ord('A')))
        else:
            out.append(c)
    return ''.join(out)


def _smart_label_text(text: str) -> str:
    """LaTeX 비슷한 라벨 → SVG 표시용 (PUA + <tspan>) 시퀀스.

    지원
    - LaTeX 백슬래시 그리스 (\\pi, \\theta) → PUA 그리스
    - 그리스 단어 (pi, theta, alpha …) → PUA 그리스 (이탤릭)
    - 합성 (2pi, 3theta) → 숫자(로마) + PUA 그리스
    - 함수명 (sin, cos, tan, log, ln, exp …) → 로마체 + thin space + 인자
      · 함수명 직후 `(...)` 는 괄호 자동 벗기고 인자만 표시
        (한글 수식입력기 규칙: sin`x — 백틱 작은 공백)
    - `^x`, `^{...}` → <tspan baseline-shift="super" font-size="70%">
    - `_x`, `_{...}` → <tspan baseline-shift="sub"  font-size="70%">
    - 영문 소문자 → 이탤릭 PUA / 대문자 → 로마체 PUA
    - 숫자·기호 → hwp_text 변환 (PUA 매핑)
    """
    # `\pi` 같은 LaTeX 백슬래시 단어를 일반 단어로 정규화
    text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)

    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]

        # 위/아래첨자
        if c in ('^', '_'):
            shift = 'super' if c == '^' else 'sub'
            i += 1
            if i < n and text[i] == '{':
                end = _find_close_brace(text, i)
                if end > 0:
                    inner = _smart_label_text(text[i + 1:end])
                    out.append(
                        f'<tspan baseline-shift="{shift}" font-size="70%">'
                        f'{inner}</tspan>'
                    )
                    i = end + 1
                    continue
            if i < n:
                inner = _smart_label_text(text[i])
                out.append(
                    f'<tspan baseline-shift="{shift}" font-size="70%">'
                    f'{inner}</tspan>'
                )
                i += 1
            continue

        # 함수명 (sin, cos, log, …)
        matched = False
        for fn in _FUNC_NAMES:
            if not text.startswith(fn, i):
                continue
            after = text[i + len(fn):i + len(fn) + 1]
            if after and after.isalpha():
                # 'sing' 'login' 같이 함수명 뒤에 영문이 이어지면 함수 아님
                continue
            out.append(_roman_word(fn) + _THIN_SPACE)
            i += len(fn)
            # 함수명 직후 `(...)` → 괄호 자동 벗기고 인자만 (한글 수식 sin`x 표기)
            if i < n and text[i] == '(':
                end = _find_close_paren(text, i)
                if end > 0:
                    out.append(_smart_label_text(text[i + 1:end]))
                    i = end + 1
            matched = True
            break
        if matched:
            continue

        # 그리스 단어 (pi, theta, …) — 단어 경계 검사로 'piano' 같은 거 회피
        for gw in _GREEK_WORDS:
            if not text.startswith(gw, i):
                continue
            after = text[i + len(gw):i + len(gw) + 1]
            if after and after.isalpha():
                continue
            out.append(hwp_var(gw))
            i += len(gw)
            matched = True
            break
        if matched:
            continue

        # 그 외 한 글자 — hwp_text 변환
        out.append(hwp_text(c))
        i += 1

    return ''.join(out)


# 추가 스타일 상수 — standard_axes 의 HWPX_SCALE 동기화
try:
    from services.standard_axes import HWPX_SCALE as _SC
except ImportError:
    from standard_axes import HWPX_SCALE as _SC

CURVE_STROKE_WIDTH    = 1.0 * _SC  # 함수 곡선 두께 (좌표축보다 살짝 두껍게)
DASHED_STROKE_WIDTH   = 0.5 * _SC
DASHED_ARRAY          = f"{1.5 * _SC} {1.5 * _SC}"

POINT_RADIUS          = 1.4 * _SC
LABEL_FONT_SIZE       = 8.99 * _SC


class Graph:
    """좌표평면 + 곡선 + 점 + 보조선을 통합한 SVG 그래프 빌더"""

    def __init__(self, width=300, height=220,
                 ox=None, oy=None, scale=20,
                 x_left_margin=20, x_right_margin=25,
                 y_top_margin=20,  y_bottom_margin=25,
                 x_label='x', y_label='y', show_o=True):
        """
        width, height : SVG 전체 크기
        ox, oy        : 원점 (None이면 자동)
        scale         : 좌표평면 1단위 = SVG 몇 px? (기본 20px)
        *_margin      : 원점에서 축 끝까지 거리는 자동 계산되지만,
                        margin 값으로 라벨 공간을 보장
        """
        self.W = width
        self.H = height
        self.scale = scale

        # 원점 자동 배치
        self.ox = ox if ox is not None else width  * 0.48
        self.oy = oy if oy is not None else height * 0.52

        # 축 끝점 (margin 고려)
        self.x_left  = self.ox - x_left_margin
        self.x_right = (width - self.ox) - x_right_margin
        self.y_up    = self.oy - y_top_margin
        self.y_down  = (height - self.oy) - y_bottom_margin

        self.x_label = x_label
        self.y_label = y_label
        self.show_o  = show_o

        self.elements = []  # 곡선·점·점선 등 추가 요소

    # ─── 좌표 변환 ────────────────────────────────────
    def to_svg(self, x, y):
        """수학 좌표 (x, y) -> SVG 좌표 (px, py).
        SVG는 y축이 아래로 가므로 부호 반전."""
        return self.ox + x * self.scale, self.oy - y * self.scale

    # ─── 함수 곡선 ────────────────────────────────────
    def plot(self, func, x_range, samples=120,
             color=None, stroke_width=None, dashed=False, y_clip=None):
        """함수를 그래프 위에 그림.

        func         : 단일 인자 함수 (x -> y)
        x_range      : (x_min, x_max) 튜플
        samples      : 샘플링 점 수 (많을수록 부드러움)
        color        : 색상 (기본 표준 검정)
        stroke_width : 선 두께 (기본 1.0)
        dashed       : 점선 여부
        y_clip       : (ymin, ymax) 또는 None. 범위 밖 sample을 만나면 폴리라인을
                       끊어 다음 segment 로 분리한다. clipPath 가 가장자리에서
                       잘라내는 것보다 자연스러운 그래프 가장자리 표현이 가능.
        """
        color = color or STROKE_COLOR
        sw = stroke_width if stroke_width is not None else CURVE_STROKE_WIDTH

        x_min, x_max = x_range
        segments: list[list[tuple[float, float]]] = []
        current: list[tuple[float, float]] = []

        def flush():
            nonlocal current
            if len(current) >= 2:
                segments.append(current)
            current = []

        for i in range(samples + 1):
            x = x_min + (x_max - x_min) * i / samples
            try:
                y = func(x)
            except (ValueError, ZeroDivisionError, OverflowError):
                flush()
                continue
            if y is None or math.isnan(y) or math.isinf(y):
                flush()
                continue
            if y_clip is not None and (y < y_clip[0] or y > y_clip[1]):
                flush()
                continue
            current.append((x, y))
        flush()

        for seg in segments:
            self._add_polyline(seg, color, sw, dashed)

    def _add_polyline(self, points, color, sw, dashed):
        """수학 좌표 점들을 SVG polyline으로 변환"""
        svg_pts = [self.to_svg(x, y) for x, y in points]
        path_d = "M " + " L ".join(f"{px:.3f},{py:.3f}" for px, py in svg_pts)
        dash_attr = f' stroke-dasharray="{DASHED_ARRAY}"' if dashed else ''
        self.elements.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linejoin="round" '
            f'stroke-linecap="round"{dash_attr}/>'
        )

    # ─── 점 ──────────────────────────────────────────
    def point(self, x, y, label=None, label_pos='above_right',
              color=None, radius=None):
        """점을 그리고 옵션으로 라벨도 표시

        label_pos : 'above', 'below', 'left', 'right',
                    'above_left', 'above_right', 'below_left', 'below_right'
        """
        color = color or STROKE_COLOR
        r = radius if radius is not None else POINT_RADIUS

        px, py = self.to_svg(x, y)
        self.elements.append(
            f'<circle cx="{px:.3f}" cy="{py:.3f}" r="{r}" fill="{color}"/>'
        )

        if label:
            # 라벨 위치 오프셋 계산
            dx, dy = self._label_offset(label_pos)
            lx, ly = px + dx, py + dy
            self.elements.append(
                f'<text x="{lx:.3f}" y="{ly:.3f}" class="axis-text">'
                f'{hwp_point(label) if label.isupper() else hwp_var(label)}</text>'
            )

    def _label_offset(self, pos):
        """라벨 위치별 (dx, dy) 오프셋"""
        d = LABEL_FONT_SIZE  # 기준 거리
        offsets = {
            'above':       (-d * 0.35,  -d * 0.5),
            'below':       (-d * 0.35,   d * 1.3),
            'left':        (-d * 1.3,    d * 0.4),
            'right':       ( d * 0.5,    d * 0.4),
            'above_left':  (-d * 1.0,   -d * 0.3),
            'above_right': ( d * 0.4,   -d * 0.3),
            'below_left':  (-d * 1.0,    d * 1.2),
            'below_right': ( d * 0.4,    d * 1.2),
        }
        return offsets.get(pos, (d * 0.4, -d * 0.3))

    # ─── 점선 보조선 ─────────────────────────────────
    def dashed_v(self, x, y_from, y_to, color=None, stroke_width=None):
        """수직 점선 (x = const, y_from ~ y_to)"""
        color = color or STROKE_COLOR
        sw = stroke_width if stroke_width is not None else DASHED_STROKE_WIDTH
        x1, y1 = self.to_svg(x, y_from)
        x2, y2 = self.to_svg(x, y_to)
        self.elements.append(
            f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
            f'stroke="{color}" stroke-width="{sw}" '
            f'stroke-dasharray="{DASHED_ARRAY}"/>'
        )

    def dashed_h(self, y, x_from, x_to, color=None, stroke_width=None):
        """수평 점선 (y = const, x_from ~ x_to)"""
        color = color or STROKE_COLOR
        sw = stroke_width if stroke_width is not None else DASHED_STROKE_WIDTH
        x1, y1 = self.to_svg(x_from, y)
        x2, y2 = self.to_svg(x_to,   y)
        self.elements.append(
            f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
            f'stroke="{color}" stroke-width="{sw}" '
            f'stroke-dasharray="{DASHED_ARRAY}"/>'
        )

    def line(self, x1, y1, x2, y2, color=None, stroke_width=None, dashed=False):
        """일반 직선"""
        color = color or STROKE_COLOR
        sw = stroke_width if stroke_width is not None else STROKE_WIDTH
        sx1, sy1 = self.to_svg(x1, y1)
        sx2, sy2 = self.to_svg(x2, y2)
        dash_attr = f' stroke-dasharray="{DASHED_ARRAY}"' if dashed else ''
        self.elements.append(
            f'<line x1="{sx1:.3f}" y1="{sy1:.3f}" x2="{sx2:.3f}" y2="{sy2:.3f}" '
            f'stroke="{color}" stroke-width="{sw}"{dash_attr}/>'
        )

    # ─── 축 위 눈금 ───────────────────────────────────
    # ★ 라벨이 좌표축·곡선·점선과 겹쳐도 가독성을 절대 보장하기 위한 강력 규정:
    #   - 흰 후광 + 검정 글자를 별도 <text> 두 개로 분리하여 그림.
    #     (paint-order 속성은 resvg-py 등 일부 PNG 변환기가 무시해 후광이
    #      사라지는 사고가 있었음 — 두 요소로 분리하면 어느 변환기에서도
    #      흰 outline 이 보장됨.)
    #   - 흰 후광 두께 = 폰트의 35% (LABEL_FONT_SIZE × 0.35)
    #   - axis-라벨 거리 = 폰트의 1.6배 이상 (글자 자체가 axis 선에 닿지 않게)
    _HALO_W = LABEL_FONT_SIZE * 0.35

    @staticmethod
    def _halo_text(x: float, y: float, anchor: str, text: str, halo_w: float) -> str:
        """흰 후광 + 검정 글자를 두 <text> 요소로 그려 SVG→PNG 변환 시에도 후광 보장."""
        common = (
            f'x="{x:.3f}" y="{y:.3f}" class="axis-text" '
            f'text-anchor="{anchor}"'
        )
        return (
            f'<text {common} fill="white" stroke="white" stroke-width="{halo_w:.2f}" '
            f'stroke-linejoin="round">{text}</text>'
            f'<text {common} fill="{STROKE_COLOR}">{text}</text>'
        )

    def x_tick(self, x, label, label_pos='below'):
        """x축 위에 눈금 라벨. 라벨에 흰 후광 + 음·양 빗겨가기 적용."""
        px, py = self.to_svg(x, 0)
        tick_h = STROKE_WIDTH * 1.5
        self.elements.append(
            f'<line x1="{px}" y1="{py - tick_h}" x2="{px}" y2="{py + tick_h}" '
            f'stroke="{STROKE_COLOR}" stroke-width="{STROKE_WIDTH}"/>'
        )
        shift = LABEL_FONT_SIZE * 0.30
        if x < 0:
            lx, anchor = px - shift, 'end'
        elif x > 0:
            lx, anchor = px + shift, 'start'
        else:
            lx, anchor = px, 'middle'
        # 거리 1.6 — 글자 위쪽이 axis 선에서 폰트 0.9배 정도 떨어져 안 닿음
        ly = py + LABEL_FONT_SIZE * 1.6 if label_pos == 'below' else py - LABEL_FONT_SIZE * 0.9

        text = _smart_label_text(str(label))
        self.elements.append(self._halo_text(lx, ly, anchor, text, self._HALO_W))

    def y_tick(self, y, label, label_pos='left'):
        """y축 위에 눈금 라벨. 라벨에 흰 후광 + 음·양 빗겨가기."""
        px, py = self.to_svg(0, y)
        tick_w = STROKE_WIDTH * 1.5
        self.elements.append(
            f'<line x1="{px - tick_w}" y1="{py}" x2="{px + tick_w}" y2="{py}" '
            f'stroke="{STROKE_COLOR}" stroke-width="{STROKE_WIDTH}"/>'
        )
        # 빗겨가기 — 음수 라벨이 axis 선과 가깝지 않도록 충분히 비낌
        shift_y = LABEL_FONT_SIZE * 0.45
        if y < 0:
            ly = py + shift_y
        elif y > 0:
            ly = py - shift_y + LABEL_FONT_SIZE * 0.7
        else:
            ly = py + LABEL_FONT_SIZE * 0.35
        # 좌/우 위치 — y축 선과 충분히 떨어지도록
        gap = LABEL_FONT_SIZE * 0.35
        if label_pos == 'left':
            lx, anchor = px - gap, 'end'
        else:
            lx, anchor = px + gap, 'start'

        text = _smart_label_text(str(label))
        self.elements.append(self._halo_text(lx, ly, anchor, text, self._HALO_W))

    # ─── 원 ──────────────────────────────────────────
    def circle(self, cx, cy, r, color=None, stroke_width=None, fill='none'):
        """원 (수학 좌표 기준 중심·반지름)."""
        spx, spy = self.to_svg(cx, cy)
        spr = r * self.scale
        color = color or STROKE_COLOR
        sw = stroke_width if stroke_width is not None else CURVE_STROKE_WIDTH
        self.elements.append(
            f'<circle cx="{spx:.3f}" cy="{spy:.3f}" r="{spr:.3f}" '
            f'fill="{fill}" stroke="{color}" stroke-width="{sw}"/>'
        )

    # ─── 자유 위치 라벨 ──────────────────────────────
    def label(self, x, y, text, *, dx=0, dy=0, anchor='start', font_size=None):
        """자유 위치 텍스트 라벨 (수학 좌표 기준).

        LaTeX 비슷한 라벨(`$y=f(x)$`, `$y=2^x$`, `$\\sin x$` 등)을 그대로 받아
        `_smart_label_text` 로 한글 수식입력기 표기(PUA + <tspan>)로 변환.
        곡선·점선과 겹쳐도 가독성을 위해 흰 stroke 후광 적용.
        """
        spx, spy = self.to_svg(x, y)
        s = str(text)
        if s.startswith('$') and s.endswith('$'):
            s = s[1:-1]
        converted = _smart_label_text(s)
        size_attr = f' font-size="{font_size}"' if font_size else ''
        # 흰 후광 + 검정 글자를 두 <text> 로 분리 (resvg-py 호환)
        common = (
            f'x="{spx + dx:.3f}" y="{spy + dy:.3f}" class="axis-text" '
            f'text-anchor="{anchor}"{size_attr}'
        )
        self.elements.append(
            f'<text {common} fill="white" stroke="white" '
            f'stroke-width="{self._HALO_W:.2f}" stroke-linejoin="round">{converted}</text>'
            f'<text {common} fill="{STROKE_COLOR}">{converted}</text>'
        )

    # ─── 최종 렌더링 ─────────────────────────────────
    def render(self):
        """완성된 SVG 문자열 반환"""
        # 좌표축
        x_line_R = self.ox + self.x_right
        x_line_L = self.ox - self.x_left
        x_tip    = x_line_R + ARROW_LINE_GAP

        y_line_T = self.oy - self.y_up
        y_line_B = self.oy + self.y_down
        y_tip    = y_line_T - ARROW_LINE_GAP

        # 클리핑 영역 — viewBox 전체로 잡아 곡선이 좌표축 박스 위/아래로
        # 살짝 튀어나가도 viewBox 안이면 자연스럽게 표시되게 함.
        # (좌표축 끝점에서 칼같이 잘려 화살촉 위에 겹치는 듯한 인상 방지)
        clip_x = 0
        clip_y = 0
        clip_w = self.W
        clip_h = self.H

        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
            f'viewBox="0 0 {self.W} {self.H}">',
            '  <defs>',
            '    <style>',
            f'      .axis-text {{ font-family: HyhwpEQ, "HCR Batang", serif; '
            f'font-size: {FONT_SIZE}px; fill: {STROKE_COLOR}; }}',
            f'      .axis-fill {{ fill: {STROKE_COLOR}; }}',
            f'      .axis-line {{ fill: none; stroke: {STROKE_COLOR}; '
            f'stroke-miterlimit: 10; stroke-width: {STROKE_WIDTH}px; }}',
            '    </style>',
            f'    <clipPath id="plot-area">',
            f'      <rect x="{clip_x:.3f}" y="{clip_y:.3f}" '
            f'width="{clip_w:.3f}" height="{clip_h:.3f}"/>',
            f'    </clipPath>',
            '  </defs>',
        ]

        # 추가 요소들 (곡선·점·점선)을 클리핑 그룹 안에
        if self.elements:
            parts.append('  <g clip-path="url(#plot-area)">')
            for el in self.elements:
                parts.append('    ' + el)
            parts.append('  </g>')

        # y축 (클리핑 밖에서 그려서 화살촉이 보이도록)
        parts.append('  <g>')
        parts.append(f'    <line class="axis-line" x1="{self.ox}" y1="{y_line_B}" '
                     f'x2="{self.ox}" y2="{y_line_T}"/>')
        parts.append(f'    <polygon class="axis-fill" points="{arrow_up(self.ox, y_tip)}"/>')
        parts.append('  </g>')

        # x축
        parts.append('  <g>')
        parts.append(f'    <line class="axis-line" x1="{x_line_L}" y1="{self.oy}" '
                     f'x2="{x_line_R}" y2="{self.oy}"/>')
        parts.append(f'    <polygon class="axis-fill" points="{arrow_right(x_tip, self.oy)}"/>')
        parts.append('  </g>')

        # x 라벨
        if self.x_label:
            parts.append(f'  <text class="axis-text" '
                         f'transform="translate({x_tip + 1.5} {self.oy + 8.20})">'
                         f'<tspan x="0" y="0">{hwp_var(self.x_label)}</tspan></text>')
        # y 라벨
        if self.y_label:
            parts.append(f'  <text class="axis-text" '
                         f'transform="translate({self.ox - 7.44} {y_tip + 1.07})">'
                         f'<tspan x="0" y="0">{hwp_var(self.y_label)}</tspan></text>')
        # O 라벨
        if self.show_o:
            parts.append(f'  <text class="axis-text" '
                         f'transform="translate({self.ox + ORIGIN_LABEL_DX} {self.oy + ORIGIN_LABEL_DY})">'
                         f'<tspan x="0" y="0">{hwp_point("O")}</tspan></text>')

        parts.append('</svg>')
        return '\n'.join(parts)


# ──────────────────────────────────────────────────────────────
# 데모
# ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # 데모 1: 미적분1 그림 재현 (3차함수 -x^3 + 3x^2 + 1 정도)
    g = Graph(width=300, height=200, scale=18,
              x_left_margin=10, x_right_margin=25,
              y_top_margin=20, y_bottom_margin=20)
    g.plot(lambda x: -0.5 * x**3 + 3 * x**2 - 2 * x + 1,
           x_range=(-0.5, 5.5), samples=200)
    # 극댓값 위치에 수평 점선
    # y = f(x_max), x_max ~ 3.7 정도 (수치 미분)
    import scipy
    # scipy 없을 수도 있으니 수동
    best_x, best_y = 0, -float('inf')
    for i in range(1000):
        x = -0.5 + 6 * i / 1000
        y = -0.5 * x**3 + 3 * x**2 - 2 * x + 1
        if y > best_y:
            best_y, best_x = y, x
    g.dashed_h(best_y, 0, best_x)
    with open('demo_cubic.svg', 'w', encoding='utf-8') as f:
        f.write(g.render())

    # 데모 2: 포물선 + 두 교점
    g2 = Graph(width=260, height=220, scale=22,
               x_left_margin=15, x_right_margin=20,
               y_top_margin=15, y_bottom_margin=20)
    g2.plot(lambda x: x**2 - 2*x - 3, x_range=(-2, 4))
    g2.point(-1, 0, label='A', label_pos='below_left')
    g2.point( 3, 0, label='B', label_pos='below_right')
    g2.point( 1, -4, label='P', label_pos='below')
    with open('demo_parabola.svg', 'w', encoding='utf-8') as f:
        f.write(g2.render())

    # 데모 3: 사인 곡선
    import math as m
    g3 = Graph(width=320, height=180, scale=30,
               x_left_margin=10, x_right_margin=15,
               y_top_margin=10, y_bottom_margin=15)
    g3.plot(m.sin, x_range=(-0.3, 6.6))
    g3.x_tick(m.pi, 'pi')          # 그리스 π 자동 변환
    g3.x_tick(2 * m.pi, '2pi')     # '2pi' 그대로 (그리스 매핑은 단어만)
    g3.y_tick(1, '1')
    g3.y_tick(-1, '-1')
    with open('demo_sine.svg', 'w', encoding='utf-8') as f:
        f.write(g3.render())

    print("생성 완료: demo_cubic.svg, demo_parabola.svg, demo_sine.svg")
