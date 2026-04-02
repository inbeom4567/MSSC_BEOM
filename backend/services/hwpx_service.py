"""HWPX 파일 읽기/쓰기 서비스.

HWPX는 ZIP 파일 안에 XML(section0.xml)로 본문이 저장됨.
수식은 <hp:script> 태그에 한글 수식 코드로 저장.
텍스트는 <hp:t> 태그에 저장.
"""

import zipfile
import io
import re
import logging
from xml.etree import ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

# 템플릿 HWPX 경로 (빈 문서 기반)
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data"


def read_hwpx(file_bytes: bytes) -> str:
    """HWPX 파일에서 텍스트+수식을 추출하여 평문 텍스트로 반환.

    수식은 [한글수식코드] 형태로 변환.
    """
    with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as z:
        section_files = [n for n in z.namelist() if n.startswith('Contents/section') and n.endswith('.xml')]
        if not section_files:
            raise ValueError("HWPX 파일에서 section XML을 찾을 수 없습니다.")

        all_text = []
        for section_file in sorted(section_files):
            xml_content = z.read(section_file).decode('utf-8')
            text = _parse_section_xml(xml_content)
            all_text.append(text)

        return '\n'.join(all_text).strip()


def _parse_section_xml(xml_content: str) -> str:
    """section XML에서 텍스트+수식을 추출. 미주(endNote)가 있으면 문제/해설을 자동 분리."""

    # 1단계: 미주(endNote) 추출 + 본문에서 제거
    endnote_map = {}
    endnote_pattern = re.compile(r'<hp:endNote\s+number="(\d+)"[^>]*>(.*?)</hp:endNote>', re.DOTALL)

    for match in endnote_pattern.finditer(xml_content):
        num = match.group(1)
        endnote_xml = match.group(2)
        texts = re.findall(r'<hp:t>(.*?)</hp:t>', endnote_xml)
        scripts = re.findall(r'<hp:script>(.*?)</hp:script>', endnote_xml)

        # 텍스트와 수식을 순서대로 조합 (정규식으로 순서 유지)
        parts = []
        for item in re.finditer(r'<hp:t>(.*?)</hp:t>|<hp:script>(.*?)</hp:script>', endnote_xml):
            if item.group(1) is not None:
                t = item.group(1).strip()
                if t and '<' not in t:  # HTML 태그 제외
                    parts.append(t)
            elif item.group(2) is not None:
                s = item.group(2).strip()
                if s:
                    parts.append(f'[{s}]')
        endnote_map[num] = ' '.join(parts)

    # 미주가 제거된 본문 XML
    body_xml = endnote_pattern.sub('', xml_content)

    has_endnotes = len(endnote_map) > 0

    # 2단계: 본문 텍스트 추출
    root = _safe_parse(body_xml, xml_content)

    body_lines = []
    for p in root.iter('{http://www.hancom.co.kr/hwpml/2011/paragraph}p'):
        parts = []
        for elem in p.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag == 't' and elem.text:
                parts.append(elem.text)
            elif tag == 'script' and elem.text:
                formula = elem.text.strip()
                if formula:
                    parts.append(f'[{formula}]')
        line = ''.join(parts).strip()
        body_lines.append(line)

    if not has_endnotes:
        return '\n'.join(body_lines)

    # 3단계: 미주 형식 → -문제- / -해설- 구조로 변환
    # 본문에서 비어있지 않은 줄 = 문제 텍스트
    problem_text = '\n'.join(line for line in body_lines if line.strip())

    result_parts = []
    if len(endnote_map) == 1:
        # 단일 문제
        result_parts.append('-문제-')
        result_parts.append(problem_text)
        result_parts.append('\n-해설-')
        result_parts.append(list(endnote_map.values())[0])
    else:
        # 여러 문제 (미주 번호별)
        # 본문을 미주 번호 기준으로 분리하기 어려우므로 전체를 하나로
        for num, solution in sorted(endnote_map.items(), key=lambda x: int(x[0])):
            result_parts.append(f'\n-{num}번-')
            result_parts.append('-문제-')
            result_parts.append(problem_text)  # TODO: 문제별 분리 개선
            result_parts.append('\n-해설-')
            result_parts.append(solution)

    return '\n'.join(result_parts)


def _safe_parse(modified_xml: str, original_xml: str):
    """수정된 XML 파싱 시도, 실패하면 원본으로 파싱."""
    try:
        return ET.fromstring(modified_xml)
    except ET.ParseError:
        return ET.fromstring(original_xml)


def split_problems(text: str) -> list[dict]:
    """텍스트에서 -N번- 구분자로 여러 문제를 분리.

    Returns: [{"number": 1, "text": "-문제-\n...\n-해설-\n..."}, ...]
    구분자가 없으면 전체를 1개 문제로 반환.
    """
    # -1번-, -2번- 등으로 분리
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


def create_hwpx(text: str, template_bytes: bytes = None) -> bytes:
    """텍스트를 HWPX 파일로 변환.

    template_bytes가 주어지면 원본 HWPX 구조를 유지하면서 section0.xml만 교체.
    없으면 기본 템플릿 사용.
    """
    if template_bytes:
        return _create_from_template(text, template_bytes)
    return _create_from_default_template(text)


def _create_from_template(text: str, template_bytes: bytes) -> bytes:
    """원본 HWPX 파일을 기반으로 section0.xml만 교체."""
    buf = io.BytesIO()

    with zipfile.ZipFile(io.BytesIO(template_bytes), 'r') as src:
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as dst:
            for item in src.namelist():
                if item == 'Contents/section0.xml':
                    # section0.xml만 새로 생성
                    section_xml = _text_to_section_xml(text, src.read(item).decode('utf-8'))
                    dst.writestr(item, section_xml)
                elif item == 'Preview/PrvText.txt':
                    # 미리보기 텍스트 교체
                    dst.writestr(item, text[:500].encode('utf-8'))
                else:
                    dst.writestr(item, src.read(item))

    buf.seek(0)
    return buf.read()


def _create_from_default_template(text: str) -> bytes:
    """기본 템플릿으로 HWPX 생성."""
    # data/template.hwpx가 있으면 사용
    template_path = TEMPLATE_DIR / "template.hwpx"
    if template_path.exists():
        with open(template_path, 'rb') as f:
            return _create_from_template(text, f.read())

    # 템플릿 없으면 최소 구조 생성
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype', 'application/hwp+zip')
        z.writestr('META-INF/container.xml', _META_CONTAINER)
        z.writestr('Contents/header.xml', _HEADER_XML)
        z.writestr('Contents/content.hpf', _CONTENT_HPF)
        z.writestr('Contents/section0.xml', _text_to_simple_section(text))
        z.writestr('version.xml', _VERSION_XML)
    buf.seek(0)
    return buf.read()


def _make_equation_xml(script: str, eq_id: int) -> str:
    """한글 수식 코드를 hp:equation XML로 변환."""
    # 수식 길이에 따라 대략적인 너비 계산 (글자당 약 400 단위)
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
    """한 줄의 텍스트를 hp:run + hp:equation XML로 변환.

    [수식코드] 패턴을 찾아서 hp:equation으로 변환.
    """
    formula_pattern = re.compile(r'\[([^\]]+)\]')
    parts = []
    last_end = 0

    for match in formula_pattern.finditer(line):
        # 수식 앞 텍스트
        before = line[last_end:match.start()]
        if before:
            escaped = before.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            parts.append(f'<hp:run charPrIDRef="0"><hp:t>{escaped}</hp:t></hp:run>')

        # 수식 객체
        script = match.group(1)
        eq_id = 1700000000 + eq_counter[0]
        eq_counter[0] += 1
        parts.append(f'<hp:run charPrIDRef="0">{_make_equation_xml(script, eq_id)}</hp:run>')

        last_end = match.end()

    # 남은 텍스트
    after = line[last_end:]
    if after:
        escaped = after.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        parts.append(f'<hp:run charPrIDRef="0"><hp:t>{escaped}</hp:t></hp:run>')

    return ''.join(parts)


def _text_to_section_xml(text: str, original_section: str) -> str:
    """원본 section XML 구조를 유지하면서 본문 내용만 교체. 수식을 equation 객체로 변환."""
    # 원본 XML에서 secPr (섹션 속성) 부분 추출
    sec_pr_match = re.search(r'(<hp:secPr.*?</hp:secPr>)', original_section, re.DOTALL)
    sec_pr = sec_pr_match.group(1) if sec_pr_match else ''

    # 네임스페이스 추출
    ns_match = re.search(r'(<hs:sec[^>]+>)', original_section)
    ns_tag = ns_match.group(1) if ns_match else '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">'

    eq_counter = [1]  # 수식 ID 카운터 (mutable로 전달)

    paragraphs = []
    first = True
    for line in text.split('\n'):
        runs = _line_to_runs(line, eq_counter)

        if first and sec_pr:
            # 첫 paragraph에 secPr 삽입
            runs = f'<hp:run charPrIDRef="0">{sec_pr}</hp:run>' + runs
            first = False

        if not runs:
            runs = '<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>'

        paragraphs.append(f'<hp:p paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{runs}</hp:p>')

    body = '\n'.join(paragraphs)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{ns_tag}\n{body}\n</hs:sec>'


def _text_to_simple_section(text: str) -> str:
    """간단한 section XML 생성 (수식 객체 포함)."""
    eq_counter = [1]
    paragraphs = []
    for line in text.split('\n'):
        runs = _line_to_runs(line, eq_counter)
        if not runs:
            runs = '<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>'
        paragraphs.append(
            f'<hp:p paraPrIDRef="0" styleIDRef="0">'
            f'{runs}'
            f'</hp:p>'
        )
    body = '\n'.join(paragraphs)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
    xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">
{body}
</hs:sec>'''


# 최소 HWPX 구조
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
