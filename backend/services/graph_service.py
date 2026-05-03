"""graph_service.py — Matplotlib 기반 수능/교과서 스타일 그래프 생성.

Claude 출력 형식:
-그래프-
함수: x**2 - 4*x + 3
함수2: 2*x - 1
x범위: -1, 5
y범위: -2, 6
점선: x=1, x=3, y=0
점: (1,0,채움), (2,-1,채움), (3,0,속빔)
직선: (0,1)→(4,5)
원: 0, 0, 2
라벨: "$y=f(x)$"@(4, 5)
x축: O@0, 1@1, 3@3
y축: 3@3, $-1$@-1
-그래프끝-
"""
import re
import io
import base64
import logging
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

GRAPH_PATTERN = re.compile(r'-그래프-\n(.*?)\n-그래프끝-', re.DOTALL)

# ── 스타일 상수 ──────────────────────────────────────────────────────────────
_CURVE_LW = 1.9
_AXIS_LW  = 0.9
_REF_LW   = 0.7
_POINT_MS = 6
_FONTSIZE  = 12

plt.rcParams.update({
    "mathtext.fontset": "stix",
    "font.family":      "STIXGeneral",
    "font.size":         _FONTSIZE,
})

# numpy 수식 평가 네임스페이스
_NS: dict = {k: getattr(np, k) for k in dir(np) if not k.startswith('_')}
_NS.update({"pi": np.pi, "e": np.e, "inf": np.inf, "np": np, "abs": np.abs})


def _ev(expr: str):
    return eval(expr.strip(), {"__builtins__": {}}, _NS)


def _math(s: str) -> str:
    """단일 영문자 레이블 → $...$ 자동 래핑 (이탤릭 처리)."""
    if s.startswith('$') or not s:
        return s
    if len(s) == 1 and s.isalpha():
        return f'${s}$'
    return s


def _expr_to_latex(expr: str) -> str:
    """파이썬 함수 표현식 → LaTeX 수식 (파서 없이 문자열 치환)."""
    s = expr.strip()
    s = s.replace('**', '^')
    s = re.sub(r'(\d|\))\s*\*\s*([a-zA-Z(])', r'\1\2', s)
    s = re.sub(r'([a-zA-Z)])\s*\*\s*(\d|\()', r'\1\2', s)
    s = s.replace('*', ' \\cdot ')
    s = s.replace('pi', '\\pi')
    s = re.sub(r'\bsqrt\(([^)]+)\)', r'\\sqrt{\1}', s)
    s = re.sub(r'\b(sin|cos|tan|log|ln|exp)\b', r'\\\1', s)
    return s


# ── 파서 ─────────────────────────────────────────────────────────────────────

def _parse(raw: str) -> dict:
    spec: dict = {
        "함수":  [],
        "x범위": None,
        "y범위": None,
        "점선":  [],
        "점":    [],
        "직선":  [],
        "원":    [],
        "라벨":  [],
        "x축":   [],
        "y축":   [],
        "원점":  "O",
        "축":    True,
    }
    for line in raw.strip().splitlines():
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key, val = key.strip(), val.strip()
        try:
            if key.startswith('함수'):
                spec['함수'].append(val)
            elif key == 'x범위':
                a, b = val.split(',', 1)
                spec['x범위'] = (_ev(a), _ev(b))
            elif key == 'y범위':
                a, b = val.split(',', 1)
                spec['y범위'] = (_ev(a), _ev(b))
            elif key == '점선':
                for p in re.split(r',\s*(?=[xy]=)', val):
                    p = p.strip()
                    if '=' in p:
                        ax_name, v = p.split('=', 1)
                        spec['점선'].append((ax_name.strip(), _ev(v.strip())))
            elif key == '점':
                for m in re.finditer(r'\(([^)]+)\)', val):
                    pts = [s.strip() for s in m.group(1).split(',')]
                    if len(pts) >= 3:
                        filled = pts[2] not in ('속빔', 'hollow', 'False', 'false')
                        spec['점'].append((_ev(pts[0]), _ev(pts[1]), filled))
            elif key == '직선':
                for m in re.finditer(r'\(([^)]+)\)\s*(?:→|->)\s*\(([^)]+)\)', val):
                    p1 = [_ev(v.strip()) for v in m.group(1).split(',')]
                    p2 = [_ev(v.strip()) for v in m.group(2).split(',')]
                    spec['직선'].append((p1[0], p1[1], p2[0], p2[1]))
            elif key == '원':
                for seg in val.split(';'):
                    pts = [_ev(p.strip()) for p in seg.strip().split(',')]
                    if len(pts) == 3:
                        spec['원'].append((pts[0], pts[1], pts[2]))
            elif key == '라벨':
                for m in re.finditer(r'"([^"]+)"@\(([^)]+)\)', val):
                    xy = [_ev(v.strip()) for v in m.group(2).split(',')]
                    spec['라벨'].append((m.group(1), xy[0], xy[1]))
            elif key == 'x축':
                for p in val.split(','):
                    p = p.strip()
                    if '@' in p:
                        lbl, xv = p.rsplit('@', 1)
                        spec['x축'].append((lbl.strip().strip('"'), _ev(xv.strip())))
            elif key == 'y축':
                for p in val.split(','):
                    p = p.strip()
                    if '@' in p:
                        lbl, yv = p.rsplit('@', 1)
                        spec['y축'].append((lbl.strip().strip('"'), _ev(yv.strip())))
            elif key == '원점':
                spec['원점'] = val.strip('"')
            elif key == '축':
                spec['축'] = val.lower() not in ('없음', 'false', 'no')
        except Exception as ex:
            logger.debug(f"그래프 파싱 오류 ({key}={val}): {ex}")
    return spec


# ── 렌더러 ───────────────────────────────────────────────────────────────────

def _render(spec: dict) -> str:
    xmin, xmax = spec['x범위']
    xs = np.linspace(xmin, xmax, 1200)

    # 함수값 계산 (Claude API에서 오는 신뢰된 입력이므로 builtins 허용)
    import warnings
    curves = []
    all_ys: list[float] = []
    for expr in spec['함수']:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                ys = eval(expr, dict(_NS, x=xs))
            ys = np.asarray(ys, dtype=float)
            curves.append(ys)
            finite = ys[np.isfinite(ys)]
            if len(finite):
                all_ys += [float(finite.min()), float(finite.max())]
        except Exception as ex:
            logger.warning(f"함수 계산 실패 '{expr}': {ex}")
            curves.append(None)

    # y범위 결정
    if spec['y범위']:
        ymin, ymax = spec['y범위']
    elif all_ys:
        span = max(all_ys) - min(all_ys) or 2
        ymin = min(all_ys) - span * 0.18
        ymax = max(all_ys) + span * 0.18
    else:
        ymin, ymax = -5.0, 5.0

    xpad = (xmax - xmin) * 0.14
    ypad = (ymax - ymin) * 0.14

    # Figure 생성
    fig, ax = plt.subplots(figsize=(4.0, 4.0))
    xlim = (xmin - xpad, xmax + xpad)
    ylim = (ymin - ypad, ymax + ypad)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    if spec['원']:
        ax.set_aspect('equal', adjustable='datalim')
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    # ── 화살표 축 ─────────────────────────────────────────────────────────
    if spec['축']:
        aw = dict(arrowstyle='->', color='black', lw=_AXIS_LW, mutation_scale=9)
        y0 = float(np.clip(0.0, ylim[0], ylim[1]))
        x0 = float(np.clip(0.0, xlim[0], xlim[1]))

        ax.annotate('', xy=(xlim[1], y0), xytext=(xlim[0], y0),
                    arrowprops=aw, annotation_clip=False)
        ax.annotate('', xy=(x0, ylim[1]), xytext=(x0, ylim[0]),
                    arrowprops=aw, annotation_clip=False)
        ax.text(xlim[1] + xpad * 0.09, y0, '$x$',
                ha='left', va='center', fontsize=_FONTSIZE, clip_on=False)
        ax.text(x0, ylim[1] + ypad * 0.09, '$y$',
                ha='center', va='bottom', fontsize=_FONTSIZE, clip_on=False)

        if spec['원점'] and xlim[0] <= 0 <= xlim[1] and ylim[0] <= 0 <= ylim[1]:
            ax.text(-xpad * 0.28, -ypad * 0.28, spec['원점'],
                    ha='right', va='top', fontsize=_FONTSIZE, clip_on=False)

    # ── 점선 ──────────────────────────────────────────────────────────────
    for axis, val in spec['점선']:
        if axis == 'x':
            ax.axvline(val, color='black', linestyle=':', lw=_REF_LW, zorder=1)
        elif axis == 'y':
            ax.axhline(val, color='black', linestyle=':', lw=_REF_LW, zorder=1)

    # ── 원 ────────────────────────────────────────────────────────────────
    for cx, cy, r in spec['원']:
        ax.add_patch(plt.Circle((cx, cy), r, fill=False, color='black', lw=_CURVE_LW))

    # ── 직선(선분) ────────────────────────────────────────────────────────
    for x1, y1, x2, y2 in spec['직선']:
        ax.plot([x1, x2], [y1, y2], color='black',
                lw=_CURVE_LW - 0.5, solid_capstyle='round', zorder=2)

    # ── 함수 곡선 ─────────────────────────────────────────────────────────
    clip_lo = ymin - ypad * 3
    clip_hi = ymax + ypad * 3
    for ys in curves:
        if ys is None:
            continue
        ys_c = np.where((ys < clip_lo) | (ys > clip_hi), np.nan, ys)
        ax.plot(xs, ys_c, color='black', lw=_CURVE_LW,
                solid_capstyle='round', solid_joinstyle='round', zorder=3)

    # ── 점 ────────────────────────────────────────────────────────────────
    for px, py, filled in spec['점']:
        if filled:
            ax.plot(px, py, 'o', color='black', markersize=_POINT_MS, zorder=5)
        else:
            ax.plot(px, py, 'o', color='black', markersize=_POINT_MS,
                    markerfacecolor='white', markeredgewidth=1.5, zorder=5)

    # ── x축 레이블 ────────────────────────────────────────────────────────
    # 틱 선과 겹치지 않도록 tick 기준 바깥쪽으로 살짝 빗겨가게 배치
    y0 = float(np.clip(0.0, ylim[0], ylim[1]))
    tick_h = ypad * 0.22
    shift_x = xpad * 0.08
    for lbl, xv in spec['x축']:
        if abs(xv) < 1e-9 and spec['원점']:
            continue
        ax.plot([xv, xv], [y0 - tick_h, y0 + tick_h],
                color='black', lw=_AXIS_LW)
        lx = xv - shift_x if xv < 0 else xv + shift_x if xv > 0 else xv
        ha = 'right' if xv < 0 else 'left' if xv > 0 else 'center'
        ax.text(lx, y0 - tick_h * 1.3, _math(lbl),
                ha=ha, va='top', fontsize=_FONTSIZE - 1, clip_on=False,
                bbox=dict(facecolor='white', edgecolor='none', pad=0.8), zorder=4)

    # ── y축 레이블 ────────────────────────────────────────────────────────
    x0 = float(np.clip(0.0, xlim[0], xlim[1]))
    tick_w = xpad * 0.22
    shift_y = ypad * 0.08
    for lbl, yv in spec['y축']:
        if abs(yv) < 1e-9:
            continue
        ax.plot([x0 - tick_w, x0 + tick_w], [yv, yv],
                color='black', lw=_AXIS_LW)
        ly = yv - shift_y if yv < 0 else yv + shift_y if yv > 0 else yv
        va = 'top' if yv < 0 else 'bottom' if yv > 0 else 'center'
        ax.text(x0 - tick_w * 1.3, ly, _math(lbl),
                ha='right', va=va, fontsize=_FONTSIZE - 1, clip_on=False,
                bbox=dict(facecolor='white', edgecolor='none', pad=0.8), zorder=4)

    # ── 텍스트 라벨 ───────────────────────────────────────────────────────
    for text, lx, ly in spec['라벨']:
        ax.text(lx, ly, text, ha='left', va='center',
                fontsize=_FONTSIZE, clip_on=False)

    # ── 함수 수식 자동 라벨 (사용자가 라벨 미지정 시) ───────────────────
    if not spec['라벨'] and spec['함수']:
        for idx, (expr, ys) in enumerate(zip(spec['함수'], curves)):
            if ys is None:
                continue
            finite_mask = np.isfinite(ys) & (ys >= ymin) & (ys <= ymax)
            if not finite_mask.any():
                continue
            visible_idx = np.where(finite_mask)[0]
            anchor_i = visible_idx[int(len(visible_idx) * 0.75)]
            ax_x = xs[anchor_i]
            ax_y = ys[anchor_i]
            direction = 1 if idx == 0 else -1
            ax.text(ax_x + xpad * 0.3, ax_y + ypad * 0.35 * direction,
                    f'$y = {_expr_to_latex(expr)}$',
                    ha='left', va='center', fontsize=_FONTSIZE, clip_on=False)

    # ── PNG 출력 ──────────────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150,
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def _process_one(raw: str) -> str | None:
    try:
        spec = _parse(raw)
        if not spec['x범위']:
            logger.warning("x범위 없음 — 그래프 생성 건너뜀")
            return None
        return _render(spec)
    except Exception as ex:
        logger.error(f"그래프 생성 실패: {ex}", exc_info=True)
        return None


def process_graphs_in_text(text: str, engine: str = "png") -> tuple[str, list[str]]:
    """텍스트의 -그래프- 태그를 PNG로 변환 (모드별 선택).

    engine:
      - "png" (기본): Matplotlib STIX 폰트 PNG 직접 렌더 (4월 21일 도입)
      - "svg":       graph_builder + standard_axes 로 HyhwpEQ 표준 SVG 렌더 후
                     resvg-py 로 PNG 변환 (2026-04-25 도입). 한국 교과서 픽셀
                     정합 + HyhwpEQ PUA 폰트가 한글 수식과 톤 일치.

    Returns: (처리된 텍스트, base64 PNG 리스트). 플레이스홀더: [GRAPH:N]
             모드 무관 동일 형식 — 호출부 영향 없음.
    """
    if engine == "svg":
        return _process_graphs_svg_to_png(text)

    # 기본 PNG 모드 (Matplotlib)
    graphs: list[str] = []

    def replace(m: re.Match) -> str:
        png = _process_one(m.group(1).strip())
        if png:
            graphs.append(png)
            return f"[GRAPH:{len(graphs) - 1}]"
        return "(그래프를 생성할 수 없습니다)"

    return GRAPH_PATTERN.sub(replace, text), graphs


def _process_graphs_svg_to_png(text: str) -> tuple[str, list[str]]:
    """SVG 모드 — graph_builder SVG → resvg-py PNG → base64."""
    try:
        from services.svg_to_png import svg_to_png
    except ImportError as ex:
        logger.warning(f"svg_to_png 모듈 로드 실패 — PNG 모드 폴백: {ex}")
        return process_graphs_in_text(text, engine="png")

    graphs: list[str] = []

    def replace(m: re.Match) -> str:
        try:
            spec = _parse(m.group(1).strip())
            if not spec.get('x범위'):
                return "(그래프를 생성할 수 없습니다)"
            svg = _render_svg(spec)
            # SVG → PNG 100% 1:1 변환 (viewBox 크기 == PNG 픽셀 크기). 확대/축소 없음.
            vb_m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
            if vb_m:
                vb_w = max(int(float(vb_m.group(1))), 100)
                vb_h = max(int(float(vb_m.group(2))), 100)
                png_bytes = svg_to_png(svg, width=vb_w, height=vb_h)
            else:
                png_bytes = svg_to_png(svg, width=800, height=600)
            graphs.append(base64.b64encode(png_bytes).decode('utf-8'))
            return f"[GRAPH:{len(graphs) - 1}]"
        except Exception as ex:
            logger.error(f"SVG→PNG 변환 실패: {ex}", exc_info=True)
            return "(그래프를 생성할 수 없습니다)"

    return GRAPH_PATTERN.sub(replace, text), graphs


# ── SVG 모드 (graph_builder + standard_axes 기반, HyhwpEQ PUA) ──────────────
# 2026-04-25 추가 — Matplotlib(STIX) 모드와 공존. 교과서 픽셀 정합 + 한글 수식
# 폰트(HyhwpEQ) 사용. main.py 의 신규 라우트 `/api/graph-svg/render` 가 호출.

def _auto_y_range(spec: dict, xmin: float, xmax: float) -> tuple[float, float]:
    """함수 표현식들에서 y범위 자동 추정 (Matplotlib 모드와 동일 로직)."""
    import warnings
    xs = np.linspace(xmin, xmax, 240)
    all_ys: list[float] = []
    for expr in spec['함수']:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                ys = eval(expr, dict(_NS, x=xs))
            ys = np.asarray(ys, dtype=float)
            finite = ys[np.isfinite(ys)]
            if len(finite):
                all_ys += [float(finite.min()), float(finite.max())]
        except Exception:
            continue
    if not all_ys:
        return -5.0, 5.0
    span = max(all_ys) - min(all_ys) or 2.0
    return min(all_ys) - span * 0.18, max(all_ys) + span * 0.18


def _make_func_evaluator(expr: str):
    """expr 문자열을 컴파일해 단일 인자 함수로 반환. graph_builder.plot 용."""
    code = compile(expr, '<graph-spec>', 'eval')

    def func(x, _c=code):
        try:
            return float(eval(_c, dict(_NS, x=x)))
        except Exception:
            return float('nan')
    return func


def _render_svg(spec: dict) -> str:
    """spec → SVG 문자열 (graph_builder.Graph 기반).

    좌표평면 viewBox·원점·scale 은 spec의 x범위/y범위에서 자동 계산한다.
    Claude `-그래프-` 태그 본문을 _parse 한 결과를 그대로 받음.
    """
    # 늦은 import — Matplotlib 모드만 쓸 때는 graph_builder 가져올 필요 없음
    from services.graph_builder import Graph

    if not spec['x범위']:
        raise ValueError("x범위 없음 — SVG 그래프 생성 불가")

    xmin, xmax = spec['x범위']
    if spec['y범위']:
        ymin, ymax = spec['y범위']
    else:
        ymin, ymax = _auto_y_range(spec, xmin, xmax)

    # 픽셀 좌표계 결정 — HWPX_SCALE=4.0 에 맞춰 viewBox 도 4배 비례.
    # padding 도 라벨/화살촉 공간을 충분히 확보하도록 비례 키움.
    target_w = 800.0
    pad_x = 90.0
    pad_y = 70.0
    x_span = max(xmax - xmin, 1e-6)
    y_span = max(ymax - ymin, 1e-6)
    scale = (target_w - 2 * pad_x) / x_span

    # viewBox 데이터 헤드룸 — spec y범위에서 살짝(7%)만 위·아래 여유.
    # 14% 였을 때는 그래프 영역이 세로로 너무 길어 보였음.
    head_ratio = 0.07
    head = y_span * head_ratio
    view_ymax = ymax + head
    view_ymin = ymin - head
    target_h = (view_ymax - view_ymin) * scale + 2 * pad_y

    # 원점 픽셀 좌표 — 수학 (0,0) 이 viewBox 어디 가는지
    ox = pad_x - xmin * scale
    oy = pad_y + view_ymax * scale

    # 좌표평면 끝 거리 (Graph 생성자의 *_margin 인자는 viewBox 가장자리까지의
    # 여백으로 동작하지만, 우리는 ox/oy 를 직접 계산했으므로 margin = pad)
    g = Graph(
        width=target_w, height=target_h,
        ox=ox, oy=oy, scale=scale,
        x_left_margin=pad_x, x_right_margin=pad_x,
        y_top_margin=pad_y, y_bottom_margin=pad_y,
        x_label='x' if spec['축'] else '',
        y_label='y' if spec['축'] else '',
        show_o=spec['축'] and bool(spec['원점']),
    )

    # ── 함수 곡선 ─────────────────────────────────────────────────────────
    # y_clip 을 viewBox 범위(view_ymin, view_ymax)와 일치 — 곡선이 viewBox
    # 안에서만 그려지고 vertically 자연스럽게 끊김. spec y범위를 초과하는
    # 함수 영역은 미적 균형을 위해 보여주지 않음 (수치 정확성보다 균형 우선).
    y_clip = (view_ymin, view_ymax)
    for idx, expr in enumerate(spec['함수']):
        try:
            func = _make_func_evaluator(expr)
            g.plot(func, x_range=(xmin, xmax), samples=180, y_clip=y_clip)
        except Exception as ex:
            logger.warning(f"SVG 함수 그리기 실패 '{expr}': {ex}")

    # ── 점선 (보조선) ─────────────────────────────────────────────────────
    for axis_name, val in spec['점선']:
        if axis_name == 'x':
            g.dashed_v(val, ymin, ymax)
        elif axis_name == 'y':
            g.dashed_h(val, xmin, xmax)

    # ── 직선(선분) ────────────────────────────────────────────────────────
    for x1, y1, x2, y2 in spec['직선']:
        g.line(x1, y1, x2, y2)

    # ── 원 ────────────────────────────────────────────────────────────────
    for cx, cy, r in spec['원']:
        g.circle(cx, cy, r)

    # ── 점 (채움/속빔) ────────────────────────────────────────────────────
    for px, py, filled in spec['점']:
        if filled:
            g.point(px, py, color='#231815')
        else:
            # 속빔 — graph_builder.point 는 채움 점만 지원하므로 circle 로 대체
            g.circle(px, py, 0.08, fill='white', stroke_width=0.9)

    # ── 라벨 (자유 위치 + 함수 라벨 자동 배치) ─────────────────────────
    # `y=...` / `f(x)=...` 류 함수 표기 라벨은 spec 좌표 무시하고 함수 곡선의
    # 75% 지점 근처에 자동 배치 — Claude가 좌표를 부정확하게 주더라도 라벨이
    # 대응 곡선 옆에 자연스럽게 붙도록 함. 그 외 라벨(원 표기, 점 이름 등)은
    # spec 좌표 그대로.
    _func_label_re = re.compile(r'^\s*\$?\s*(y\s*=|f\s*\(x\)\s*=)')
    _xs_anchor = None  # lazy
    for label_idx, (label_text, lx, ly) in enumerate(spec['라벨']):
        is_func_label = bool(_func_label_re.match(str(label_text)))
        if is_func_label and spec['함수']:
            if _xs_anchor is None:
                _xs_anchor = np.linspace(xmin, xmax, 240)
            # 같은 라벨 인덱스의 함수에 매칭, 부족하면 첫 함수 fallback
            expr = spec['함수'][min(label_idx, len(spec['함수']) - 1)]
            try:
                import warnings as _warn
                with _warn.catch_warnings():
                    _warn.simplefilter("ignore", RuntimeWarning)
                    ys_arr = eval(expr, dict(_NS, x=_xs_anchor))
                ys_arr = np.asarray(ys_arr, dtype=float)
                vis = (ys_arr >= ymin) & (ys_arr <= ymax) & np.isfinite(ys_arr)
                idxs = np.where(vis)[0]
                if len(idxs):
                    anchor_i = idxs[int(len(idxs) * 0.75)]
                    anchor_x = float(_xs_anchor[anchor_i])
                    lx = anchor_x + (xmax - xmin) * 0.04
                    # 라벨 x 에서의 함수값을 다시 계산하고 거기서 충분히 위로 띄움
                    # (y=x 처럼 기울기 큰 함수에서 anchor_y만 쓰면 라벨 x에서의
                    #  함수값이 더 커서 라벨이 곡선 위에 그대로 얹힘)
                    try:
                        with _warn.catch_warnings():
                            _warn.simplefilter("ignore", RuntimeWarning)
                            func_at_lx = float(eval(expr, dict(_NS, x=lx)))
                        if not np.isfinite(func_at_lx):
                            func_at_lx = float(ys_arr[anchor_i])
                    except Exception:
                        func_at_lx = float(ys_arr[anchor_i])
                    ly = func_at_lx + (ymax - ymin) * 0.08
            except Exception as ex:
                logger.debug(f"함수 라벨 자동 배치 실패 ('{label_text}'): {ex}")
        g.label(lx, ly, label_text, dx=2, dy=-2)

    # ── x축 / y축 눈금 ─────────────────────────────────────────────────────
    for label, xv in spec['x축']:
        # 원점은 O 라벨로 이미 표시되므로 0 위치는 건너뜀
        if abs(xv) < 1e-9 and spec['원점']:
            continue
        g.x_tick(xv, label)
    for label, yv in spec['y축']:
        if abs(yv) < 1e-9:
            continue
        g.y_tick(yv, label)

    return g.render()


def _process_one_svg(raw: str) -> str | None:
    """단일 그래프 spec(raw 텍스트) → SVG 문자열. 실패 시 None."""
    try:
        spec = _parse(raw)
        if not spec['x범위']:
            logger.warning("x범위 없음 — SVG 그래프 건너뜀")
            return None
        return _render_svg(spec)
    except Exception as ex:
        logger.error(f"SVG 그래프 생성 실패: {ex}", exc_info=True)
        return None


def process_graphs_to_svg(text: str) -> tuple[str, list[str]]:
    """텍스트의 -그래프- 태그를 SVG 문자열로 변환.

    Returns: (처리된 텍스트, SVG 문자열 리스트)
    플레이스홀더: [GRAPH:N]   (PNG 모드와 동일 형식 — 호출자에서 구분)
    """
    svgs: list[str] = []

    def replace(m: re.Match) -> str:
        svg = _process_one_svg(m.group(1).strip())
        if svg:
            svgs.append(svg)
            return f"[GRAPH:{len(svgs) - 1}]"
        return "(그래프를 생성할 수 없습니다)"

    return GRAPH_PATTERN.sub(replace, text), svgs
