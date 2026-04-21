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


def process_graphs_in_text(text: str) -> tuple[str, list[str]]:
    """텍스트의 -그래프- 태그를 matplotlib PNG로 변환.

    Returns: (처리된 텍스트, base64 PNG 리스트)
    플레이스홀더: [GRAPH:N]
    """
    graphs: list[str] = []

    def replace(m: re.Match) -> str:
        png = _process_one(m.group(1).strip())
        if png:
            graphs.append(png)
            return f"[GRAPH:{len(graphs) - 1}]"
        return "(그래프를 생성할 수 없습니다)"

    return GRAPH_PATTERN.sub(replace, text), graphs
