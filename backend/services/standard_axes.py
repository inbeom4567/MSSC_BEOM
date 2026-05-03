"""
표준 좌표평면 SVG 생성 모듈
무제-1.svg 기준 규격을 따름

사용 예시:
    svg = standard_coord_plane(width=200, height=180)
    with open('output.svg', 'w') as f:
        f.write(svg)
"""

# ──────────────────────────────────────────────────────────────
# 표준 규격 상수 (graph_style_guide.md 의 책 SVG 기준 × HWPX_SCALE)
# 한글에 박힐 때 적당한 크기로 보이도록 일괄 2배. 비율은 표준 그대로 유지.
# ──────────────────────────────────────────────────────────────
HWPX_SCALE      = 4.0              # 모든 픽셀 크기 스케일 (책 SVG 기준 ×4)

STROKE_COLOR    = "#231815"        # 표준 검정
STROKE_WIDTH    = 0.75 * HWPX_SCALE
ARROW_HALF_W    = 1.39 * HWPX_SCALE
ARROW_LEN       = 3.29 * HWPX_SCALE
ARROW_INDENT    = 0.59 * HWPX_SCALE
ARROW_LINE_GAP  = 2.24 * HWPX_SCALE

FONT_FAMILY     = "HyhwpEQ, HyhwpEQ"
FONT_SIZE       = 8.99 * HWPX_SCALE   # px

ORIGIN_LABEL_DX = -8.81 * HWPX_SCALE
ORIGIN_LABEL_DY = 10.90 * HWPX_SCALE


# ──────────────────────────────────────────────────────────────
# HyhwpEQ 폰트 PUA 매핑
# 한컴 수식편집기는 변수/점이름을 PUA 영역에 매핑함
#
# [로마체] (점 이름, 함수 이름, 단위 등 - 정자체)
#   A~Z: E000 ~ E019
#   a~z: E01A ~ E033
#   0~9: E034 ~ E03D
#
# [이탤릭] (변수 - 기울임체)
#   a~z (소문자): E0E5 ~ E0FE
#   A~Z (대문자): E0CC ~ E0E4 (블랙보드/이중라인 형태)
#   그리스 대문자 Α~Ψ: E084 ~ E09A
#   그리스 소문자 α~ω: E09B ~ E0B2
# ──────────────────────────────────────────────────────────────

# 이탤릭 소문자 a~z: E0E5 ~ E0FE
ITALIC_LOWER_BASE = 0xE0E5

# 로마체 소문자 a~z: E01A ~ E033 (점 이름 등)
ROMAN_LOWER_BASE  = 0xE01A

# 로마체 대문자 A~Z: E000 ~ E019 (점 이름)
ROMAN_UPPER_BASE  = 0xE000

# 이탤릭 그리스 소문자 (정확한 매핑 - 시각 검증 완료)
GREEK_LOWER_ITALIC = {
    'alpha': 0xE09D, 'beta': 0xE09E, 'gamma': 0xE09F, 'delta': 0xE0A0,
    'epsilon': 0xE0A1, 'zeta': 0xE0A2, 'eta': 0xE0A3, 'theta': 0xE0A4,
    'iota': 0xE0A5, 'kappa': 0xE0A6, 'lambda': 0xE0A7, 'mu': 0xE0A8,
    'nu': 0xE0A9, 'xi': 0xE0AA, 'omicron': 0xE0AB, 'pi': 0xE0AC,
    'rho': 0xE0AD, 'sigma': 0xE0AE, 'tau': 0xE0AF, 'upsilon': 0xE0B0,
    'phi': 0xE0B1, 'chi': 0xE0B2, 'psi': 0xE0B3, 'omega': 0xE0B4,
}

# 이탤릭 그리스 대문자 (E085~E09C)
GREEK_UPPER_ITALIC = {
    'Alpha': 0xE085, 'Beta': 0xE086, 'Gamma': 0xE087, 'Delta': 0xE088,
    'Epsilon': 0xE089, 'Zeta': 0xE08A, 'Eta': 0xE08B, 'Theta': 0xE08C,
    'Iota': 0xE08D, 'Kappa': 0xE08E, 'Lambda': 0xE08F, 'Mu': 0xE090,
    'Nu': 0xE091, 'Xi': 0xE092, 'Omicron': 0xE093, 'Pi': 0xE094,
    'Rho': 0xE095, 'Sigma': 0xE096, 'Tau': 0xE097, 'Upsilon': 0xE098,
    'Phi': 0xE099, 'Chi': 0xE09A, 'Psi': 0xE09B, 'Omega': 0xE09C,
}


# 로마체 숫자 매핑 (E034=1, E035=2, ..., E03C=9, E03D=0)
ROMAN_DIGIT = {
    '0': 0xE03D, '1': 0xE034, '2': 0xE035, '3': 0xE036, '4': 0xE037,
    '5': 0xE038, '6': 0xE039, '7': 0xE03A, '8': 0xE03B, '9': 0xE03C,
}

# 수식 기호 매핑
SYMBOL_MAP = {
    '-': 0xE046,  # − (마이너스, 긴 dash)
    '=': 0xE047,  # =
    '+': 0xE048,  # +
    '(': 0xE044,  # (
    ')': 0xE045,  # )
    '[': 0xE049,  # [
    ']': 0xE04A,  # ]
    '{': 0xE04B,  # {
    '}': 0xE04C,  # }
    '|': 0xE04D,  # |
    ';': 0xE04E,  # ;
    ':': 0xE04F,  # :
    ',': 0xE052,  # ,
    '.': 0xE053,  # .
    '/': 0xE054,  # /
    '<': 0xE055,  # <
    '>': 0xE056,  # >
    '?': 0xE057,  # ?
}


def hwp_text(text):
    """문자열 전체를 HyhwpEQ PUA 코드로 변환
    - 소문자 a-z: 이탤릭
    - 숫자 0-9: 로마체
    - 대문자 A-Z: 로마체 (점 이름)
    - 수식 기호 (-, =, +, 괄호 등): PUA
    - 그 외: 그대로 (공백 등)
    """
    out = []
    for c in text:
        if 'a' <= c <= 'z':
            out.append(chr(ITALIC_LOWER_BASE + ord(c) - ord('a')))
        elif 'A' <= c <= 'Z':
            out.append(chr(ROMAN_UPPER_BASE + ord(c) - ord('A')))
        elif c in ROMAN_DIGIT:
            out.append(chr(ROMAN_DIGIT[c]))
        elif c in SYMBOL_MAP:
            out.append(chr(SYMBOL_MAP[c]))
        else:
            out.append(c)
    return ''.join(out)


def hwp_var(label):
    """변수 라벨을 HyhwpEQ PUA 이탤릭 코드로 변환

    'x' -> 0xE0FC chr (이탤릭 x)
    'y' -> 0xE0FD chr (이탤릭 y)
    'theta' -> 0xE0A4 chr (이탤릭 θ)
    'pi' -> 0xE0AC chr (이탤릭 π)
    """
    if len(label) == 1 and 'a' <= label <= 'z':
        return chr(ITALIC_LOWER_BASE + ord(label) - ord('a'))
    if label in GREEK_LOWER_ITALIC:
        return chr(GREEK_LOWER_ITALIC[label])
    if label in GREEK_UPPER_ITALIC:
        return chr(GREEK_UPPER_ITALIC[label])
    return label


def hwp_point(label):
    """점 이름을 HyhwpEQ PUA 로마체 코드로 변환

    'O' -> 0xE00E chr (로마체 O)
    'A' -> 0xE000 chr (로마체 A)
    'P' -> 0xE00F chr (로마체 P)
    """
    if len(label) == 1 and 'A' <= label <= 'Z':
        return chr(ROMAN_UPPER_BASE + ord(label) - ord('A'))
    if len(label) == 1 and 'a' <= label <= 'z':
        return chr(ROMAN_LOWER_BASE + ord(label) - ord('a'))
    return label


# ──────────────────────────────────────────────────────────────
# 화살촉 polygon 생성
# ──────────────────────────────────────────────────────────────
def arrow_up(tip_x, tip_y):
    """위 방향 화살촉 polygon points (y축 끝)
    tip_x, tip_y: 화살촉 꼭짓점 좌표"""
    base_y = tip_y + ARROW_LEN
    indent_y = base_y - ARROW_INDENT
    return (
        f"{tip_x + ARROW_HALF_W} {base_y} "
        f"{tip_x} {indent_y} "
        f"{tip_x - ARROW_HALF_W} {base_y} "
        f"{tip_x} {tip_y} "
        f"{tip_x + ARROW_HALF_W} {base_y}"
    )

def arrow_right(tip_x, tip_y):
    """오른쪽 방향 화살촉 polygon points (x축 끝)"""
    base_x = tip_x - ARROW_LEN
    indent_x = base_x + ARROW_INDENT
    return (
        f"{base_x} {tip_y + ARROW_HALF_W} "
        f"{indent_x} {tip_y} "
        f"{base_x} {tip_y - ARROW_HALF_W} "
        f"{tip_x} {tip_y} "
        f"{base_x} {tip_y + ARROW_HALF_W}"
    )

def arrow_down(tip_x, tip_y):
    """아래 방향 화살촉 (음의 y축, 필요 시)"""
    base_y = tip_y - ARROW_LEN
    indent_y = base_y + ARROW_INDENT
    return (
        f"{tip_x - ARROW_HALF_W} {base_y} "
        f"{tip_x} {indent_y} "
        f"{tip_x + ARROW_HALF_W} {base_y} "
        f"{tip_x} {tip_y} "
        f"{tip_x - ARROW_HALF_W} {base_y}"
    )

def arrow_left(tip_x, tip_y):
    """왼쪽 방향 화살촉 (음의 x축, 필요 시)"""
    base_x = tip_x + ARROW_LEN
    indent_x = base_x - ARROW_INDENT
    return (
        f"{base_x} {tip_y - ARROW_HALF_W} "
        f"{indent_x} {tip_y} "
        f"{base_x} {tip_y + ARROW_HALF_W} "
        f"{tip_x} {tip_y} "
        f"{base_x} {tip_y - ARROW_HALF_W}"
    )


# ──────────────────────────────────────────────────────────────
# 표준 좌표평면 SVG 생성
# ──────────────────────────────────────────────────────────────
def standard_coord_plane(width=200, height=180,
                          ox=None, oy=None,
                          x_left=None, x_right=None,
                          y_up=None, y_down=None,
                          x_label="x", y_label="y",
                          show_o=True):
    """
    표준 좌표평면 SVG 생성

    Args:
        width, height : 전체 viewBox 크기 (단위 동일)
        ox, oy        : 원점 좌표 (None이면 width*0.48, height*0.52)
        x_left        : 원점에서 x축이 왼쪽으로 뻗는 길이 (None이면 자동)
        x_right       : 원점에서 x축이 오른쪽으로 뻗는 길이
        y_up          : 원점에서 y축이 위로 뻗는 길이
        y_down        : 원점에서 y축이 아래로 뻗는 길이
        x_label, y_label : 축 라벨 텍스트 ("x", "y", 빈 문자열 등)
        show_o        : 원점 O 라벨 표시 여부

    Returns:
        SVG 문자열
    """
    if ox is None:
        ox = width * 0.48
    if oy is None:
        oy = height * 0.52

    if x_left is None:
        x_left = ox - 25
    if x_right is None:
        x_right = (width - ox) - 25
    if y_up is None:
        y_up = oy - 20
    if y_down is None:
        y_down = (height - oy) - 25

    # 라인 양 끝 (화살촉이 들어갈 자리는 라인이 가지 않음)
    # 화살촉 꼭짓점은 라인 끝점에서 ARROW_LINE_GAP 만큼 더 나간 자리
    x_line_end_R = ox + x_right
    x_tip = x_line_end_R + ARROW_LINE_GAP
    x_line_start_L = ox - x_left

    y_line_end_T = oy - y_up
    y_tip = y_line_end_T - ARROW_LINE_GAP
    y_line_start_B = oy + y_down

    parts = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'viewBox="0 0 {width} {height}">'
    )
    parts.append('  <defs>')
    parts.append('    <style>')
    parts.append(f'      .axis-text {{ font-family: HyhwpEQ, "HCR Batang", serif; font-size: {FONT_SIZE}px; }}')
    parts.append(f'      .axis-fill {{ fill: {STROKE_COLOR}; }}')
    parts.append(f'      .axis-line {{ fill: none; stroke: {STROKE_COLOR}; '
                 f'stroke-miterlimit: 10; stroke-width: {STROKE_WIDTH}px; }}')
    parts.append('    </style>')
    parts.append('  </defs>')

    # y축 (라인 + 위쪽 화살촉)
    parts.append('  <g>')
    parts.append(f'    <line class="axis-line" x1="{ox}" y1="{y_line_start_B}" x2="{ox}" y2="{y_line_end_T}"/>')
    parts.append(f'    <polygon class="axis-fill" points="{arrow_up(ox, y_tip)}"/>')
    parts.append('  </g>')

    # x축 (라인 + 오른쪽 화살촉)
    parts.append('  <g>')
    parts.append(f'    <line class="axis-line" x1="{x_line_start_L}" y1="{oy}" x2="{x_line_end_R}" y2="{oy}"/>')
    parts.append(f'    <polygon class="axis-fill" points="{arrow_right(x_tip, oy)}"/>')
    parts.append('  </g>')

    # x 라벨 (x축 화살촉 꼭짓점 오른쪽) - hwp_var로 이탤릭 PUA 코드 변환
    if x_label:
        parts.append(f'  <text class="axis-text" transform="translate({x_tip + 1.5} {oy + 8.20})">'
                     f'<tspan x="0" y="0">{hwp_var(x_label)}</tspan></text>')

    # y 라벨 (y축 화살촉 꼭짓점 위 살짝 왼쪽) - hwp_var로 이탤릭 PUA 코드 변환
    if y_label:
        parts.append(f'  <text class="axis-text" transform="translate({ox - 7.44} {y_tip + 1.07})">'
                     f'<tspan x="0" y="0">{hwp_var(y_label)}</tspan></text>')

    # O 라벨 - 점 이름이므로 hwp_point로 PUA 로마체 코드 변환
    if show_o:
        parts.append(f'  <text class="axis-text" transform="translate({ox + ORIGIN_LABEL_DX} {oy + ORIGIN_LABEL_DY})">'
                     f'<tspan x="0" y="0">{hwp_point("O")}</tspan></text>')

    parts.append('</svg>')
    return '\n'.join(parts)


# ──────────────────────────────────────────────────────────────
# 데모
# ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # 무제-1.svg 그대로 재현
    svg_repro = standard_coord_plane(
        width=197.01, height=165.79,
        ox=94.87, oy=86.05,
        x_left=60.90, x_right=75.63,
        y_up=62.74,  y_down=50.92,
        x_label="", y_label="",   # 원본은 라벨 비어있음
        show_o=True,
    )
    with open('std_coord_plane.svg', 'w', encoding='utf-8') as f:
        f.write(svg_repro)

    # 일반적인 사용 (x, y 라벨 포함)
    svg_normal = standard_coord_plane(
        width=200, height=180,
        x_label="x", y_label="y",
    )
    with open('std_coord_plane_with_labels.svg', 'w', encoding='utf-8') as f:
        f.write(svg_normal)

    print("생성 완료:")
    print("  - std_coord_plane.svg (무제-1.svg 재현)")
    print("  - std_coord_plane_with_labels.svg (x, y 라벨 포함)")
