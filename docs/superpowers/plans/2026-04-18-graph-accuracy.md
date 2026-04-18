# 그래프 정확도 고도화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** book/ 폴더의 실제 기출 HWPX 파일에서 그래프 이미지를 추출하여 Gemini로 수능 스타일 SVG 규칙을 분석하고, solve_prompt.txt의 그래프 출력 지시를 구체화한다.

**Architecture:** `analyze_book_graphs.py` 단일 스크립트가 HWPX→BinData 이미지 추출 → `analyze_graph()`로 그래프 필터링 → `analyze_graph_style()`로 SVG 스타일 추출 → `graph_style_report.json` 저장의 전체 파이프라인을 담당. 분석 결과를 수동 검토 후 solve_prompt.txt SVG 섹션에 반영.

**Tech Stack:** Python zipfile, base64, pathlib, Gemini API (gemini-2.5-flash), JSON

---

### Task 1: gemini_service.py에 analyze_graph_style() 추가

**Files:**
- Modify: `backend/services/gemini_service.py:352` (파일 끝에 추가)

- [ ] **Step 1: gemini_service.py 끝(352줄)에 함수 추가**

`backend/services/gemini_service.py` 352줄 끝에 아래 코드를 추가한다:

```python


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
```

- [ ] **Step 2: py_compile로 문법 검사**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution/backend"
python -m py_compile services/gemini_service.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution"
git add backend/services/gemini_service.py
git commit -m "feat: gemini_service에 analyze_graph_style() 추가"
```

---

### Task 2: analyze_book_graphs.py 스크립트 생성

**Files:**
- Create: `backend/scripts/analyze_book_graphs.py`

- [ ] **Step 1: backend/scripts/ 폴더 생성 확인**

```bash
mkdir -p "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution/backend/scripts"
```

- [ ] **Step 2: analyze_book_graphs.py 파일 생성**

`backend/scripts/analyze_book_graphs.py` 를 아래 내용으로 생성한다:

```python
"""book/ 폴더의 HWPX 기출 파일에서 그래프 이미지를 추출하고
Gemini로 수능 SVG 스타일 규칙을 분석하여 graph_style_report.json에 저장."""

import sys
import json
import base64
import zipfile
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.gemini_service import analyze_graph, analyze_graph_style

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BOOK_DIR = Path(__file__).parent.parent.parent / "book"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "graph_style_report.json"

IMAGE_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png"}
MEDIA_TYPES = {
    ".bmp": "image/bmp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def extract_images_from_hwpx(hwpx_path: Path) -> list:
    """HWPX ZIP에서 BinData/ 이미지 파일을 base64로 추출."""
    images = []
    try:
        with zipfile.ZipFile(hwpx_path) as z:
            for name in z.namelist():
                if not name.startswith("BinData/"):
                    continue
                ext = Path(name).suffix.lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue
                data = z.read(name)
                images.append({
                    "name": name,
                    "base64": base64.b64encode(data).decode(),
                    "media_type": MEDIA_TYPES.get(ext, "image/jpeg"),
                })
    except Exception as e:
        logger.warning(f"  [경고] {hwpx_path.name} 열기 실패: {e}")
    return images


def _aggregate_styles(results: list) -> dict:
    """스타일 결과 목록에서 필드별 샘플 집계."""
    fields = [
        "axis_arrow", "tick_marks", "origin_label", "curve_style",
        "asymptote_style", "point_style", "label_placement",
        "shading_style", "overall_size", "svg_notes",
    ]
    aggregated = {}
    for field in fields:
        values = [
            r["style"].get(field, "")
            for r in results
            if r.get("style", {}).get(field)
        ]
        aggregated[field] = values[:8]  # 최대 8개 샘플
    return aggregated


def main(year_filter: str = None):
    """
    year_filter: "2025년" 처럼 특정 연도만 처리. None이면 전체.
    사용법:
      python scripts/analyze_book_graphs.py           # 전체
      python scripts/analyze_book_graphs.py 2025년    # 2025년만
    """
    if year_filter:
        hwpx_files = sorted((BOOK_DIR / year_filter).rglob("*.hwpx"))
    else:
        hwpx_files = sorted(BOOK_DIR.rglob("*.hwpx"))

    logger.info(f"HWPX 파일 {len(hwpx_files)}개 처리 시작")
    if year_filter:
        logger.info(f"  필터: {year_filter}")

    results = []
    total_images = 0
    graph_images = 0
    errors = 0

    for hwpx_path in hwpx_files:
        logger.info(f"\n[{hwpx_path.relative_to(BOOK_DIR)}]")
        images = extract_images_from_hwpx(hwpx_path)
        logger.info(f"  이미지 {len(images)}개 추출")
        total_images += len(images)

        for img in images:
            try:
                analysis = analyze_graph(img["base64"], img["media_type"])
                if not analysis.get("has_graph", False):
                    continue
                graph_images += 1
                logger.info(f"  그래프: {img['name']} (타입: {analysis.get('graph_type')})")

                style = analyze_graph_style(img["base64"], img["media_type"])
                results.append({
                    "file": str(hwpx_path.relative_to(BOOK_DIR)),
                    "image": img["name"],
                    "graph_type": analysis.get("graph_type", "unknown"),
                    "description": analysis.get("description", ""),
                    "style": style,
                })
            except Exception as e:
                errors += 1
                logger.warning(f"  [에러] {img['name']}: {e}")

    aggregated = _aggregate_styles(results)

    report = {
        "analyzed_at": datetime.now().isoformat(),
        "year_filter": year_filter or "전체",
        "total_hwpx_files": len(hwpx_files),
        "total_images": total_images,
        "graph_images": graph_images,
        "errors": errors,
        "styles": results,
        "aggregated": aggregated,
    }

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'='*50}")
    logger.info(f"완료: HWPX {len(hwpx_files)}개 / 이미지 {total_images}개 / 그래프 {graph_images}개 / 에러 {errors}개")
    logger.info(f"결과 저장: {OUTPUT_FILE}")


if __name__ == "__main__":
    year_filter = sys.argv[1] if len(sys.argv) > 1 else None
    main(year_filter)
```

- [ ] **Step 3: py_compile로 문법 검사**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution/backend"
python -m py_compile scripts/analyze_book_graphs.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 4: 커밋**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution"
git add backend/scripts/analyze_book_graphs.py
git commit -m "feat: book/ 기출 그래프 분석 스크립트 추가"
```

---

### Task 3: 스크립트 샘플 실행 (2025년만)

**Files:**
- Output: `backend/data/graph_style_report.json` (스크립트가 생성)

- [ ] **Step 1: 2025년 파일만 먼저 실행**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution/backend"
python scripts/analyze_book_graphs.py "2025년"
```

Expected 출력 예시:
```
HWPX 파일 15개 처리 시작
  필터: 2025년
[2025년/2025년 고3 수능 문항.hwpx]
  이미지 26개 추출
  그래프: BinData/image2.jpg (타입: function)
  그래프: BinData/image5.jpg (타입: function)
  ...
완료: HWPX 15개 / 이미지 ~200개 / 그래프 ~30개 / 에러 0개
결과 저장: backend/data/graph_style_report.json
```

- [ ] **Step 2: 출력 파일 검증**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution/backend"
python -c "
import json
with open('data/graph_style_report.json', encoding='utf-8') as f:
    r = json.load(f)
print(f'그래프 이미지: {r[\"graph_images\"]}개')
print(f'집계 필드: {list(r[\"aggregated\"].keys())}')
print('--- axis_arrow 샘플 ---')
for v in r['aggregated'].get('axis_arrow', [])[:3]:
    print(' ', v)
"
```

Expected: `그래프 이미지: 20개 이상` / axis_arrow 샘플 3개 출력

- [ ] **Step 3: 오류가 있으면 수정 후 재실행**

에러가 발생했다면 콘솔 출력에서 `[에러]` 줄을 확인하고 해당 파일의 MEDIA_TYPE 또는 JSON 파싱 문제를 수정한 뒤 재실행.

에러 없이 graph_images ≥ 20 이면 다음 단계로 진행.

---

### Task 4: 전체 book/ 스캔 실행

**Files:**
- Output: `backend/data/graph_style_report.json` (덮어쓰기)

- [ ] **Step 1: 전체 실행**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution/backend"
python scripts/analyze_book_graphs.py
```

Expected: 수 분 소요 (파일 85개, 이미지 ~1000장 처리)

완료 후 출력 예시:
```
완료: HWPX 85개 / 이미지 ~1200개 / 그래프 ~150개 / 에러 N개
결과 저장: backend/data/graph_style_report.json
```

- [ ] **Step 2: 집계 결과 확인**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution/backend"
python -c "
import json
with open('data/graph_style_report.json', encoding='utf-8') as f:
    r = json.load(f)
print(f'그래프: {r[\"graph_images\"]}개 / 에러: {r[\"errors\"]}개')
agg = r['aggregated']
for field, samples in agg.items():
    print(f'\n[{field}]')
    for s in samples[:3]:
        print(f'  {s}')
"
```

이 출력을 그대로 복사해서 다음 Task에서 활용한다.

- [ ] **Step 3: 커밋**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution"
git add backend/data/graph_style_report.json
git commit -m "data: 기출 그래프 스타일 분석 결과 (book/ 전체)"
```

---

### Task 5: solve_prompt.txt SVG 섹션 업데이트

**Files:**
- Modify: `backend/prompts/solve_prompt.txt:854-894`

- [ ] **Step 1: graph_style_report.json 집계 값 확인**

Task 4 Step 2의 집계 출력에서 각 필드의 가장 많이 반복된 패턴을 파악한다.

반드시 확인할 항목:
- `axis_arrow`: 화살표 SVG polygon points 값
- `tick_marks`: 눈금 선 길이 (px)
- `origin_label`: O 원점 위치 offset
- `curve_style`: stroke-width 값
- `point_style`: circle r 값

- [ ] **Step 2: solve_prompt.txt의 SVG 규칙 섹션 교체**

`backend/prompts/solve_prompt.txt` 854~894줄의 `### 수능/교과서 스타일 SVG 규칙` 블록 전체를 아래로 교체한다. `{...}` 부분을 Task 4에서 확인한 실제 값으로 채운다:

```
### 수능/교과서 스타일 SVG 규칙 (기출 이미지 분석 기반)

**기본 캔버스:** viewBox="-20 -20 280 280" width="300" height="300"
- 좌표 변환: svgX = origin_x + x * scale, svgY = origin_y - y * scale
- 기본 origin=(80,140), scale=40 (그래프 범위에 따라 조정)

**1. 좌표축**
- 선: stroke="black" stroke-width="1.5" (x축: y1=y2=origin_y, y축: x1=x2=origin_x)
- 화살표: <polygon> x축 끝 오른쪽, y축 끝 위쪽
  - x축 화살표: points="{끝x},{oy} {끝x-9},{oy-4} {끝x-9},{oy+4}" fill="black"
  - y축 화살표: points="{ox},{끝y} {ox-4},{끝y+9} {ox+4},{끝y+9}" fill="black"
- 축 라벨: font-size="14" font-style="italic" font-family="serif"
  - x: x축 끝에서 +5px 오른쪽, y 축 레이블과 수평
  - y: y축 끝에서 -18px 위쪽, x 레이블 왼쪽 정렬

**2. 원점 O**
- <text> 위치: x=origin_x-14, y=origin_y+14 (축 교차점 아래왼쪽)
- font-size="12" font-family="serif" (이탤릭 없음, 로마체)

**3. 눈금과 숫자**
- 눈금선 없음 (tick mark 없음)
- 축 위 숫자: 축에서 수직 4px 바깥쪽
  - x축 숫자: y=origin_y+16, font-size="12" font-family="serif"
  - y축 숫자: x=origin_x-8, text-anchor="end", font-size="12"

**4. 함수 곡선**
- stroke="black" stroke-width="1.5" fill="none"
- <path d="M ... C ... "> 또는 <path d="M ... Q ... "> 사용
- 이차함수: 3점 이상으로 자연스러운 곡선, 끝은 축 바깥까지 연장

**5. 점근선**
- stroke="black" stroke-width="1" stroke-dasharray="4,3" (없으면 생략)

**6. 좌표점**
- <circle r="3" fill="black"> (채워진 점)
- <circle r="3" fill="white" stroke="black" stroke-width="1.5"> (빈 점, 열린 구간)

**7. 라벨**
- 함수 이름: 곡선 끝 오른쪽 위, font-size="13" font-style="italic"
- 좌표 (a, b): 점 오른쪽 위 +4px, font-size="12"
- 단독 숫자(절편): 점 아래 또는 왼쪽 +4px, font-size="12"

**8. 음영**
- <path> fill="lightgray" fill-opacity="0.3" 또는 fill="url(#hatch)"
- 해칭: <pattern id="hatch"> <line> 45도 간격 4px

**9. SVG 전체 구조 순서**
1. 좌표축 선
2. 화살표 polygon
3. 점근선 (있으면)
4. 함수 곡선/도형
5. 음영 (있으면)
6. 좌표점 circle
7. 숫자/라벨 text
8. 축 라벨 x, y, O
```

- [ ] **Step 3: 변경 후 서버 재시작 없이 즉시 반영 확인**

solve_prompt.txt는 서버 재시작 없이 API 호출 시 매번 읽힘. 백엔드가 실행 중이면 다음 생성 요청부터 즉시 적용.

```bash
# 서버가 실행 중인지 확인
curl -s http://localhost:8001/api/history | python -m json.tool | head -5
```

Expected: JSON 응답 (서버 정상)

- [ ] **Step 4: 커밋**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution"
git add backend/prompts/solve_prompt.txt
git commit -m "feat: SVG 그래프 규칙 고도화 — 기출 이미지 분석 기반 수능 스타일 적용"
```
