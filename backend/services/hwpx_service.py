"""HWPX 파일 읽기/쓰기 서비스.

HWPX는 ZIP 파일 안에 XML(section0.xml)로 본문이 저장됨.
수식은 <hp:script> 태그에 한글 수식 코드로 저장.
텍스트는 <hp:t> 태그에 저장.
미주(endNote)에 해설이 저장되는 형식을 기본으로 지원.
"""

import zipfile
import io
import re
import logging
import html
from pathlib import Path
import json as _json
import os as _os

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data"

_BOX_TEMPLATES: dict = {}

def _load_box_templates() -> dict:
    global _BOX_TEMPLATES
    if _BOX_TEMPLATES:
        return _BOX_TEMPLATES
    path = _os.path.join(_os.path.dirname(__file__), '..', 'data', 'box_templates.json')
    try:
        with open(path, encoding='utf-8') as f:
            _BOX_TEMPLATES = _json.load(f)
    except Exception as e:
        import sys
        print(f"[경고] box_templates.json 로드 실패: {e}", file=sys.stderr)
        _BOX_TEMPLATES = {}
    return _BOX_TEMPLATES


def read_hwpx(file_bytes: bytes) -> str:
    """HWPX 파일에서 텍스트+수식을 추출. 미주(endNote) 자동 인식."""
    with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as z:
        section_files = [n for n in z.namelist() if n.startswith('Contents/section') and n.endswith('.xml')]
        if not section_files:
            raise ValueError("HWPX 파일에서 section XML을 찾을 수 없습니다.")

        all_text = []
        for section_file in sorted(section_files):
            xml_content = z.read(section_file).decode('utf-8')
            text = _parse_section(xml_content)
            all_text.append(text)

        return '\n'.join(all_text).strip()


def _extract_text_and_formulas(xml_fragment: str) -> str:
    """XML 조각에서 텍스트와 수식을 순서대로 추출."""
    parts = []
    for match in re.finditer(r'<hp:t>(.*?)</hp:t>|<hp:script>(.*?)</hp:script>', xml_fragment):
        if match.group(1) is not None:
            t = html.unescape(match.group(1).strip())
            if t and not t.startswith('<'):
                parts.append(t)
        elif match.group(2) is not None:
            s = html.unescape(match.group(2).strip())
            if s:
                parts.append(f'[{s}]')
    return ''.join(parts)


def _parse_section(xml_content: str) -> str:
    """section XML에서 문제+해설을 추출. 미주 자동 감지."""

    # 미주(endNote) 추출
    endnote_pattern = re.compile(
        r'<hp:endNote\s+number="(\d+)"[^>]*>(.*?)</hp:endNote>', re.DOTALL
    )
    endnote_map = {}
    for match in endnote_pattern.finditer(xml_content):
        num = match.group(1)
        endnote_xml = match.group(2)
        endnote_map[num] = _extract_text_and_formulas(endnote_xml)

    # 미주 제거한 본문
    body_xml = endnote_pattern.sub('', xml_content)

    # paragraph별 텍스트 추출
    # endNote가 제거된 XML에서 paragraph 단위로 추출
    body_lines = []
    endnote_at_line = {}  # line_index -> endnote_number

    # paragraph 패턴으로 분리
    p_pattern = re.compile(r'<hp:p[^>]*>(.*?)</hp:p>', re.DOTALL)

    # 원본 XML에서 각 paragraph의 endNote 번호 매핑
    for p_match in p_pattern.finditer(xml_content):
        p_content = p_match.group(1)
        en_match = re.search(r'<hp:endNote\s+number="(\d+)"', p_content)

        # endNote 제거한 텍스트 추출
        clean_p = endnote_pattern.sub('', p_content)
        line = _extract_text_and_formulas(clean_p).strip()
        idx = len(body_lines)
        body_lines.append(line)

        if en_match:
            endnote_at_line[idx] = en_match.group(1)

    if not endnote_map:
        # 미주 없음: 그냥 텍스트 반환
        return '\n'.join(body_lines)

    # 미주 있음: 번호별로 문제+해설 구조 생성
    result = []
    problem_count = len(endnote_map)
    sorted_endnotes = sorted(endnote_at_line.items())

    for i, (line_idx, en_num) in enumerate(sorted_endnotes):
        if problem_count > 1:
            result.append(f'\n-{en_num}번-')
        result.append('-문제-')

        # [주군 지시 — 3차 재명, 2026-04-22]
        # 새 경계 규칙: "미주가 있는 라인부터 다음 미주 직전 라인까지" 한 문제.
        # 즉 미주는 문제 시작(첫 paragraph)에 붙어있다는 전제.
        # 첫 미주 이전 paragraph들은 표지/머리말로 간주하고 버린다.
        start_line = line_idx
        next_line = (
            sorted_endnotes[i + 1][0]
            if i + 1 < len(sorted_endnotes)
            else len(body_lines)
        )
        problem_lines = [
            body_lines[j] for j in range(start_line, next_line) if body_lines[j].strip()
        ]

        # [방어 유지] 새 경계에서는 "이전 문제 선지 꼬리 흡수"가 발생하지 않아야
        # 하지만, 비정형 HWPX (미주가 여전히 문제 끝에 달려 있는 문서) 대비용으로
        # 유지. false-positive는 _strip_leading_choice_tail 내부 임계치로 억제됨.
        problem_lines = _strip_leading_choice_tail(problem_lines)

        result.append('\n'.join(problem_lines))

        result.append('\n-해설-')
        result.append(endnote_map.get(en_num, ''))

    return '\n'.join(result)


# ①②③④⑤ (CIRCLED DIGIT, U+2460~) + ➀➁➂➃➄ (DINGBAT CIRCLED SANS-SERIF, U+2780~)
_CHOICE_MARKS_RE = re.compile(r'[①②③④⑤➀➁➂➃➄]')


_ANSWER_MARKER_RE = re.compile(r'\[?\s*정답\s*\]?')


def _strip_leading_choice_tail(lines: list[str]) -> list[str]:
    """블록 맨 앞의 '이전 문제 선택지 꼬리'로 보이는 라인을 제거.

    휴리스틱 (2 Pass 통합):
    - Pass A: '①~⑤ 중 2개 이상이 한 라인에 몰려 있는' 케이스
      (예: "① 5  ② 6  ③ 7  ④ 8  ⑤ 9")
    - Pass B: '선지가 여러 라인으로 쪼개진' 케이스
      (예: "①[-2][-1][0]" + "④[1][2]" — 한 라인에 1개씩이지만
       블록 맨 앞에 연속해서 나옴)
    - 추가: 선지 직후의 "[정답] X" 라인도 이전 문제 꼬리로 함께 drop.
    """
    if not lines:
        return lines

    drop_until = 0
    total_marks = 0
    had_answer_marker = False
    for idx, ln in enumerate(lines[:7]):
        stripped = ln.strip()
        if not stripped:
            # 빈 줄: 선지 블록 중간의 공백 줄로 허용하고 계속
            drop_until = idx + 1
            continue

        marks = _CHOICE_MARKS_RE.findall(ln)

        # "[정답] ⑤" / "[정답] ➁" 같은 이전 문제 정답 마커 — 선지 후 꼬리
        is_answer_marker = (
            _ANSWER_MARKER_RE.match(stripped) is not None
            and len(stripped) <= 40
        )

        # 선지성 라인: 기호 1개 이상, 맨 앞이 선지 기호 또는 짧은 라인, 길이 120자 이하
        is_choice_line = (
            len(marks) >= 1
            and len(ln) <= 120
            and (stripped[0] in '①②③④⑤➀➁➂➃➄' or len(marks) >= 2)
        )

        if is_choice_line or is_answer_marker:
            drop_until = idx + 1
            total_marks += len(marks)
            if is_answer_marker:
                had_answer_marker = True
        else:
            break

    # drop 트리거: 누적 선지 기호 ≥ 2  또는  정답 마커 단독 발견
    # (정답 마커는 그 자체로 강한 신호 — 본문에 "[정답]"이 첫 줄에 짧게
    #  등장하는 정상 케이스는 거의 없다.)
    if total_marks >= 2 or had_answer_marker:
        return lines[drop_until:]
    return lines


_PHONE_RE = re.compile(r'010-\d{3,4}-\d{4}')
_BOX_CHAR_RUN_RE = re.compile(r'[═─━▬▀]{5,}')
_BRANDING_KEYWORDS = (
    '명품을 만든다',
    'NGDMath',
    '고등수학 학원',
)
_FORMULA_BLOCK_RE = re.compile(r'\[[^\]]+\]')


def _is_branding_block(text: str) -> bool:
    """표지/브랜딩 박스 여부 판정 (보수적 — 확실한 브랜딩만 True).

    정규 문제 블록이 아니라 학원 표지/연락처/구분선으로만 구성된 블록을
    걸러내기 위한 헬퍼. false positive 를 피하기 위해 아래 조건 중
    하나라도 확실히 매치되어야 True 를 반환.

    판정 기준(OR):
    - 전화번호 패턴 `010-XXX(X)-XXXX` 매치
    - 박스 문자(═ ─ ━ ▬ ▀) 연속 5개 이상
    - 브랜딩 키워드("명품을 만든다", "NGDMath", "고등수학 학원")
    - 본문이 너무 짧음(공백 제거 후 50자 미만) AND 수식 블록 `[...]` 3개 미만
    """
    if not text:
        return False

    if _PHONE_RE.search(text):
        return True
    if _BOX_CHAR_RUN_RE.search(text):
        return True
    for kw in _BRANDING_KEYWORDS:
        if kw in text:
            return True

    # 실질 본문이 거의 없는 블록 (공백 기준 50자 미만 + 수식도 3개 미만)
    compact = re.sub(r'\s+', '', text)
    if len(compact) < 50 and len(_FORMULA_BLOCK_RE.findall(text)) < 3:
        return True

    return False


def split_problems(text: str) -> list[dict]:
    """텍스트에서 -N번- 구분자로 여러 문제를 분리."""
    pattern = re.compile(r'-(\d+)번-')
    matches = list(pattern.finditer(text))

    if not matches:
        return [{"number": 1, "text": text.strip()}]

    problems = []
    for i, match in enumerate(matches):
        number = int(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content and not _is_branding_block(content):
            problems.append({"number": number, "text": content})

    return problems


# ──────────────────────────────────────────────
# HWPX 출력 (미주 형식)
# ──────────────────────────────────────────────

def create_hwpx(text: str, template_bytes: bytes = None, graphs: list | None = None) -> bytes:
    """텍스트를 HWPX 파일로 변환.

    graphs: base64 PNG 리스트. 각 인덱스가 텍스트 안의 [GRAPH:N] 단독 라인에 대응.
            제공 시 BinData/graph{N}.png 추가 + content.hpf manifest 갱신 +
            section XML의 [GRAPH:N] 단독 라인을 <hp:pic> 으로 치환.
    """
    if template_bytes:
        return _create_from_template(text, template_bytes, graphs)
    return _create_minimal(text, graphs)


def _create_from_template(text: str, template_bytes: bytes, graphs: list | None = None) -> bytes:
    """원본 HWPX를 템플릿으로 사용하여 section0.xml + BinData/content.hpf 갱신."""
    graphs = graphs or []
    buf = io.BytesIO()

    with zipfile.ZipFile(io.BytesIO(template_bytes), 'r') as src:
        original_section = src.read('Contents/section0.xml').decode('utf-8')
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as dst:
            for item in src.namelist():
                if item == 'Contents/section0.xml':
                    section_xml = _build_section_xml(text, original_section, graphs)
                    dst.writestr(item, section_xml)
                elif item == 'Contents/content.hpf' and graphs:
                    hpf = src.read(item).decode('utf-8')
                    hpf = _inject_graph_manifest(hpf, len(graphs))
                    dst.writestr(item, hpf)
                elif item == 'Preview/PrvText.txt':
                    dst.writestr(item, text[:500].encode('utf-8'))
                else:
                    dst.writestr(item, src.read(item))
            # 그래프 PNG 들을 BinData/graph{N}.png 로 추가
            import base64 as _b64
            for idx, png_b64 in enumerate(graphs):
                try:
                    dst.writestr(f'BinData/graph{idx}.png', _b64.b64decode(png_b64))
                except Exception as ex:
                    logger.error(f'graph{idx} BinData 쓰기 실패: {ex}')

    buf.seek(0)
    return buf.read()


def _create_minimal(text: str, graphs: list | None = None) -> bytes:
    """최소 HWPX 구조로 생성."""
    template_path = TEMPLATE_DIR / "template.hwpx"
    if template_path.exists():
        with open(template_path, 'rb') as f:
            return _create_from_template(text, f.read(), graphs)

    graphs = graphs or []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype', 'application/hwp+zip')
        z.writestr('META-INF/container.xml', _META_CONTAINER)
        z.writestr('Contents/header.xml', _HEADER_XML)
        hpf = _CONTENT_HPF
        if graphs:
            hpf = _inject_graph_manifest(hpf, len(graphs))
        z.writestr('Contents/content.hpf', hpf)
        z.writestr('Contents/section0.xml', _build_section_xml(text, None, graphs))
        z.writestr('version.xml', _VERSION_XML)
        import base64 as _b64
        for idx, png_b64 in enumerate(graphs):
            try:
                z.writestr(f'BinData/graph{idx}.png', _b64.b64decode(png_b64))
            except Exception as ex:
                logger.error(f'graph{idx} BinData 쓰기 실패: {ex}')
    buf.seek(0)
    return buf.read()


def _inject_graph_manifest(hpf_xml: str, num_graphs: int) -> str:
    """content.hpf 의 <opf:manifest> 안에 graph{N} 항목을 추가 (이미 있으면 skip)."""
    if num_graphs <= 0:
        return hpf_xml
    new_items = ''.join(
        f'<opf:item id="graph{i}" href="BinData/graph{i}.png" media-type="image/png" isEmbeded="1"/>'
        for i in range(num_graphs)
        if f'id="graph{i}"' not in hpf_xml
    )
    if not new_items:
        return hpf_xml
    # </opf:manifest> 직전에 삽입
    return hpf_xml.replace('</opf:manifest>', new_items + '</opf:manifest>', 1)


def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """PNG 헤더(IHDR)에서 width, height(px) 추출. PIL 의존성 없이."""
    if len(png_bytes) >= 24 and png_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        import struct
        w = struct.unpack('>I', png_bytes[16:20])[0]
        h = struct.unpack('>I', png_bytes[20:24])[0]
        return w, h
    return 640, 480  # fallback


def _build_picture_xml(image_id: str, w_units: int, h_units: int) -> str:
    """<hp:pic>...</hp:pic> 본체만 반환. hp:run 으로 감싸지 않음."""
    pic_id = abs(hash(image_id)) % 2_000_000_000 or 1
    inst_id = (pic_id + 1) % 2_000_000_000 or 2
    cx = w_units // 2
    cy = h_units // 2
    return (
        f'<hp:pic id="{pic_id}" zOrder="0" numberingType="PICTURE" '
        f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        f'dropcapstyle="None" href="" groupLevel="0" instid="{inst_id}" reverse="0">'
        f'<hp:offset x="0" y="0"/>'
        f'<hp:orgSz width="{w_units}" height="{h_units}"/>'
        f'<hp:curSz width="{w_units}" height="{h_units}"/>'
        f'<hp:flip horizontal="0" vertical="0"/>'
        f'<hp:rotationInfo angle="0" centerX="{cx}" centerY="{cy}" rotateimage="1"/>'
        f'<hp:renderingInfo>'
        f'<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        f'</hp:renderingInfo>'
        f'<hp:imgRect>'
        f'<hc:pt0 x="0" y="0"/><hc:pt1 x="{w_units}" y="0"/>'
        f'<hc:pt2 x="{w_units}" y="{h_units}"/><hc:pt3 x="0" y="{h_units}"/>'
        f'</hp:imgRect>'
        f'<hp:imgClip left="0" right="{w_units}" top="0" bottom="{h_units}"/>'
        f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        f'<hp:imgDim dimwidth="{w_units}" dimheight="{h_units}"/>'
        f'<hc:img binaryItemIDRef="{image_id}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
        f'<hp:effects/>'
        f'<hp:sz width="{w_units}" widthRelTo="ABSOLUTE" height="{h_units}" heightRelTo="ABSOLUTE" protect="0"/>'
        f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" '
        f'vertOffset="0" horzOffset="0"/>'
        f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        f'</hp:pic>'
    )


def _build_picture_paragraph(idx: int, png_b64: str) -> str:
    """[GRAPH:N] 단독 라인 자리에 들어갈 정상 형식의 picture paragraph.

    책 hwpx 의 실제 패턴 (`<hp:p id="..."><hp:run><hp:pic/><hp:t/></hp:run>
    <hp:linesegarray><hp:lineseg .../></hp:linesegarray></hp:p>`) 그대로
    재현. linesegarray 가 누락되면 한글이 파일을 거부함.
    """
    import base64 as _b64
    try:
        png_bytes = _b64.b64decode(png_b64)
    except Exception:
        return ''
    w_px, h_px = _png_dimensions(png_bytes)
    # 1px ≒ 26.46 unit (96 dpi 기준 HWP 단위 1/100mm). 폭 16000(160mm)으로 제한.
    # (HWPX_SCALE=4.0 시 PNG 가 더 크므로 표시 폭도 좀 더 넉넉히)
    w_units = int(w_px * 26.46)
    h_units = int(h_px * 26.46)
    MAX_W = 16000
    if w_units > MAX_W:
        h_units = int(h_units * MAX_W / w_units)
        w_units = MAX_W

    image_id = f'graph{idx}'
    para_id = (abs(hash(f'graph_para_{idx}')) % 2_000_000_000) or 1
    baseline = int(h_units * 0.847)  # 책 hwpx 패턴 비율
    pic_xml = _build_picture_xml(image_id, w_units, h_units)

    return (
        f'<hp:p id="{para_id}" paraPrIDRef="0" styleIDRef="0" '
        f'pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="0">'
        f'{pic_xml}'
        f'<hp:t/>'
        f'</hp:run>'
        f'<hp:linesegarray>'
        f'<hp:lineseg textpos="0" vertpos="0" vertsize="{h_units}" '
        f'textheight="{h_units}" baseline="{baseline}" spacing="540" '
        f'horzpos="0" horzsize="25796" flags="393216"/>'
        f'</hp:linesegarray>'
        f'</hp:p>'
    )


def _build_section_xml(text: str, original_section: str = None, graphs: list | None = None) -> str:
    """텍스트를 section XML로 변환. -문제-/-해설- → 미주 구조.

    graphs 가 제공되면 [GRAPH:N] 단독 라인을 picture run 으로 치환.
    """
    graphs = graphs or []

    # 원본에서 secPr, 네임스페이스 추출
    sec_pr = ''
    ns_tag = '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">'

    if original_section:
        sec_pr_match = re.search(r'(<hp:secPr.*?</hp:secPr>)', original_section, re.DOTALL)
        sec_pr = sec_pr_match.group(1) if sec_pr_match else ''
        ns_match = re.search(r'(<hs:sec[^>]+>)', original_section)
        if ns_match:
            ns_tag = ns_match.group(1)

    # 박스 마커를 sentinel로 교체
    text = _substitute_box_markers(text)

    # 텍스트를 문제+해설 블록으로 분리
    blocks = _parse_problem_blocks(text)

    eq_counter = [1]
    en_counter = [1]
    paragraphs = []
    first = True

    block_count = 0
    for block in blocks:
        if block['type'] == 'problem_with_solution':
            # 문제 사이에 빈 줄 10개 삽입 (첫 문제 제외)
            if block_count > 0:
                for _ in range(10):
                    paragraphs.append('<hp:p paraPrIDRef="0" styleIDRef="0"><hp:run charPrIDRef="0"><hp:t></hp:t></hp:run></hp:p>')
            block_count += 1

            problem_lines = block['problem'].split('\n')
            answer_text = block.get('answer', '')
            solution_text = block.get('solution', '')

            for i, line in enumerate(problem_lines):
                # [GRAPH:N] 단독 라인 → 정상 형식 picture paragraph 로 분기
                gm = _GRAPH_LINE_RE.match(line) if graphs else None
                if gm:
                    g_idx = int(gm.group(1))
                    if 0 <= g_idx < len(graphs):
                        # i == 0 인 경우 (첫 줄이 그림이면) 미주는 다음 텍스트 줄에 박는다 — 일단 단순화: 첫 줄이 그림이어도 미주 적용 안 함
                        paragraphs.append(_build_picture_paragraph(g_idx, graphs[g_idx]))
                        continue

                runs = _line_to_runs(line, eq_counter, graphs=graphs)

                if i == 0:
                    endnote_xml = _make_endnote(answer_text, solution_text, en_counter[0], eq_counter, graphs=graphs)
                    runs = f'<hp:run charPrIDRef="0"><hp:ctrl>{endnote_xml}</hp:ctrl></hp:run>' + runs
                    en_counter[0] += 1

                if first and sec_pr:
                    runs = f'<hp:run charPrIDRef="0">{sec_pr}</hp:run>' + runs
                    first = False

                if not runs:
                    runs = '<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>'
                paragraphs.append(f'<hp:p paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{runs}</hp:p>')
        else:
            # 일반 텍스트 줄
            for line in block['text'].split('\n'):
                # [GRAPH:N] 단독 라인 → picture paragraph
                gm = _GRAPH_LINE_RE.match(line) if graphs else None
                if gm:
                    g_idx = int(gm.group(1))
                    if 0 <= g_idx < len(graphs):
                        paragraphs.append(_build_picture_paragraph(g_idx, graphs[g_idx]))
                        continue

                runs = _line_to_runs(line, eq_counter, graphs=graphs)
                if first and sec_pr:
                    runs = f'<hp:run charPrIDRef="0">{sec_pr}</hp:run>' + runs
                    first = False
                if not runs:
                    runs = '<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>'
                paragraphs.append(f'<hp:p paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{runs}</hp:p>')

    body = '\n'.join(paragraphs)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{ns_tag}\n{body}\n</hs:sec>'


def _parse_problem_blocks(text: str) -> list[dict]:
    """텍스트를 문제+정답+해설 블록으로 분리."""
    blocks = []

    # 태그로 분리: -N번-, -문제-, -유사문항-, -정답-, -해설-
    parts = re.split(r'(-\d+번-|-문제-|-유사문항-|-정답-|-해설-)', text)

    current_problem = None
    current_type = None

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if re.match(r'-\d+번-', part):
            continue
        elif part in ('-문제-', '-유사문항-'):
            current_type = 'problem'
            current_problem = {'problem': '', 'answer': '', 'solution': ''}
        elif part == '-정답-':
            current_type = 'answer'
        elif part == '-해설-':
            current_type = 'solution'
        elif current_type == 'problem' and current_problem:
            current_problem['problem'] = part
        elif current_type == 'answer' and current_problem:
            current_problem['answer'] = part
        elif current_type == 'solution' and current_problem:
            current_problem['solution'] = part
            blocks.append({'type': 'problem_with_solution', **current_problem})
            current_problem = None
            current_type = None
        else:
            if not current_problem:
                blocks.append({'type': 'text', 'text': part})

    if current_problem:
        if current_problem.get('solution') or current_problem.get('answer'):
            blocks.append({'type': 'problem_with_solution', **current_problem})
        elif current_problem.get('problem'):
            blocks.append({'type': 'text', 'text': current_problem['problem']})

    return blocks


def _make_endnote(answer_text: str, solution_text: str, number: int, eq_counter: list, graphs: list | None = None) -> str:
    """[정답] 답 + 빈줄 + 해설 형식의 hp:endNote XML 생성."""
    inst_id = 2125617800 + number

    inner_paragraphs = []

    # 미주 번호 자동 삽입 + [정답] 줄
    autonum_xml = (
        f'<hp:run charPrIDRef="0"><hp:ctrl>'
        f'<hp:autoNum num="{number}" numType="ENDNOTE">'
        f'<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>'
        f'</hp:autoNum>'
        f'</hp:ctrl></hp:run>'
    )

    # 정답 있으면 "N) [정답] <답>" / 없으면 "N) [정답] " 까지만 (교사가 직접 채우기 용)
    first_runs = autonum_xml
    first_runs += f'<hp:run charPrIDRef="0"><hp:t> [정답] </hp:t></hp:run>'
    if answer_text:
        first_runs += _line_to_runs(answer_text.strip(), eq_counter, graphs=graphs)
    inner_paragraphs.append(f'<hp:p paraPrIDRef="0" styleIDRef="0">{first_runs}</hp:p>')

    # 해설 각 줄
    for line in solution_text.split('\n'):
        # [GRAPH:N] 단독 라인 → picture paragraph (미주 안에서도 동작)
        gm = _GRAPH_LINE_RE.match(line) if graphs else None
        if gm:
            g_idx = int(gm.group(1))
            if 0 <= g_idx < len(graphs):
                inner_paragraphs.append(_build_picture_paragraph(g_idx, graphs[g_idx]))
                continue
        runs = _line_to_runs(line, eq_counter, graphs=graphs)
        if not runs:
            runs = '<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>'
        inner_paragraphs.append(f'<hp:p paraPrIDRef="0" styleIDRef="0">{runs}</hp:p>')

    inner_body = ''.join(inner_paragraphs)

    return (
        f'<hp:endNote number="{number}" suffixChar="41" instId="{inst_id}">'
        f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
        f'vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" '
        f'textWidth="0" textHeight="0">'
        f'{inner_body}'
        f'</hp:subList>'
        f'</hp:endNote>'
    )


def _make_equation_xml(script: str, eq_id: int) -> str:
    """한글 수식 코드를 hp:equation XML로 변환."""
    width = max(2000, len(script) * 400)
    height = 9100

    return (
        f'<hp:equation id="{eq_id}" zOrder="0" numberingType="EQUATION" '
        f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        f'dropcapstyle="None" version="Equation Version 60" baseLine="0" '
        f'textColor="#000000" baseUnit="1000" lineMode="CHAR" font="HancomEQN">'
        f'<hp:sz width="{width}" widthRelTo="ABSOLUTE" height="{height}" '
        f'heightRelTo="ABSOLUTE" protect="0" />'
        f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
        f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" '
        f'vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0" />'
        f'<hp:outMargin left="56" right="56" top="0" bottom="0" />'
        f'<hp:shapeComment>수식 입니다.</hp:shapeComment>'
        f'<hp:script>{script.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}</hp:script>'
        f'</hp:equation>'
    )


_GRAPH_LINE_RE = re.compile(r'^\s*\[GRAPH:(\d+)\]\s*$')


def _line_to_runs(line: str, eq_counter: list, graphs: list | None = None) -> str:
    """한 줄 텍스트를 hp:run + hp:equation XML로 변환.

    [GRAPH:N] 단독 라인은 paragraph 단계에서 picture paragraph 로 분기되므로
    여기서는 처리하지 않는다 (안전장치만 — 이 함수에 들어왔다면 빈 run 반환).
    """
    if graphs and _GRAPH_LINE_RE.match(line):
        # paragraph 단계에서 처리되어야 하지만, 만약 여기까지 왔다면 빈 run 으로.
        return ''

    templates = _load_box_templates()
    # 박스 sentinel 처리
    if line.startswith('\x00BOX:') and line.endswith('\x00'):
        key = line[5:-1]
        xml = templates.get(key, '')
        if xml:
            return f'<hp:run charPrIDRef="0">{xml}</hp:run>'
        return ''
    # 수식 사이 불필요한 공백 제거: '] [' → ']['
    line = re.sub(r'\]\s+\[', '][', line)

    # `[...]` 수식 매칭에서 `[GRAPH:N]` 형식은 제외 (단독 라인이 아니라
    # 본문 안에 섞여 있는 경우의 안전장치 — 수식 변환 시도 방지)
    formula_pattern = re.compile(r'\[(?!GRAPH:\d+\])([^\]]+)\]')
    parts = []
    last_end = 0

    for match in formula_pattern.finditer(line):
        before = line[last_end:match.start()]
        if before:
            escaped = before.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            parts.append(f'<hp:run charPrIDRef="0"><hp:t>{escaped}</hp:t></hp:run>')

        script = match.group(1)
        eq_id = 1700000000 + eq_counter[0]
        eq_counter[0] += 1
        parts.append(f'<hp:run charPrIDRef="0">{_make_equation_xml(script, eq_id)}</hp:run>')

        last_end = match.end()

    after = line[last_end:]
    if after:
        escaped = after.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        parts.append(f'<hp:run charPrIDRef="0"><hp:t>{escaped}</hp:t></hp:run>')

    return ''.join(parts)


# ──────────────────────────────────────────────
# 최소 HWPX 구조 상수
# ──────────────────────────────────────────────

_META_CONTAINER = '''<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="Contents/content.hpf" media-type="application/hwp+zip"/>
  </rootfiles>
</container>'''

_CONTENT_HPF = '''<?xml version="1.0" encoding="UTF-8"?>
<opf:package xmlns:opf="http://www.idpf.org/2007/opf/">
  <opf:manifest>
    <opf:item id="section0" href="section0.xml" media-type="application/xml"/>
  </opf:manifest>
  <opf:spine>
    <opf:itemref idref="section0"/>
  </opf:spine>
</opf:package>'''

_HEADER_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"
    xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
    xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
    xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" version="1.5" secCnt="1">
    <hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>
    <hh:refList>
        <hh:fontfaces itemCnt="2">
            <hh:fontface lang="HANGUL" fontCnt="1">
                <hh:font id="0" face="맑은 고딕" type="TTF" isEmbedded="0"/>
            </hh:fontface>
            <hh:fontface lang="LATIN" fontCnt="1">
                <hh:font id="0" face="맑은 고딕" type="TTF" isEmbedded="0"/>
            </hh:fontface>
        </hh:fontfaces>
        <hh:borderFills itemCnt="1">
            <hh:borderFill id="1" threeD="0" shadow="0" slash="0" backSlash="0" brokenCellSeparate="0" centerLine="0">
                <hh:fillBrush/>
            </hh:borderFill>
        </hh:borderFills>
        <hh:charProperties itemCnt="1">
            <hh:charPr id="0" height="1000" textColor="#000000" shadeColor="none" useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="1">
                <hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
                <hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>
                <hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
                <hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>
                <hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
            </hh:charPr>
        </hh:charProperties>
        <hh:tabProperties itemCnt="1">
            <hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/>
        </hh:tabProperties>
        <hh:paraProperties itemCnt="1">
            <hh:paraPr id="0" tabPrIDRef="0" condense="0">
                <hh:align horizontal="JUSTIFY" vertical="BASELINE"/>
                <hh:heading type="NONE" idRef="0" level="0"/>
                <hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>
                <hh:autoSpacing eAsianEng="0" eAsianNum="0"/>
            </hh:paraPr>
        </hh:paraProperties>
        <hh:styles itemCnt="1">
            <hh:style id="0" type="PARA" name="바탕글" engName="Normal" paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0"/>
        </hh:styles>
    </hh:refList>
</hh:head>'''

_VERSION_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<ha:HWPDocumentVersion xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"
    major="1" minor="5" micro="0" buildNumber="1"/>'''

_BOX_MARKER_RE = re.compile(r'===(조건박스|보기박스[123]|조건박스끝|보기박스끝)===')

def _substitute_box_markers(text: str) -> str:
    """텍스트의 ===조건박스=== 등 마커를 sentinel 문자열로 교체.
    닫기 마커(끝)는 빈 문자열로 제거."""
    templates = _load_box_templates()
    def replace(m):
        key = m.group(1)
        if key.endswith('끝'):
            return ''  # 닫기 마커는 제거
        if key in templates and templates[key]:
            return f'\x00BOX:{key}\x00'
        return ''
    return _BOX_MARKER_RE.sub(replace, text)


# ──────────────────────────────────────────────
# HWPX 문제 번호 필터 (특정 번호만 남긴 새 HWPX 생성)
# ──────────────────────────────────────────────

def filter_hwpx_by_numbers(source_bytes: bytes, keep_numbers: set) -> bytes:
    """원본 HWPX에서 keep_numbers에 해당하는 문제만 남긴 새 HWPX 생성.

    문제 경계는 `<hp:endNote number="N">`가 달린 paragraph 기준:
    - 문제 N의 paragraph 블록: 이전 endNote paragraph 다음 ~ endNote N paragraph까지
    - 해설: endNote 내부 XML

    Args:
        source_bytes: 원본 HWPX 바이트
        keep_numbers: 유지할 문제 번호 집합 (endNote number 기준)

    Returns:
        필터링된 새 HWPX 바이트
    """
    with zipfile.ZipFile(io.BytesIO(source_bytes), 'r') as src:
        section_xml = src.read('Contents/section0.xml').decode('utf-8')
        other_files = {name: src.read(name) for name in src.namelist()
                       if name != 'Contents/section0.xml'}

    new_section = _filter_section_xml(section_xml, keep_numbers)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as dst:
        # mimetype은 압축 안 됨 (HWPX 규격)
        for name, data in other_files.items():
            if name == 'mimetype':
                dst.writestr(name, data, compress_type=zipfile.ZIP_STORED)
            else:
                dst.writestr(name, data)
        dst.writestr('Contents/section0.xml', new_section)
    buf.seek(0)
    return buf.read()


def _extract_top_level_paragraphs(body: str) -> list[tuple[int, int, str]]:
    """body XML에서 최상위 <hp:p> paragraph들만 추출 (중첩 무시).

    hp:endNote 내부에는 중첩된 <hp:p>가 있기 때문에, 단순 비탐욕 regex는
    첫 번째 내부 </hp:p>에서 잘려서 paragraph 내용이 누락된다.
    이 함수는 depth를 추적하며 최상위 paragraph 경계를 정확히 찾는다.

    Returns:
        [(start_offset, end_offset, xml_str), ...] — body 문자열 기준 오프셋
    """
    results = []
    # 모든 <hp:p ...> 열기와 </hp:p> 닫기 토큰 찾기
    # 자기 닫기 형식 <hp:p ... /> 도 고려 (있을 경우 depth 0 유지)
    token_re = re.compile(r'<hp:p\b[^>]*?(/?)>|</hp:p>', re.DOTALL)

    depth = 0
    start = -1
    for m in token_re.finditer(body):
        tok = m.group(0)
        if tok.startswith('</'):
            # 닫는 태그
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    results.append((start, m.end(), body[start:m.end()]))
                    start = -1
        else:
            # 여는 태그 — 자기 닫기 체크
            is_self_closing = m.group(1) == '/'
            if is_self_closing:
                if depth == 0:
                    results.append((m.start(), m.end(), body[m.start():m.end()]))
            else:
                if depth == 0:
                    start = m.start()
                depth += 1
    return results


def _filter_section_xml(section_xml: str, keep_numbers: set) -> str:
    """section0.xml에서 문제 번호 필터링.

    실제 HWPX 구조상 endNote는 문제의 **첫 단락** (문제 번호/본문)에 삽입되어
    있고, 선지(①②③④⑤)는 그 뒤 단락에 나온다. 따라서 문제 N의 단락 블록은
    "endNote=N 단락부터 다음 endNote 단락 직전까지"로 정의해야 한다.

    전략:
    1. <hs:sec> 루트 래퍼를 찾아서 전/후 분리
    2. depth-tracking tokenizer로 최상위 paragraph들 파싱
    3. endNote 번호가 있는 단락의 인덱스 목록 수집
    4. keep_numbers에 해당하는 각 endNote에 대해, 그 단락부터 다음 endNote
       단락 직전까지의 단락들을 유지
    5. 첫 endNote 이전의 단락(문서 헤더) — 유지할 문제가 하나라도 있으면 보존
    """
    # <hs:sec> 또는 <hp:sec> 등 루트 sec 태그 찾기
    sec_match = re.search(r'(<[a-z]+:sec\b[^>]*>)(.*)(</[a-z]+:sec>)',
                         section_xml, re.DOTALL)
    if not sec_match:
        return section_xml

    prefix = section_xml[:sec_match.start()] + sec_match.group(1)
    body = sec_match.group(2)
    suffix = sec_match.group(3) + section_xml[sec_match.end():]

    p_iter = _extract_top_level_paragraphs(body)
    if not p_iter:
        return section_xml

    en_num_re = re.compile(r'<hp:endNote\s+number="(\d+)"')

    # 각 paragraph의 endNote 번호 수집: [(paragraph_index, number), ...]
    en_positions = []
    for i, (_, _, p_xml) in enumerate(p_iter):
        m = en_num_re.search(p_xml)
        if m:
            en_positions.append((i, int(m.group(1))))

    # keep_numbers에 해당하는 블록 범위 계산 — [start_idx, end_idx_exclusive)
    keep_ranges = []
    for k, (p_idx, num) in enumerate(en_positions):
        if num in keep_numbers:
            next_p_idx = en_positions[k + 1][0] if k + 1 < len(en_positions) else len(p_iter)
            keep_ranges.append((p_idx, next_p_idx))

    if not keep_ranges:
        # 유지할 블록이 없으면 본문 전부 제거 (헤더도 함께)
        return prefix + suffix

    first_p_start = p_iter[0][0]
    header_xml = body[:first_p_start]

    # 문서 헤더 단락 — 첫 endNote 이전의 단락들. 유지할 게 있으면 보존.
    first_en_p_idx = en_positions[0][0] if en_positions else 0
    pre_header_paragraphs = [p_iter[j][2] for j in range(0, first_en_p_idx)]

    kept_parts = list(pre_header_paragraphs)
    for (s, e) in keep_ranges:
        for j in range(s, e):
            kept_parts.append(p_iter[j][2])

    new_body = header_xml + ''.join(kept_parts)
    return prefix + new_body + suffix


def _extract_first_problem_paragraphs(section_xml: str) -> str | None:
    """section0.xml에서 첫 endNote 블록(= 첫 문제)의 단락 XML을 이어붙여 반환.

    블록 정의: 첫 endNote=N 단락 ~ 두 번째 endNote 단락 직전. endNote가 없으면
    전체 top-level 단락. 실패 시 None.
    """
    sec_match = re.search(r'(<[a-z]+:sec\b[^>]*>)(.*)(</[a-z]+:sec>)',
                         section_xml, re.DOTALL)
    if not sec_match:
        return None
    body = sec_match.group(2)
    paragraphs = _extract_top_level_paragraphs(body)
    if not paragraphs:
        return None

    en_num_re = re.compile(r'<hp:endNote\s+number="(\d+)"')
    en_indices = [i for i, (_, _, p) in enumerate(paragraphs) if en_num_re.search(p)]

    if not en_indices:
        return ''.join(p[2] for p in paragraphs)

    start = en_indices[0]
    end = en_indices[1] if len(en_indices) > 1 else len(paragraphs)
    return ''.join(paragraphs[j][2] for j in range(start, end))


def _extract_all_problem_paragraphs(section_xml: str) -> str | None:
    """section0.xml 본문의 모든 top-level 단락 XML을 이어붙여 반환.

    (헤더 파라그래프 포함) 실패 시 None.
    """
    sec_match = re.search(r'(<[a-z]+:sec\b[^>]*>)(.*)(</[a-z]+:sec>)',
                         section_xml, re.DOTALL)
    if not sec_match:
        return None
    paragraphs = _extract_top_level_paragraphs(sec_match.group(2))
    if not paragraphs:
        return None
    return ''.join(p[2] for p in paragraphs)


def append_hwpx_problems(target_bytes: bytes, source_bytes: bytes) -> bytes:
    """source HWPX의 모든 문제 단락을 target 본문 뒤에 append한 새 HWPX 반환.

    양쪽 모두 filter_hwpx_by_numbers 결과(문제만 남긴 상태)를 기대.
    endNote number 충돌 시 source 단락의 번호를 target 너머로 shift.
    BinData는 병합하지 않음 — source 쪽 이미지는 깨질 수 있음.
    """
    with zipfile.ZipFile(io.BytesIO(source_bytes), 'r') as src:
        src_section = src.read('Contents/section0.xml').decode('utf-8')
    with zipfile.ZipFile(io.BytesIO(target_bytes), 'r') as tgt:
        tgt_section = tgt.read('Contents/section0.xml').decode('utf-8')
        others = {n: tgt.read(n) for n in tgt.namelist()
                  if n != 'Contents/section0.xml'}

    src_all = _extract_all_problem_paragraphs(src_section)
    if not src_all:
        return target_bytes

    en_num_re = re.compile(r'<hp:endNote\s+number="(\d+)"')
    tgt_nums = {int(m.group(1)) for m in en_num_re.finditer(tgt_section)}
    src_nums = {int(m.group(1)) for m in en_num_re.finditer(src_all)}

    if src_nums & tgt_nums:
        shift = max(tgt_nums | src_nums) + 1
        src_all = en_num_re.sub(
            lambda m: f'<hp:endNote number="{shift + int(m.group(1))}"',
            src_all,
        )

    sec_match = re.search(r'(<[a-z]+:sec\b[^>]*>)(.*)(</[a-z]+:sec>)',
                         tgt_section, re.DOTALL)
    if not sec_match:
        return target_bytes

    prefix = tgt_section[:sec_match.start()] + sec_match.group(1)
    body = sec_match.group(2)
    suffix = sec_match.group(3) + tgt_section[sec_match.end():]
    new_section = prefix + body + src_all + suffix

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as dst:
        for name, data in others.items():
            if name == 'mimetype':
                dst.writestr(name, data, compress_type=zipfile.ZIP_STORED)
            else:
                dst.writestr(name, data)
        dst.writestr('Contents/section0.xml', new_section)
    return buf.getvalue()


def merge_reference_problem(target_bytes: bytes, source_bytes: bytes) -> bytes:
    """source(기준문항 HWPX)의 첫 문제 단락들을 target 본문 맨 앞에 삽입한 HWPX 반환.

    - target_bytes는 이미 filter_hwpx_by_numbers 결과(유사문항만 남긴 상태)를 기대.
    - source의 첫 endNote 블록만 사용 (여러 문제가 있으면 첫 번째만).
    - endNote number 충돌 시 source 단락의 번호를 target 최대 번호 너머로 shift.
    - BinData는 병합하지 않음 — 원본 쪽 이미지 참조는 깨질 수 있음 (수식/텍스트는 대부분 보존).
    """
    with zipfile.ZipFile(io.BytesIO(source_bytes), 'r') as src:
        src_section = src.read('Contents/section0.xml').decode('utf-8')

    with zipfile.ZipFile(io.BytesIO(target_bytes), 'r') as tgt:
        tgt_section = tgt.read('Contents/section0.xml').decode('utf-8')
        others = {n: tgt.read(n) for n in tgt.namelist()
                  if n != 'Contents/section0.xml'}

    src_first = _extract_first_problem_paragraphs(src_section)
    if not src_first:
        return target_bytes  # 기준문항 추출 실패 → target 그대로

    en_num_re = re.compile(r'<hp:endNote\s+number="(\d+)"')
    tgt_nums = {int(m.group(1)) for m in en_num_re.finditer(tgt_section)}
    src_nums = {int(m.group(1)) for m in en_num_re.finditer(src_first)}

    if src_nums & tgt_nums:
        shift = max(tgt_nums | src_nums) + 1
        src_first = en_num_re.sub(
            lambda m: f'<hp:endNote number="{shift + int(m.group(1))}"',
            src_first,
        )

    sec_match = re.search(r'(<[a-z]+:sec\b[^>]*>)(.*)(</[a-z]+:sec>)',
                         tgt_section, re.DOTALL)
    if not sec_match:
        return target_bytes

    prefix = tgt_section[:sec_match.start()] + sec_match.group(1)
    body = sec_match.group(2)
    suffix = sec_match.group(3) + tgt_section[sec_match.end():]

    first_p_match = re.search(r'<hp:p\b', body)
    if first_p_match:
        new_body = body[:first_p_match.start()] + src_first + body[first_p_match.start():]
    else:
        new_body = src_first + body

    new_section = prefix + new_body + suffix

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as dst:
        for name, data in others.items():
            if name == 'mimetype':
                dst.writestr(name, data, compress_type=zipfile.ZIP_STORED)
            else:
                dst.writestr(name, data)
        dst.writestr('Contents/section0.xml', new_section)
    return buf.getvalue()
