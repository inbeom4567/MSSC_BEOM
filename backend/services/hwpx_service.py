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

logger = logging.getLogger(__name__)

# 네임스페이스
NS = {
    'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
    'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
    'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
}


def read_hwpx(file_bytes: bytes) -> str:
    """HWPX 파일에서 텍스트+수식을 추출하여 평문 텍스트로 반환.

    수식은 [한글수식코드] 형태로 변환.
    """
    with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as z:
        # section0.xml 읽기
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
    # XML 파싱
    root = ET.fromstring(xml_content)

    lines = []
    # 모든 paragraph (hp:p) 순회
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
            # 수식: [한글수식코드] 형태로
            formula = elem.text.strip()
            if formula:
                parts.append(f'[{formula}]')


def create_hwpx(text: str) -> bytes:
    """텍스트를 간단한 HWPX 파일로 변환.

    수식은 [한글수식코드] 텍스트 그대로 포함 (수식 객체 아님).
    """
    # 최소한의 HWPX 구조 생성
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        # mimetype (압축 없이)
        z.writestr('mimetype', 'application/hwp+zip')

        # META-INF/container.xml
        z.writestr('META-INF/container.xml', _META_CONTAINER)

        # Contents/header.xml (최소)
        z.writestr('Contents/header.xml', _HEADER_XML)

        # Contents/content.hpf
        z.writestr('Contents/content.hpf', _CONTENT_HPF)

        # Contents/section0.xml (본문)
        section_xml = _text_to_section_xml(text)
        z.writestr('Contents/section0.xml', section_xml)

        # version.xml
        z.writestr('version.xml', _VERSION_XML)

    buf.seek(0)
    return buf.read()


def _text_to_section_xml(text: str) -> str:
    """평문 텍스트를 section0.xml 형식으로 변환."""
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
    xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
    xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core">
{body}
</hs:sec>'''


# 최소 HWPX 구조용 상수
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

_HEADER_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">
</hh:head>'''

_VERSION_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<ha:HWPDocumentVersion xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"
    major="1" minor="0" micro="0" buildNumber="1"/>'''
