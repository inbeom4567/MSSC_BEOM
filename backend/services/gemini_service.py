import os
import json
import base64
import logging
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_ANALYZE = "gemini-2.5-flash"
GEMINI_MODEL_IMAGE = "gemini-2.5-flash-image"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _call_gemini(model: str, payload: dict, timeout: int = 300) -> dict:
    """Gemini API 호출 (동기)"""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. backend/.env 파일을 확인하세요.")

    url = f"{BASE_URL}/{model}:generateContent?key={GEMINI_API_KEY}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def analyze_image(image_base64: str, media_type: str, prompt: str) -> str:
    """Gemini로 이미지를 분석하여 텍스트 결과 반환.

    용도:
    - 원본 문제의 그래프/그림 분석
    - 손필기 이미지에서 수식/텍스트 추출
    """
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": image_base64}},
                {"text": prompt},
            ]
        }]
    }

    result = _call_gemini(GEMINI_MODEL_ANALYZE, payload)
    parts = result["candidates"][0]["content"]["parts"]

    texts = [p["text"] for p in parts if "text" in p]
    return "\n".join(texts)


def analyze_graph(image_base64: str, media_type: str) -> dict:
    """원본 문제 이미지에서 그래프 정보를 분석하여 구조화된 데이터로 반환.

    Returns:
        dict: {
            "has_graph": bool,
            "graph_type": str,  # "function", "geometry", "mixed", "none"
            "functions": list,  # 감지된 함수식 리스트
            "points": list,     # 주요 좌표점
            "description": str, # 그래프에 대한 설명
        }
    """
    prompt = """이 수학 문제 이미지를 분석해주세요. 반드시 아래 JSON 형식으로만 응답하세요.

{
  "has_graph": true/false,
  "graph_type": "function" 또는 "geometry" 또는 "mixed" 또는 "none",
  "functions": ["y = x^2 - 4x + 3", ...],
  "points": [{"label": "A", "x": 1, "y": 0}, ...],
  "x_range": [-5, 5],
  "y_range": [-3, 5],
  "description": "이차함수 y=x²-4x+3의 그래프. 꼭짓점 (2,-1), x절편 (1,0), (3,0)",
  "style_notes": "검은 실선, 점선 보조선, 음영 영역 있음"
}

주의:
- 함수식은 y = ... 형태로 정확하게 추출
- 좌표는 그래프에서 읽을 수 있는 만큼 정확하게
- 기하 도형이면 꼭짓점 좌표와 도형 종류를 설명
- JSON만 출력, 다른 텍스트 없이"""

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": image_base64}},
                {"text": prompt},
            ]
        }]
    }

    result = _call_gemini(GEMINI_MODEL_ANALYZE, payload)
    text = result["candidates"][0]["content"]["parts"][0]["text"]

    # JSON 파싱 시도
    try:
        # ```json ... ``` 블록 추출
        json_match = text
        if "```" in text:
            import re
            m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            if m:
                json_match = m.group(1)
        return json.loads(json_match)
    except json.JSONDecodeError:
        logger.warning(f"Gemini 그래프 분석 JSON 파싱 실패: {text[:200]}")
        return {
            "has_graph": False,
            "graph_type": "none",
            "functions": [],
            "points": [],
            "description": text,
        }


def recognize_handwriting(image_base64: str, media_type: str) -> dict:
    """손필기 이미지에서 수식과 텍스트를 인식.

    Returns:
        dict: {
            "text": str,           # 인식된 전체 텍스트
            "equations": list,     # 추출된 수식 리스트
            "confidence": str,     # "high", "medium", "low"
        }
    """
    prompt = """이 손글씨/손필기 수학 이미지를 분석해주세요. 반드시 아래 JSON 형식으로만 응답하세요.

{
  "text": "인식된 전체 내용을 텍스트로",
  "equations": ["y = 2x + 1", "x^2 + y^2 = 4"],
  "confidence": "high" 또는 "medium" 또는 "low"
}

주의:
- 수식은 가능한 정확하게 인식
- 읽기 어려운 부분은 [?]로 표시
- JSON만 출력"""

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": image_base64}},
                {"text": prompt},
            ]
        }]
    }

    result = _call_gemini(GEMINI_MODEL_ANALYZE, payload)
    text = result["candidates"][0]["content"]["parts"][0]["text"]

    try:
        json_match = text
        if "```" in text:
            import re
            m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            if m:
                json_match = m.group(1)
        return json.loads(json_match)
    except json.JSONDecodeError:
        logger.warning(f"손필기 인식 JSON 파싱 실패: {text[:200]}")
        return {
            "text": text,
            "equations": [],
            "confidence": "low",
        }


def ocr_scan_general(image_base64: str, media_type: str, page_range: str = "") -> dict:
    """일반 스캔: 수학 문제/해설 텍스트 추출.

    page_range: 예) "1-3", "2", "" (전체)

    Returns:
        dict: {
            "problem": str,        # 문제 텍스트 (수식은 LaTeX로)
            "solution": str|None,  # 해설 텍스트 (없으면 null)
            "has_solution": bool,
            "problem_number": str, # 문제 번호 (있으면)
        }
    """
    page_instruction = ""
    if page_range:
        page_instruction = f"\n\n※ {page_range}페이지의 내용만 추출하세요. 다른 페이지는 무시하세요."

    prompt = f"""이 수학 문제 스캔 이미지(또는 PDF)를 분석하세요. 반드시 아래 JSON 형식으로만 응답하세요.{page_instruction}

{{
  "problem": "문제 전체 텍스트. 수식은 $ $ 사이에 LaTeX로 표기. 예: $x^2 + 2x - 3 = 0$. 여러 문제가 있으면 번호와 함께 전부 포함.",
  "solution": "해설 전체 텍스트 (없으면 null)",
  "has_solution": true 또는 false,
  "problem_number": "첫 번째 문제 번호 (없으면 빈 문자열)"
}}

주의:
- 문제와 해설을 구분하여 추출
- 수식, 분수, 적분 기호 등 모든 수학 기호를 LaTeX로 정확히 표기
- 여러 문제가 있으면 problem 필드에 번호와 함께 모두 포함
- JSON만 출력"""

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": image_base64}},
                {"text": prompt},
            ]
        }]
    }

    result = _call_gemini(GEMINI_MODEL_ANALYZE, payload)
    text = result["candidates"][0]["content"]["parts"][0]["text"]

    try:
        json_match = text
        if "```" in text:
            import re
            m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            if m:
                json_match = m.group(1)
        return json.loads(json_match)
    except json.JSONDecodeError:
        logger.warning(f"일반 스캔 OCR JSON 파싱 실패: {text[:200]}")
        return {
            "problem": text,
            "solution": None,
            "has_solution": False,
            "problem_number": "",
        }


def ocr_scan_student_paper(image_base64: str, media_type: str) -> dict:
    """학생 시험지 스캔: 인쇄 텍스트(문제)와 손필기(학생 답안)를 구분하여 추출.

    Returns:
        dict: {
            "printed": str,             # 인쇄된 문제 텍스트 (LaTeX 수식)
            "handwriting": str,         # 손필기 내용 (학생 답안/풀이)
            "has_solution": bool,       # 인쇄된 해설 포함 여부
            "solution": str|None,       # 인쇄된 해설 (있으면)
            "student_answer": str,      # 학생이 쓴 최종 답 (추출 가능하면)
        }
    """
    prompt = """학생 시험지 이미지입니다. 인쇄된 텍스트와 손글씨를 반드시 구분하여 추출하세요. 아래 JSON 형식으로만 응답하세요.

{
  "printed": "인쇄된 문제 텍스트 전체. 수식은 $ $ 사이에 LaTeX로 표기",
  "handwriting": "학생이 손으로 쓴 내용 전체 (풀이 과정, 메모 등). 수식은 LaTeX로",
  "has_solution": false,
  "solution": null,
  "student_answer": "학생이 쓴 최종 답 (알 수 없으면 빈 문자열)"
}

구분 기준:
- 인쇄된 텍스트: 균일한 폰트, 깔끔한 선
- 손글씨: 불규칙한 획, 연필/펜 자국, 지운 흔적
- 학생이 빈칸에 쓴 내용은 handwriting으로 분류
- JSON만 출력"""

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": image_base64}},
                {"text": prompt},
            ]
        }]
    }

    result = _call_gemini(GEMINI_MODEL_ANALYZE, payload)
    text = result["candidates"][0]["content"]["parts"][0]["text"]

    try:
        json_match = text
        if "```" in text:
            import re
            m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            if m:
                json_match = m.group(1)
        return json.loads(json_match)
    except json.JSONDecodeError:
        logger.warning(f"학생 시험지 OCR JSON 파싱 실패: {text[:200]}")
        return {
            "printed": text,
            "handwriting": "",
            "has_solution": False,
            "solution": None,
            "student_answer": "",
        }


def detect_problem_bboxes(image_base64: str, media_type: str) -> list:
    """수학 문제지 이미지에서 각 문제 영역의 bounding box를 비율 좌표로 반환.

    Returns:
        list: [{"x": 0.05, "y": 0.03, "w": 0.90, "h": 0.18}, ...]
              좌표는 이미지 크기 대비 비율값(0.0 ~ 1.0)
              x, y는 박스 왼쪽 상단 모서리
    """
    prompt = """이 수학 문제지 이미지에서 인쇄된 각 문제의 영역을 감지하세요.
반드시 아래 JSON 배열 형식으로만 응답하세요.

[
  {"x": 0.05, "y": 0.03, "w": 0.90, "h": 0.18},
  {"x": 0.05, "y": 0.24, "w": 0.90, "h": 0.22}
]

규칙:
- 좌표는 이미지 전체 크기 대비 비율값(0.0 ~ 1.0)
- x, y는 박스의 왼쪽 상단 모서리 위치
- w는 박스 너비, h는 박스 높이
- 인쇄된 문제 번호, 지문, 조건, 보기를 모두 포함하는 넉넉한 영역으로 잡기
- 학생이 손으로 쓴 답안, 풀이 과정, 메모 등 필기 영역은 절대 포함하지 말 것
- 빈칸(답 쓰는 공간)은 포함 가능하나 그 아래 학생 필기까지 포함하지 말 것
- 교재/교과서/시험지의 인쇄된 텍스트, 수식, 그림만 포함
- 문제가 없으면 빈 배열 [] 반환
- JSON 배열만 출력, 다른 텍스트 없이"""

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": image_base64}},
                {"text": prompt},
            ]
        }]
    }

    result = _call_gemini(GEMINI_MODEL_ANALYZE, payload)
    text = result["candidates"][0]["content"]["parts"][0]["text"]

    try:
        json_match = text
        if "```" in text:
            import re
            m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            if m:
                json_match = m.group(1)
        bboxes = json.loads(json_match)
        if not isinstance(bboxes, list):
            return []
        required = {"x", "y", "w", "h"}
        valid = [b for b in bboxes if isinstance(b, dict) and required.issubset(b.keys())]
        # clamp values to 0.0-1.0
        for b in valid:
            b["x"] = max(0.0, min(1.0, float(b["x"])))
            b["y"] = max(0.0, min(1.0, float(b["y"])))
            b["w"] = max(0.0, min(1.0, float(b["w"])))
            b["h"] = max(0.0, min(1.0, float(b["h"])))
        return valid
    except json.JSONDecodeError:
        logger.warning(f"bbox 감지 JSON 파싱 실패: {text[:200]}")
        return []


def analyze_graph_style(image_base64: str, media_type: str) -> dict:
    """수능/교과서 그래프 이미지에서 SVG 렌더링 시각 스타일 규칙 추출.

    Returns:
        dict with keys: axis_arrow, tick_marks, origin_label, curve_style,
                        asymptote_style, point_style, label_placement,
                        shading_style, overall_size, svg_notes
    """
    prompt = """이것은 한국 수능/교과서의 수학 그래프 이미지입니다.
이 그래프의 시각 스타일을 분석하여 SVG 코드 작성에 필요한 규칙을 JSON으로 추출하세요.

반드시 아래 JSON 형식으로만 응답:

{
  "axis_arrow": "축 끝 화살표의 모양/크기/각도 (예: 작고 날카로운 채워진 삼각형, 길이 약 8px)",
  "tick_marks": "눈금 스타일 (예: 축에 수직인 짧은 선 4px, 숫자는 축 바깥쪽 아래/왼쪽)",
  "origin_label": "원점 O 위치와 크기 (예: 축 교차점 아래왼쪽, 로마체 12px)",
  "curve_style": "함수 곡선 선 굵기/색상 (예: 검은 실선 stroke-width 1.5)",
  "asymptote_style": "점근선 스타일 (없으면 none, 예: 검은 점선 stroke-dasharray 4,3)",
  "point_style": "좌표점 원 크기와 채우기 (예: 반지름 3px 검은 채우기)",
  "label_placement": "함수 라벨/좌표 라벨 위치 패턴 (예: 곡선 끝 오른쪽 위, 점 오른쪽 위)",
  "shading_style": "음영 처리 방식 (없으면 none)",
  "overall_size": "그래프 전체 비율과 여백 (예: 정사각형 비율, 여백 20px 내외)",
  "svg_notes": "SVG 코드 작성 시 주의할 특이사항"
}

JSON만 출력하세요."""

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": image_base64}},
                {"text": prompt},
            ]
        }]
    }

    result = _call_gemini(GEMINI_MODEL_ANALYZE, payload)
    text = result["candidates"][0]["content"]["parts"][0]["text"]

    try:
        json_match = text
        if "```" in text:
            import re
            m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            if m:
                json_match = m.group(1)
        return json.loads(json_match)
    except json.JSONDecodeError:
        logger.warning(f"analyze_graph_style JSON 파싱 실패: {text[:200]}")
        return {"svg_notes": text}
