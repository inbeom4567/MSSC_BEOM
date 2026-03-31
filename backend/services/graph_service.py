import re
import io
import base64
import logging
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from matplotlib import rcParams

logger = logging.getLogger(__name__)

# 한글 폰트 설정
for font in ['Malgun Gothic', 'NanumGothic', 'AppleGothic', 'DejaVu Sans']:
    try:
        rcParams['font.family'] = font
        break
    except Exception:
        continue
rcParams['axes.unicode_minus'] = False


GRAPH_PATTERN = re.compile(r'-그래프-\n(.*?)\n-그래프끝-', re.DOTALL)


def parse_graph_tag(tag_content: str) -> dict:
    """그래프 태그 내용을 파싱하여 dict로 반환"""
    result = {
        "functions": [],
        "x_range": (-5, 5),
        "points": [],
        "labels": [],
        "title": "",
        "asymptotes": [],
        "grid": True,
    }

    for line in tag_content.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.startswith('함수:'):
            funcs = line[3:].strip()
            for f in funcs.split(','):
                f = f.strip()
                if f:
                    result["functions"].append(f)
        elif line.startswith('x범위:'):
            try:
                parts = line[4:].strip().split(',')
                result["x_range"] = (float(parts[0].strip()), float(parts[1].strip()))
            except (ValueError, IndexError):
                pass
        elif line.startswith('포인트:'):
            points_str = line[4:].strip()
            for match in re.finditer(r'\(([^)]+)\)', points_str):
                try:
                    coords = match.group(1).split(',')
                    result["points"].append((float(coords[0].strip()), float(coords[1].strip())))
                except (ValueError, IndexError):
                    pass
        elif line.startswith('라벨:'):
            result["labels"].append(line[3:].strip())
        elif line.startswith('제목:'):
            result["title"] = line[3:].strip()
        elif line.startswith('점근선:'):
            asym_str = line[4:].strip()
            for val in asym_str.split(','):
                val = val.strip()
                if val.startswith('x='):
                    result["asymptotes"].append(("v", float(val[2:])))
                elif val.startswith('y='):
                    result["asymptotes"].append(("h", float(val[2:])))

    return result


def _safe_eval_func(expr: str, x: np.ndarray) -> np.ndarray:
    """수학 함수 문자열을 안전하게 평가"""
    # y = ... 형태에서 우변 추출
    if '=' in expr:
        expr = expr.split('=', 1)[1].strip()

    # 수학 표현 변환
    expr = expr.replace('^', '**')
    expr = expr.replace('π', 'np.pi')
    expr = expr.replace('pi', 'np.pi')
    expr = expr.replace('sin', 'np.sin')
    expr = expr.replace('cos', 'np.cos')
    expr = expr.replace('tan', 'np.tan')
    expr = expr.replace('log', 'np.log')
    expr = expr.replace('ln', 'np.log')
    expr = expr.replace('sqrt', 'np.sqrt')
    expr = expr.replace('abs', 'np.abs')
    expr = expr.replace('e**', 'np.exp(1)**')

    # 묵시적 곱셈 처리: 2x → 2*x, 3(x) → 3*(x)
    expr = re.sub(r'(\d)([x(])', r'\1*\2', expr)
    expr = re.sub(r'(\))(\d)', r'\1*\2', expr)
    expr = re.sub(r'(\))(x)', r'\1*\2', expr)
    expr = re.sub(r'(x)(\()', r'\1*\2', expr)

    try:
        result = eval(expr, {"__builtins__": {}, "x": x, "np": np})
        return np.where(np.isfinite(result), result, np.nan)
    except Exception as e:
        logger.warning(f"함수 평가 실패: {expr} - {e}")
        return np.full_like(x, np.nan)


def generate_graph(params: dict) -> str:
    """파라미터로부터 Matplotlib 그래프를 생성하고 base64 PNG로 반환"""
    fig, ax = plt.subplots(1, 1, figsize=(7, 5), dpi=100)

    x_min, x_max = params["x_range"]
    x = np.linspace(x_min, x_max, 1000)

    colors = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c']

    # 함수 그래프 그리기
    for i, func_str in enumerate(params["functions"]):
        y = _safe_eval_func(func_str, x)
        label = params["labels"][i] if i < len(params["labels"]) else func_str
        color = colors[i % len(colors)]

        # 불연속점 처리 (큰 점프가 있는 부분을 끊기)
        dy = np.diff(y)
        jumps = np.where(np.abs(dy) > 50)[0]
        y_plot = y.copy()
        for j in jumps:
            y_plot[j] = np.nan

        ax.plot(x, y_plot, color=color, linewidth=2, label=label)

    # 포인트 표시
    for px, py in params["points"]:
        ax.plot(px, py, 'ko', markersize=6, zorder=5)
        ax.annotate(f'({px:.0f}, {py:.0f})', (px, py),
                    textcoords="offset points", xytext=(8, 8),
                    fontsize=9, color='#374151')

    # 점근선
    for direction, val in params["asymptotes"]:
        if direction == "v":
            ax.axvline(x=val, color='gray', linestyle='--', linewidth=1, alpha=0.7)
        else:
            ax.axhline(y=val, color='gray', linestyle='--', linewidth=1, alpha=0.7)

    # 축 설정
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.axvline(x=0, color='black', linewidth=0.5)
    ax.set_xlabel('x', fontsize=11)
    ax.set_ylabel('y', fontsize=11)

    if params["title"]:
        ax.set_title(params["title"], fontsize=13, fontweight='bold')

    if params["grid"]:
        ax.grid(True, alpha=0.3)

    if params["functions"]:
        ax.legend(fontsize=10, loc='best')

    plt.tight_layout()

    # PNG → base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)

    return base64.b64encode(buf.read()).decode('utf-8')


def process_graphs_in_text(text: str) -> tuple[str, list[str]]:
    """텍스트에서 -그래프- 태그를 찾아 이미지로 교체.
    Returns: (처리된 텍스트, 그래프 base64 이미지 리스트)
    """
    graphs = []

    def replace_match(match):
        tag_content = match.group(1)
        try:
            params = parse_graph_tag(tag_content)
            img_b64 = generate_graph(params)
            graphs.append(img_b64)
            return f"[GRAPH:{len(graphs)-1}]"
        except Exception as e:
            logger.error(f"그래프 생성 실패: {e}")
            return f"(그래프 생성 실패: {e})"

    processed_text = GRAPH_PATTERN.sub(replace_match, text)
    return processed_text, graphs
