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
    """section XML에서 텍스트+수식을 순서대로 추출."""
    root = ET.fromstring(xml_content)
    lines = []
    for p in root.iter('{http://www.hancom.co.kr/hwpml/2011/paragraph}p'):
        line_parts = []
        _extract_paragraph(p, line_parts)
        line = ''.join(line_parts).strip()
        lines.append(line)
    return '\n'.join(lines)


def _extract_paragraph(p_elem, parts: list):
    """paragraph 요소에서 텍스트와 수식을 순서대로 추출."""
    for elem in p_elem.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag == 't' and elem.text:
            parts.append(elem.text)
        elif tag == 'script' and elem.text:
            formula = elem.text.strip()
            if formula:
                parts.append(f'[{formula}]')


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


def _text_to_section_xml(text: str, original_section: str) -> str:
    """원본 section XML 구조를 유지하면서 본문 내용만 교체."""
    # 원본 XML에서 secPr (섹션 속성) 부분 추출
    sec_pr_match = re.search(r'(<hp:secPr.*?</hp:secPr>)', original_section, re.DOTALL)
    sec_pr = sec_pr_match.group(1) if sec_pr_match else ''

    # 네임스페이스 추출
    ns_match = re.search(r'(<hs:sec[^>]+>)', original_section)
    ns_tag = ns_match.group(1) if ns_match else '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">'

    # 본문 paragraph 생성
    paragraphs = []
    first = True
    for line in text.split('\n'):
        escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

        p_content = ''
        if first and sec_pr:
            p_content = f'<hp:run charPrIDRef="0">{sec_pr}<hp:t>{escaped}</hp:t></hp:run>'
            first = False
        else:
            p_content = f'<hp:run charPrIDRef="0"><hp:t>{escaped}</hp:t></hp:run>'

        paragraphs.append(f'<hp:p paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{p_content}</hp:p>')

    body = '\n'.join(paragraphs)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{ns_tag}\n{body}\n</hs:sec>'


def _text_to_simple_section(text: str) -> str:
    """간단한 section XML 생성."""
    paragraphs = []
    for line in text.split('\n'):
        escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        paragraphs.append(
            f'<hp:p paraPrIDRef="0" styleIDRef="0">'
            f'<hp:run charPrIDRef="0"><hp:t>{escaped}</hp:t></hp:run>'
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
