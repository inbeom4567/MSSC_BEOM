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
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data"


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
            t = match.group(1).strip()
            if t and not t.startswith('<'):
                parts.append(t)
        elif match.group(2) is not None:
            s = match.group(2).strip()
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

    for line_idx, en_num in sorted(endnote_at_line.items()):
        if problem_count > 1:
            result.append(f'\n-{en_num}번-')
        result.append('-문제-')

        # 이 미주가 달린 줄부터 다음 미주 줄 전까지가 문제 텍스트
        next_endnote_lines = [li for li in endnote_at_line if li > line_idx]
        end_line = min(next_endnote_lines) if next_endnote_lines else len(body_lines)

        problem_lines = [body_lines[i] for i in range(line_idx, end_line) if body_lines[i].strip()]
        result.append('\n'.join(problem_lines))

        result.append('\n-해설-')
        result.append(endnote_map.get(en_num, ''))

    return '\n'.join(result)


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
        if content:
            problems.append({"number": number, "text": content})

    return problems


# ──────────────────────────────────────────────
# HWPX 출력 (미주 형식)
# ──────────────────────────────────────────────

def create_hwpx(text: str, template_bytes: bytes = None) -> bytes:
    """텍스트를 HWPX 파일로 변환. 수식은 equation 객체, 해설은 미주로."""
    if template_bytes:
        return _create_from_template(text, template_bytes)
    return _create_minimal(text)


def _create_from_template(text: str, template_bytes: bytes) -> bytes:
    """원본 HWPX를 템플릿으로 사용하여 section0.xml만 교체."""
    buf = io.BytesIO()

    with zipfile.ZipFile(io.BytesIO(template_bytes), 'r') as src:
        original_section = src.read('Contents/section0.xml').decode('utf-8')
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as dst:
            for item in src.namelist():
                if item == 'Contents/section0.xml':
                    section_xml = _build_section_xml(text, original_section)
                    dst.writestr(item, section_xml)
                elif item == 'Preview/PrvText.txt':
                    dst.writestr(item, text[:500].encode('utf-8'))
                else:
                    dst.writestr(item, src.read(item))

    buf.seek(0)
    return buf.read()


def _create_minimal(text: str) -> bytes:
    """최소 HWPX 구조로 생성."""
    template_path = TEMPLATE_DIR / "template.hwpx"
    if template_path.exists():
        with open(template_path, 'rb') as f:
            return _create_from_template(text, f.read())

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype', 'application/hwp+zip')
        z.writestr('META-INF/container.xml', _META_CONTAINER)
        z.writestr('Contents/header.xml', _HEADER_XML)
        z.writestr('Contents/content.hpf', _CONTENT_HPF)
        z.writestr('Contents/section0.xml', _build_section_xml(text, None))
        z.writestr('version.xml', _VERSION_XML)
    buf.seek(0)
    return buf.read()


def _build_section_xml(text: str, original_section: str = None) -> str:
    """텍스트를 section XML로 변환. -문제-/-해설- → 미주 구조."""

    # 원본에서 secPr, 네임스페이스 추출
    sec_pr = ''
    ns_tag = '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">'

    if original_section:
        sec_pr_match = re.search(r'(<hp:secPr.*?</hp:secPr>)', original_section, re.DOTALL)
        sec_pr = sec_pr_match.group(1) if sec_pr_match else ''
        ns_match = re.search(r'(<hs:sec[^>]+>)', original_section)
        if ns_match:
            ns_tag = ns_match.group(1)

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
                runs = _line_to_runs(line, eq_counter)

                if i == 0:
                    endnote_xml = _make_endnote(answer_text, solution_text, en_counter[0], eq_counter)
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
                runs = _line_to_runs(line, eq_counter)
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


def _make_endnote(answer_text: str, solution_text: str, number: int, eq_counter: list) -> str:
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

    if answer_text:
        answer_runs = autonum_xml
        answer_runs += f'<hp:run charPrIDRef="0"><hp:t> [정답] </hp:t></hp:run>'
        answer_runs += _line_to_runs(answer_text.strip(), eq_counter)
        inner_paragraphs.append(f'<hp:p paraPrIDRef="0" styleIDRef="0">{answer_runs}</hp:p>')
    else:
        inner_paragraphs.append(f'<hp:p paraPrIDRef="0" styleIDRef="0">{autonum_xml}</hp:p>')
        # 빈 줄
        inner_paragraphs.append('<hp:p paraPrIDRef="0" styleIDRef="0"><hp:run charPrIDRef="0"><hp:t></hp:t></hp:run></hp:p>')

    # 해설 각 줄
    for line in solution_text.split('\n'):
        runs = _line_to_runs(line, eq_counter)
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
        f'<hp:script>{script}</hp:script>'
        f'</hp:equation>'
    )


def _line_to_runs(line: str, eq_counter: list) -> str:
    """한 줄 텍스트를 hp:run + hp:equation XML로 변환."""
    # 수식 사이 불필요한 공백 제거: '] [' → ']['
    line = re.sub(r'\]\s+\[', '][', line)

    formula_pattern = re.compile(r'\[([^\]]+)\]')
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
