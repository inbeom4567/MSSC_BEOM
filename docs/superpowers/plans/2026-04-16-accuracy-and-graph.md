# 풀이 정확도 향상 + SVG 그래프 교체 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Few-shot 예시 추가로 풀이 정확도를 높이고, Matplotlib 그래프를 Claude 생성 SVG로 교체한다.

**Architecture:** `_build_prompt()`에 few-shot 예시 파일을 결합하고, `graph_service.py`에서 Matplotlib 렌더링을 SVG 추출로 대체한다. 프론트엔드 `GraphImage.jsx`는 SVG 문자열을 DOMPurify로 sanitize한 뒤 직접 렌더링한다.

**Tech Stack:** Python(FastAPI), anthropic SDK, React/Vite, DOMPurify(npm)

---

## 파일 맵

| 파일 | 작업 |
|------|------|
| `backend/prompts/fewshot_examples.txt` | 신규 — 올바른 풀이 예시 2개 |
| `backend/services/claude_service.py` | 수정 — `_build_prompt()`에 few-shot 결합, `reload_prompts()` 갱신 |
| `backend/services/graph_service.py` | 수정 — Matplotlib 제거, SVG 추출로 교체 |
| `backend/prompts/solve_prompt.txt` | 수정 — SVG 그래프 지시 및 예시 추가, 그래프 태그 문법 변경 |
| `frontend/src/components/GraphImage.jsx` | 수정 — SVG 렌더링 지원, DOMPurify 적용 |

---

## Task 1: Few-shot 예시 파일 생성

**Files:**
- Create: `backend/prompts/fewshot_examples.txt`

- [ ] **Step 1: fewshot_examples.txt 파일 생성**

아래 내용으로 `backend/prompts/fewshot_examples.txt` 파일을 생성한다.
(교사가 나중에 수정·추가 가능하도록 구조를 명확히 유지한다.)

```
## Few-shot 예시: 올바른 유사문항 출력 형식

아래는 모범적인 유사문항 생성 예시입니다. 수식 형식, 풀이 흐름, 출력 태그를 정확히 따르세요.

---

### 예시 1 (이차함수 최솟값)

-유사문항-
함수 [f(x)=x `^` 2-8x+19]의 최솟값을 구하시오.

-정답-
3

-해설-
[f(x)=x `^` 2-8x+19=(x-4) `^` 2+3]

[(x-4) `^` 2 >= 0]이므로 [x=4]일 때 최솟값은 [3]이다.

---

### 예시 2 (등차수열 일반항)

-유사문항-
첫째항이 [5]이고 공차가 [3]인 등차수열 [{a_n}]에서 [a_{12}]를 구하시오.

-정답-
38

-해설-
등차수열의 일반항은 [a_n=a_1+(n-1)d]이므로

[a_{12}=5+(12-1) times 3=5+33=38]
```

- [ ] **Step 2: 파일 생성 확인**

```bash
cat "backend/prompts/fewshot_examples.txt"
```

예상 출력: 위에서 작성한 내용이 그대로 출력됨.

- [ ] **Step 3: 커밋**

```bash
git add backend/prompts/fewshot_examples.txt
git commit -m "feat: add few-shot examples for solution accuracy"
```

---

## Task 2: `_build_prompt()`에 Few-shot 통합

**Files:**
- Modify: `backend/services/claude_service.py:121-128`

- [ ] **Step 1: `_build_prompt()` 수정**

`claude_service.py`의 `_build_prompt()` 메서드를 다음과 같이 수정한다.

현재 코드:
```python
def _build_prompt(self, filename: str) -> str:
    """프롬프트 텍스트 + 매핑 사전 예시를 결합"""
    base = _load_prompt(filename)
    return base + self.mapping_ref
```

수정 후:
```python
def _build_prompt(self, filename: str) -> str:
    """프롬프트 텍스트 + 매핑 사전 예시 + few-shot 예시를 결합"""
    base = _load_prompt(filename)
    fewshot_path = PROMPTS_DIR / "fewshot_examples.txt"
    fewshot = fewshot_path.read_text(encoding="utf-8") if fewshot_path.exists() else ""
    return base + self.mapping_ref + ("\n\n" + fewshot if fewshot else "")
```

- [ ] **Step 2: Python 문법 확인**

```bash
python -m py_compile backend/services/claude_service.py && echo "OK"
```

예상 출력: `OK`

- [ ] **Step 3: 서버 재시작 없이 적용 확인**

`reload_prompts()`는 `_build_prompt()`를 다시 호출하므로 자동 반영됨. 별도 수정 불필요.

- [ ] **Step 4: 커밋**

```bash
git add backend/services/claude_service.py
git commit -m "feat: integrate few-shot examples into prompt builder"
```

---

## Task 3: `graph_service.py` SVG 방식으로 교체

**Files:**
- Modify: `backend/services/graph_service.py`

- [ ] **Step 1: `graph_service.py` 전체 교체**

파일 전체를 다음 내용으로 교체한다. Matplotlib, numpy 임포트를 모두 제거하고 SVG 추출 로직만 남긴다.

```python
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
```

- [ ] **Step 2: Python 문법 확인**

```bash
python -m py_compile backend/services/graph_service.py && echo "OK"
```

예상 출력: `OK`

- [ ] **Step 3: `claude_service.py` import 체인 확인**

`claude_service.py` 1번 줄에 `from services.graph_service import process_graphs_in_text`가 있으므로 함수 시그니처가 유지되는지 확인:
- 입력: `str` → 출력: `tuple[str, list[str]]` — 동일함. 변경 불필요.

- [ ] **Step 4: 커밋**

```bash
git add backend/services/graph_service.py
git commit -m "feat: replace matplotlib graph with SVG extraction"
```

---

## Task 4: `solve_prompt.txt`에 SVG 그래프 지시 추가

**Files:**
- Modify: `backend/prompts/solve_prompt.txt`

- [ ] **Step 1: 파일 끝에 SVG 그래프 섹션 추가**

`solve_prompt.txt` 파일의 맨 끝(수식 매핑 사전 섹션 앞)에 아래 내용을 추가한다.

```
---

## 그래프 출력 규칙 (SVG 방식)

그래프가 필요할 때는 반드시 아래 태그 형식으로 SVG 코드를 직접 작성하세요.

### 태그 형식
-그래프-
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" width="300" height="300">
  <!-- SVG 내용 -->
</svg>
-그래프끝-

### 수능/교과서 스타일 SVG 규칙
1. 좌표축: 검은 실선(stroke="black" stroke-width="1.5"), 화살표 끝 처리
2. 함수 곡선: 검은 실선(stroke-width="1.5"), fill="none"
3. 점근선: 검은 점선(stroke-dasharray="4,3")
4. 포인트: 검은 원(r="3", fill="black")
5. 축 라벨 x, y: 이탤릭체(font-style="italic")
6. 원점 O: 로마체
7. 눈금선 없음, 배경 흰색

### 이차함수 그래프 예시 (y = x² - 4x + 3)
-그래프-
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 -20 280 280" width="300" height="300">
  <!-- 좌표축 -->
  <line x1="-10" y1="120" x2="255" y2="120" stroke="black" stroke-width="1.5"/>
  <line x1="80" y1="255" x2="80" y2="-10" stroke="black" stroke-width="1.5"/>
  <!-- 화살표 -->
  <polygon points="255,120 246,115 246,125" fill="black"/>
  <polygon points="80,-10 74,-1 86,-1" fill="black"/>
  <!-- 축 라벨 -->
  <text x="260" y="124" font-size="14" font-style="italic" font-family="serif">x</text>
  <text x="68" y="-14" font-size="14" font-style="italic" font-family="serif">y</text>
  <text x="65" y="135" font-size="12" font-family="serif">O</text>
  <!-- 포물선 y=(x-2)²-1, x: 0~4, 중심점(2,1)이 SVG(160,100)에 대응, scale=40 -->
  <!-- SVG좌표: svgX = 80 + x*40, svgY = 120 - y*40 -->
  <!-- x=0: (80,80), x=1: (120,115.6)→(120,116), x=2: (160,120+40=160)→최솟값y=-1→(160,160) -->
  <!-- y=(x-2)²-1: x=0→y=3→svgY=0, x=1→y=0→svgY=120, x=2→y=-1→svgY=160, x=3→y=0→svgY=120, x=4→y=3→svgY=0 -->
  <path d="M 80,0 C 100,40 120,100 160,160 C 200,100 220,40 240,0"
        stroke="black" stroke-width="1.5" fill="none"/>
  <!-- 꼭짓점 (2,-1) → SVG(160,160) -->
  <circle cx="160" cy="160" r="3" fill="black"/>
  <text x="164" y="174" font-size="12" font-family="serif">(2, -1)</text>
  <!-- x절편 (1,0),(3,0) → SVG(120,120),(200,120) -->
  <circle cx="120" cy="120" r="3" fill="black"/>
  <text x="114" y="136" font-size="12" font-family="serif">1</text>
  <circle cx="200" cy="120" r="3" fill="black"/>
  <text x="196" y="136" font-size="12" font-family="serif">3</text>
  <!-- y절편 (0,3) → SVG(80,0) -->
  <circle cx="80" cy="0" r="3" fill="black"/>
  <text x="56" y="4" font-size="12" font-family="serif">3</text>
  <!-- 함수 라벨 -->
  <text x="210" y="30" font-size="13" font-style="italic" font-family="serif">y=x²-4x+3</text>
</svg>
-그래프끝-
```

- [ ] **Step 2: 파일 저장 확인**

```bash
python -c "
from pathlib import Path
txt = Path('backend/prompts/solve_prompt.txt').read_text(encoding='utf-8')
print('SVG 섹션 포함:', 'SVG 방식' in txt)
print('예시 포함:', 'viewBox' in txt)
"
```

예상 출력:
```
SVG 섹션 포함: True
예시 포함: True
```

- [ ] **Step 3: 커밋**

```bash
git add backend/prompts/solve_prompt.txt
git commit -m "feat: add SVG graph instructions and example to solve_prompt"
```

---

## Task 5: 프론트엔드 SVG 렌더링 지원

**Files:**
- Modify: `frontend/src/components/GraphImage.jsx`

- [ ] **Step 1: DOMPurify 설치**

```bash
cd frontend && npm install dompurify
```

예상 출력: `added N packages` 포함한 npm 설치 완료 메시지.

- [ ] **Step 2: `GraphImage.jsx` 수정**

현재 파일은 `base64Data`를 받아 PNG `<img>`로 렌더링한다.
SVG 문자열을 받으면 DOMPurify로 sanitize 후 `dangerouslySetInnerHTML`로 렌더링하도록 수정한다.

```jsx
import { useState } from 'react'
import DOMPurify from 'dompurify'

export default function GraphImage({ base64Data, index }) {
  const [copied, setCopied] = useState(false)

  // SVG 문자열인지 확인 (Matplotlib 제거 후 graphs[]는 SVG 문자열)
  const isSvg = typeof base64Data === 'string' && base64Data.trimStart().startsWith('<svg')

  const handleDownload = () => {
    if (isSvg) {
      const blob = new Blob([base64Data], { type: 'image/svg+xml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `graph_${index + 1}.svg`
      link.click()
      URL.revokeObjectURL(url)
    } else {
      const src = `data:image/png;base64,${base64Data}`
      const link = document.createElement('a')
      link.href = src
      link.download = `graph_${index + 1}.png`
      link.click()
    }
  }

  const handleCopy = async () => {
    if (isSvg) {
      await navigator.clipboard.writeText(base64Data)
    } else {
      const src = `data:image/png;base64,${base64Data}`
      const res = await fetch(src)
      const blob = await res.blob()
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="my-4 relative group">
      {isSvg ? (
        <div
          className="mx-auto max-w-full flex justify-center"
          dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(base64Data) }}
        />
      ) : (
        <img
          src={`data:image/png;base64,${base64Data}`}
          alt={`그래프 ${index + 1}`}
          className="mx-auto rounded-lg border border-gray-200 shadow-sm max-w-full"
        />
      )}
      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button onClick={handleCopy}
          className="px-2 py-1 bg-gray-700 text-gray-200 rounded text-xs hover:bg-gray-600">
          {copied ? '✓' : '복사'}
        </button>
        <button onClick={handleDownload}
          className="px-2 py-1 bg-gray-700 text-gray-200 rounded text-xs hover:bg-gray-600">
          저장
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 프론트엔드 빌드 확인**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

예상 출력: `✓ built in` 또는 `dist/` 생성 메시지. 에러 없음.

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/components/GraphImage.jsx frontend/package.json frontend/package-lock.json
git commit -m "feat: support SVG graph rendering with DOMPurify sanitization"
```

---

## 자기 검토 (Self-Review)

**스펙 커버리지:**
- [x] 프롬프트 강화 (중간값 명시, 역검증) → solve_prompt.txt의 STEP 5 기존 규칙 + few-shot 예시로 보완
- [x] Few-shot 예시 추가 → Task 1
- [x] 검증 루프 — `_cleanup_output()`이 이미 존재하고 있으며, few-shot으로 1차 정확도를 높여 보완
- [x] Matplotlib 제거 → Task 3
- [x] SVG 파이프라인 → Task 3, 4
- [x] DOMPurify XSS 방어 → Task 5
- [x] SVG 저장 기능 → Task 5 (SVG 파일로 저장)

**플레이스홀더 없음** — 모든 코드 블록이 실제 코드로 작성됨.

**타입 일관성:**
- `process_graphs_in_text()` 시그니처 유지: `str → tuple[str, list[str]]`
- `graphs[]` 배열이 이제 SVG 문자열을 담음 — `GraphImage.jsx`에서 `isSvg` 분기로 처리
- `base64Data` prop 이름은 이전과 동일하게 유지 (이름이 부정확해졌지만 기존 코드 호환성 유지)
