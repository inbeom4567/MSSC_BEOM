import re
import logging

logger = logging.getLogger(__name__)

GRAPH_PATTERN = re.compile(r'-그래프-\n(.*?)\n-그래프끝-', re.DOTALL)

# SVG 유효성 기본 확인: <svg 태그로 시작하는지
_SVG_START = re.compile(r'^\s*<svg[\s>]', re.IGNORECASE)


def process_graphs_in_text(text: str) -> tuple[str, list[str]]:
    """텍스트에서 -그래프- 태그를 찾아 SVG 추출.

    Returns: (처리된 텍스트, SVG 문자열 리스트)
    그래프 플레이스홀더: [GRAPH:N]  (기존과 동일)
    """
    graphs = []

    def replace_match(match):
        tag_content = match.group(1).strip()
        if _SVG_START.match(tag_content):
            graphs.append(tag_content)
            return f"[GRAPH:{len(graphs)-1}]"
        else:
            logger.warning("그래프 태그 내 SVG를 찾을 수 없음")
            return "(그래프를 생성할 수 없습니다)"

    processed_text = GRAPH_PATTERN.sub(replace_match, text)
    return processed_text, graphs
