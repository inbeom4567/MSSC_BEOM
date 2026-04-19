# 스캔 에디터 개편 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스캔 처리 흐름에 문제별 리뷰 화면(ProblemReviewer)과 HWP 수식 팔레트 편집기(FormulaEditor)를 추가하고, 보기박스/조건박스 XML 템플릿을 HWPX 생성에 적용한다.

**Architecture:** CropEditor 확정 후 'reviewing' 스텝(ProblemReviewer)을 추가해 문제를 하나씩 확인/제외할 수 있게 한다. ScanResultCard에 FormulaEditor 인라인 편집 모드를 추가해 결과 텍스트를 HWP 수식 팔레트로 편집하고 실시간 KaTeX 렌더링으로 확인한다. 보기박스/조건박스 XML은 `보기박스조건박스.hwpx`에서 추출해 `backend/data/box_templates.json`에 저장하고, HWPX 생성 시 텍스트 마커(`===조건박스===` 등)를 해당 XML로 교체한다.

**Tech Stack:** React 19, KaTeX 0.16 (npm), FastAPI, Python zipfile/lxml, Tailwind CSS

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `frontend/src/components/ProblemReviewer.jsx` | 문제별 포함/제외 리뷰 UI (새로 생성) |
| `frontend/src/components/FormulaEditor.jsx` | HWP 수식 팔레트 + KaTeX 미리보기 (새로 생성) |
| `backend/data/box_templates.json` | 조건박스·보기박스 XML 블록 (새로 생성) |
| `frontend/src/components/TabScan.jsx` | 'reviewing' step 추가, ProblemReviewer 연결 |
| `frontend/src/components/ScanResultCard.jsx` | FormulaEditor 인라인 편집 + onResultChange 콜백 |
| `backend/services/hwpx_service.py` | `_build_section_xml`에 박스 마커 처리 추가 |

---

## 배경 지식

### HWPX 박스 마커 규칙
텍스트에서 아래 마커를 만나면 HWPX XML로 교체한다:
- `===조건박스===` → rect XML (단 너비 99%, widthRelTo=PARA)
- `===보기박스1===` → tbl XML 103.5mm (2단 레이아웃용)
- `===보기박스2===` → tbl XML 149.4mm (1단 전체)
- `===보기박스3===` → tbl XML 86.5mm (좁은 단용)

### FormulaEditor HWP → KaTeX 변환 규칙
| HWP 수식 | KaTeX |
|---------|-------|
| `{a} over {b}` | `\dfrac{a}{b}` |
| `sqrt {x}` | `\sqrt{x}` |
| `x^{2}` | `x^{2}` |
| `x_{n}` | `x_{n}` |
| `left ( ... right )` | `\left( ... \right)` |
| `left [ ... right ]` | `\left[ ... \right]` |
| `left \{ ... right \}` | `\left\{ ... \right\}` |
| `TIMES` | `\times` |
| `DIVIDE` | `\div` |
| `NEQ` | `\neq` |
| `LEQ` | `\leq` |
| `GEQ` | `\geq` |
| `PM` | `\pm` |
| `CDOT` | `\cdot` |
| `INT` | `\int` |
| `SUM` | `\sum` |
| `PROD` | `\prod` |
| `LIM` | `\lim` |
| `INFINITY` | `\infty` |
| `PI` | `\pi` |
| `ALPHA` | `\alpha` |
| `BETA` | `\beta` |
| `THETA` | `\theta` |
| `DELTA` | `\delta` |
| `SIGMA` | `\sigma` |
| `sin` | `\sin` |
| `cos` | `\cos` |
| `tan` | `\tan` |
| `log` | `\log` |
| `ln` | `\ln` |

텍스트에서 `[수식]` 형태(대괄호)는 수식 블록. `[a+b]` → KaTeX로 렌더링.

### TabScan 스텝 흐름
```
upload → detecting → editing(CropEditor) → reviewing(ProblemReviewer) → processing → done
```
- `editing`에서 CropEditor의 "확정" 버튼 클릭 → `reviewing`으로 전환
- `reviewing`에서 ProblemReviewer의 "처리 시작" 클릭 → `processing`

### ScanResultCard 수정 흐름
- `result` prop으로 받은 텍스트를 내부 `editedResult` state로 관리
- `onResultChange(problemId, newResult)` 콜백으로 TabScan의 `cards` 업데이트
- HWPX 다운로드 시 `cards[n].result` (편집된 값) 사용

---

## Task 1: 박스 XML 추출 + hwpx_service 마커 처리

**Files:**
- Create: `backend/data/box_templates.json`
- Modify: `backend/services/hwpx_service.py` (lines 186–248, `_build_section_xml` 함수)

- [ ] **Step 1: box_templates.json 생성 스크립트 실행**

`backend/data/` 폴더에서 아래 Python 스크립트 실행 (1회성, 저장 후 삭제):

```python
# extract_boxes.py (루트에서 실행)
import zipfile, re, json

with zipfile.ZipFile('보기박스조건박스.hwpx', 'r') as z:
    content = z.read('Contents/section0.xml').decode('utf-8', errors='replace')

rect_match = re.search(r'<hp:rect\b.*?</hp:rect>', content, re.DOTALL)
rect_xml = rect_match.group(0) if rect_match else ''

tbl_matches = list(re.finditer(r'<hp:tbl\b.*?</hp:tbl>', content, re.DOTALL))

result = {
    "조건박스": rect_xml,
    "보기박스1": tbl_matches[0].group(0) if len(tbl_matches) > 0 else '',
    "보기박스2": tbl_matches[1].group(0) if len(tbl_matches) > 1 else '',
    "보기박스3": tbl_matches[2].group(0) if len(tbl_matches) > 2 else '',
}

with open('backend/data/box_templates.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("Done:", {k: f"{len(v)}자" for k, v in result.items()})
```

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution"
python extract_boxes.py
# Expected: Done: {'조건박스': '2149자', '보기박스1': '2274자', ...}
```

- [ ] **Step 2: 스크립트 삭제 + JSON 확인**

```bash
rm extract_boxes.py
python -c "import json; d=json.load(open('backend/data/box_templates.json')); print([k+':'+str(len(v)) for k,v in d.items()])"
# Expected: ['조건박스:2149', '보기박스1:2274', '보기박스2:2425', '보기박스3:2274']
```

- [ ] **Step 3: hwpx_service.py에 _load_box_templates + 마커 치환 추가**

`backend/services/hwpx_service.py` 파일 상단 import 섹션(현재 라인 1 근처)에 추가:

```python
import json as _json
import os as _os

_BOX_TEMPLATES: dict = {}

def _load_box_templates() -> dict:
    global _BOX_TEMPLATES
    if _BOX_TEMPLATES:
        return _BOX_TEMPLATES
    path = _os.path.join(_os.path.dirname(__file__), '..', 'data', 'box_templates.json')
    try:
        with open(path, encoding='utf-8') as f:
            _BOX_TEMPLATES = _json.load(f)
    except Exception:
        _BOX_TEMPLATES = {}
    return _BOX_TEMPLATES
```

- [ ] **Step 4: _build_section_xml에 박스 마커 처리 추가**

`_build_section_xml` 함수(현재 line 186)의 `blocks = _parse_problem_blocks(text)` 직전에 삽입:

```python
    # 박스 마커를 HP XML run으로 교체 전처리
    text = _substitute_box_markers(text)
```

그리고 파일 끝에 새 함수 추가:

```python
_BOX_MARKER_RE = re.compile(r'===(조건박스|보기박스[123])===')

def _substitute_box_markers(text: str) -> str:
    """텍스트의 ===조건박스=== 등 마커를 _BOX_MARKER_LINE sentinel로 교체.
    실제 XML run 삽입은 _line_to_runs에서 처리."""
    templates = _load_box_templates()
    def replace(m):
        key = m.group(1)
        if key in templates and templates[key]:
            return f'\x00BOX:{key}\x00'
        return ''
    return _BOX_MARKER_RE.sub(replace, text)
```

그리고 `_line_to_runs` 함수 맨 앞에 sentinel 처리 추가 (현재 `_line_to_runs` 함수 찾아서):

```python
def _line_to_runs(line: str, eq_counter: list) -> str:
    templates = _load_box_templates()
    # 박스 sentinel 처리
    if line.startswith('\x00BOX:') and line.endswith('\x00'):
        key = line[5:-1]
        xml = templates.get(key, '')
        if xml:
            return f'<hp:run charPrIDRef="0">{xml}</hp:run>'
        return ''
    # ... 기존 코드 그대로 ...
```

- [ ] **Step 5: 수동 확인**

```python
# 아래 코드를 Python REPL에서 실행
import sys; sys.path.insert(0, 'backend')
from services.hwpx_service import create_hwpx
import zipfile, io

text = "===조건박스===\n문제 내용입니다.\n===보기박스1==="
hwpx_bytes = create_hwpx(text)
with zipfile.ZipFile(io.BytesIO(hwpx_bytes)) as z:
    xml = z.read('Contents/section0.xml').decode('utf-8', errors='replace')
    print('rect 포함:', 'hp:rect' in xml)
    print('tbl 포함:', 'hp:tbl' in xml)
# Expected: rect 포함: True, tbl 포함: True
```

- [ ] **Step 6: 커밋**

```bash
git add backend/data/box_templates.json backend/services/hwpx_service.py
git commit -m "feat: 보기박스/조건박스 XML 템플릿 추출 및 HWPX 마커 치환 구현"
```

---

## Task 2: FormulaEditor 컴포넌트

**Files:**
- Create: `frontend/src/components/FormulaEditor.jsx`

- [ ] **Step 1: hwpToLatex 변환 함수 작성 + 스냅샷 테스트**

`frontend/src/components/FormulaEditor.jsx` 파일 생성:

```jsx
import { useState, useRef, useEffect, useCallback } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'

// ── HWP 수식 → LaTeX 변환 ──────────────────────────────────────────
export function hwpToLatex(hwp) {
  return hwp
    // 분수: {a} over {b} → \dfrac{a}{b}
    .replace(/\{([^}]*)\}\s+over\s+\{([^}]*)\}/g, (_, n, d) => `\\dfrac{${hwpToLatex(n)}}{${hwpToLatex(d)}}`)
    // 루트: sqrt {x} → \sqrt{x}
    .replace(/sqrt\s*\{([^}]*)\}/g, (_, x) => `\\sqrt{${hwpToLatex(x)}}`)
    // 괄호
    .replace(/left\s*\(\s*(.*?)\s*right\s*\)/gs, (_, inner) => `\\left(${hwpToLatex(inner)}\\right)`)
    .replace(/left\s*\[\s*(.*?)\s*right\s*\]/gs, (_, inner) => `\\left[${hwpToLatex(inner)}\\right]`)
    .replace(/left\s*\\\{\s*(.*?)\s*right\s*\\\}/gs, (_, inner) => `\\left\\{${hwpToLatex(inner)}\\right\\}`)
    // 연산자
    .replace(/\bTIMES\b/g, '\\times')
    .replace(/\bDIVIDE\b/g, '\\div')
    .replace(/\bNEQ\b/g, '\\neq')
    .replace(/\bLEQ\b/g, '\\leq')
    .replace(/\bGEQ\b/g, '\\geq')
    .replace(/\bPM\b/g, '\\pm')
    .replace(/\bCDOT\b/g, '\\cdot')
    .replace(/\bINT\b/g, '\\int')
    .replace(/\bSUM\b/g, '\\sum')
    .replace(/\bPROD\b/g, '\\prod')
    .replace(/\bLIM\b/g, '\\lim')
    .replace(/\bINFINITY\b/g, '\\infty')
    // 그리스
    .replace(/\bPI\b/g, '\\pi')
    .replace(/\bALPHA\b/g, '\\alpha')
    .replace(/\bBETA\b/g, '\\beta')
    .replace(/\bTHETA\b/g, '\\theta')
    .replace(/\bDELTA\b/g, '\\delta')
    .replace(/\bSIGMA\b/g, '\\sigma')
    .replace(/\bOMEGA\b/g, '\\omega')
    // 삼각함수
    .replace(/\bsin\b/g, '\\sin')
    .replace(/\bcos\b/g, '\\cos')
    .replace(/\btan\b/g, '\\tan')
    .replace(/\blog\b/g, '\\log')
    .replace(/\bln\b/g, '\\ln')
}

// 텍스트 전체를 KaTeX HTML로 변환 ([ ] 안이 수식)
export function renderMathText(text) {
  const parts = text.split(/(\[[^\]]+\])/g)
  return parts.map((part, i) => {
    if (part.startsWith('[') && part.endsWith(']')) {
      const inner = part.slice(1, -1)
      try {
        return { type: 'math', html: katex.renderToString(hwpToLatex(inner), { throwOnError: false, displayMode: false }), key: i }
      } catch {
        return { type: 'text', text: part, key: i }
      }
    }
    return { type: 'text', text: part, key: i }
  })
}
```

- [ ] **Step 2: 팔레트 데이터 정의**

같은 파일에 이어서 팔레트 데이터 추가:

```jsx
const PALETTE = {
  기본: [
    { label: 'a/b', insert: '{} over {}', cursor: 1 },
    { label: '√', insert: 'sqrt {}', cursor: 6 },
    { label: 'xⁿ', insert: '^{}', cursor: 2 },
    { label: 'xₙ', insert: '_{}', cursor: 2 },
    { label: '( )', insert: 'left ( right )', cursor: 7 },
    { label: '[ ]', insert: 'left [ right ]', cursor: 7 },
    { label: '{ }', insert: 'left \\{ right \\}', cursor: 8 },
    { label: '×', insert: 'TIMES', cursor: 0 },
    { label: '÷', insert: 'DIVIDE', cursor: 0 },
    { label: '±', insert: 'PM', cursor: 0 },
    { label: '·', insert: 'CDOT', cursor: 0 },
    { label: '≠', insert: 'NEQ', cursor: 0 },
    { label: '≤', insert: 'LEQ', cursor: 0 },
    { label: '≥', insert: 'GEQ', cursor: 0 },
    { label: '∞', insert: 'INFINITY', cursor: 0 },
  ],
  그리스: [
    { label: 'π', insert: 'PI', cursor: 0 },
    { label: 'α', insert: 'ALPHA', cursor: 0 },
    { label: 'β', insert: 'BETA', cursor: 0 },
    { label: 'θ', insert: 'THETA', cursor: 0 },
    { label: 'δ', insert: 'DELTA', cursor: 0 },
    { label: 'σ', insert: 'SIGMA', cursor: 0 },
    { label: 'ω', insert: 'OMEGA', cursor: 0 },
  ],
  함수: [
    { label: 'sin', insert: 'sin', cursor: 0 },
    { label: 'cos', insert: 'cos', cursor: 0 },
    { label: 'tan', insert: 'tan', cursor: 0 },
    { label: 'log', insert: 'log', cursor: 0 },
    { label: 'ln', insert: 'ln', cursor: 0 },
    { label: '∫', insert: 'INT', cursor: 0 },
    { label: 'Σ', insert: 'SUM', cursor: 0 },
    { label: 'Π', insert: 'PROD', cursor: 0 },
    { label: 'lim', insert: 'LIM', cursor: 0 },
  ],
}

const BOX_INSERTS = [
  { label: '조건박스', text: '\n===조건박스===\n\n===조건박스끝===\n' },
  { label: '보기박스(2단)', text: '\n===보기박스1===\n\n===보기박스끝===\n' },
  { label: '보기박스(1단)', text: '\n===보기박스2===\n\n===보기박스끝===\n' },
  { label: '보기박스(좁은)', text: '\n===보기박스3===\n\n===보기박스끝===\n' },
  { label: '선지(짧은)', text: '\n① \t② \t③ \n④ \t⑤ \n' },
  { label: '선지(긴)', text: '\n① \n② \n③ \n④ \n⑤ \n' },
]
```

- [ ] **Step 3: FormulaEditor 컴포넌트 본체 작성**

같은 파일에 이어서:

```jsx
/**
 * FormulaEditor
 * props:
 *   value: string — 현재 편집 텍스트
 *   onChange: (newValue: string) => void
 *   onSave: () => void
 *   onCancel: () => void
 */
export default function FormulaEditor({ value, onChange, onSave, onCancel }) {
  const [activeCategory, setActiveCategory] = useState('기본')
  const textareaRef = useRef(null)

  // 팔레트 버튼 클릭: 커서 위치에 삽입
  const insertAtCursor = useCallback((insertText, cursorOffset) => {
    const ta = textareaRef.current
    if (!ta) return
    const start = ta.selectionStart
    const end = ta.selectionEnd
    const newVal = value.slice(0, start) + insertText + value.slice(end)
    onChange(newVal)
    // 커서 위치 조정 (cursorOffset=0이면 insertText 끝, else 내부 위치)
    const newCursor = cursorOffset > 0 ? start + cursorOffset : start + insertText.length
    requestAnimationFrame(() => {
      ta.focus()
      ta.setSelectionRange(newCursor, newCursor)
    })
  }, [value, onChange])

  // 렌더링 미리보기
  const previewParts = renderMathText(value)

  return (
    <div className="rounded-xl border border-gray-200 dark:border-[#353844] overflow-hidden bg-white dark:bg-[#22252E]">
      {/* 팔레트 카테고리 탭 */}
      <div className="flex items-center gap-1 px-3 pt-3 pb-0 flex-wrap">
        {Object.keys(PALETTE).map(cat => (
          <button key={cat} onClick={() => setActiveCategory(cat)}
            className={`px-3 py-1 rounded-t text-xs font-semibold border-b-2 transition-colors ${
              activeCategory === cat
                ? 'border-violet-500 text-violet-600 dark:text-violet-400'
                : 'border-transparent text-gray-500 dark:text-[#5A5E70] hover:text-gray-700'
            }`}>
            {cat}
          </button>
        ))}
      </div>

      {/* 팔레트 버튼들 */}
      <div className="px-3 py-2 bg-gray-50 dark:bg-[#2A2D38] border-b border-gray-200 dark:border-[#353844] flex flex-wrap gap-1">
        {PALETTE[activeCategory].map((btn, i) => (
          <button key={i}
            onClick={() => insertAtCursor(btn.insert, btn.cursor)}
            className="px-2.5 py-1 rounded border border-gray-200 dark:border-[#353844] bg-white dark:bg-[#22252E] text-gray-700 dark:text-[#E2E4F0] text-sm hover:border-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 font-serif">
            {btn.label}
          </button>
        ))}
      </div>

      {/* 구조 삽입 버튼들 */}
      <div className="px-3 py-2 bg-gray-50 dark:bg-[#2A2D38] border-b border-gray-200 dark:border-[#353844] flex flex-wrap gap-1">
        <span className="text-xs text-gray-400 dark:text-[#5A5E70] mr-1 self-center">구조:</span>
        {BOX_INSERTS.map((btn, i) => (
          <button key={i}
            onClick={() => insertAtCursor(btn.text, 0)}
            className="px-2.5 py-1 rounded border border-dashed border-gray-300 dark:border-[#454854] text-gray-500 dark:text-[#6A6E80] text-xs hover:border-violet-400 hover:text-violet-600 dark:hover:text-violet-400">
            {btn.label}
          </button>
        ))}
      </div>

      {/* 텍스트 에디터 */}
      <div className="px-3 pt-2 pb-1">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full min-h-[120px] bg-gray-50 dark:bg-[#1A1D24] border border-gray-200 dark:border-[#353844] rounded-lg text-sm text-gray-800 dark:text-[#E2E4F0] font-mono p-2.5 outline-none resize-y focus:border-violet-400"
          placeholder="텍스트를 입력하세요. 수식은 [수식코드] 형태로 입력합니다."
        />
      </div>

      {/* 미리보기 */}
      <div className="mx-3 mb-2 p-3 bg-white dark:bg-[#f8f8f8] rounded-lg border border-gray-200 text-sm text-gray-900 leading-loose min-h-[60px]">
        <div className="text-xs text-gray-400 mb-1">미리보기</div>
        <div>
          {previewParts.map(part =>
            part.type === 'math'
              ? <span key={part.key} dangerouslySetInnerHTML={{ __html: part.html }} />
              : <span key={part.key} style={{ whiteSpace: 'pre-wrap' }}>{part.text}</span>
          )}
        </div>
      </div>

      {/* 저장/취소 */}
      <div className="flex gap-2 px-3 pb-3">
        <button onClick={onCancel}
          className="flex-1 py-2 rounded-lg border border-gray-200 dark:border-[#353844] text-sm text-gray-500 dark:text-[#5A5E70] hover:bg-gray-50 dark:hover:bg-[#2A2D38]">
          취소
        </button>
        <button onClick={onSave}
          className="flex-1 py-2 rounded-lg text-sm font-semibold text-white bg-gradient-to-r from-violet-600 to-purple-700 hover:from-violet-500">
          저장
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 개발 서버에서 직접 확인**

브라우저 localhost:5173에서 스캔 탭 열고, FormulaEditor가 정상 임포트되는지는 다음 단계(Task 4)에서 확인. 현재 단계에서는 구문 오류가 없는지 확인:

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution/frontend"
npx vite build --mode development 2>&1 | grep -E "error|Error" | head -10
# Expected: 에러 없음 (exit 0 또는 빈 출력)
```

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/components/FormulaEditor.jsx
git commit -m "feat: HWP 수식 팔레트 + KaTeX 실시간 미리보기 FormulaEditor 컴포넌트 추가"
```

---

## Task 3: ProblemReviewer 컴포넌트

**Files:**
- Create: `frontend/src/components/ProblemReviewer.jsx`

현재 CropEditor 확정 후 바로 처리가 시작되는데, 그 사이에 문제별 포함/제외 검토 화면을 추가한다.

- [ ] **Step 1: ProblemReviewer 컴포넌트 작성**

`frontend/src/components/ProblemReviewer.jsx` 생성:

```jsx
import { useState, useEffect, useRef } from 'react'

/**
 * ProblemReviewer
 * props:
 *   pages: [{page_index, image_base64, media_type, bboxes}]
 *   bboxes: [{id, page_index, x, y, w, h, label, selected}]
 *   onConfirm: (selectedBboxes) => void  — 처리 시작
 *   onBack: () => void  — 크롭 편집으로 돌아가기
 */
export default function ProblemReviewer({ pages, bboxes, onConfirm, onBack }) {
  const [inclusions, setInclusions] = useState(
    () => Object.fromEntries(bboxes.map(b => [b.id, b.selected !== false]))
  )
  const [currentIdx, setCurrentIdx] = useState(0)
  const [cropUrls, setCropUrls] = useState({})  // {id: dataUrl}
  const canvasRef = useRef(null)

  const items = bboxes  // 순서 유지

  // 모든 문제의 크롭 이미지 생성 (canvas 사용)
  useEffect(() => {
    const generate = async () => {
      const urls = {}
      for (const bb of items) {
        const page = pages.find(p => p.page_index === bb.page_index)
        if (!page) continue
        try {
          const url = await cropToDataUrl(
            page.image_base64, page.media_type,
            bb.x, bb.y, bb.w, bb.h
          )
          urls[bb.id] = url
        } catch { /* 실패 시 원본 표시 */ }
      }
      setCropUrls(urls)
    }
    generate()
  }, [items, pages])

  const current = items[currentIdx]
  const included = current ? inclusions[current.id] : false
  const includedCount = Object.values(inclusions).filter(Boolean).length

  const toggleCurrent = (val) => {
    if (!current) return
    setInclusions(prev => ({ ...prev, [current.id]: val }))
  }

  const selectAll = (val) => {
    setInclusions(Object.fromEntries(items.map(b => [b.id, val])))
  }

  const handleConfirm = () => {
    const selected = items.filter(b => inclusions[b.id])
    onConfirm(selected)
  }

  const isDark = document.documentElement.classList.contains('dark')
  const colors = isDark
    ? { bg: '#22252E', card: '#2A2D38', border: '#353844', text: '#E2E4F0', muted: '#5A5E70', accent: '#8B5CF6' }
    : { bg: '#F4F5F7', card: '#FFFFFF', border: '#DDE1E9', text: '#374151', muted: '#9AA0B0', accent: '#0EA5E9' }

  return (
    <div style={{ background: colors.bg, borderRadius: 12, border: `1px solid ${colors.border}`, overflow: 'hidden' }}>
      {/* 헤더 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: colors.card, borderBottom: `1px solid ${colors.border}` }}>
        <button onClick={onBack}
          style={{ fontSize: 12, color: colors.muted, background: 'none', border: 'none', cursor: 'pointer' }}>
          ← 크롭 수정
        </button>
        <span style={{ fontSize: 14, fontWeight: 700, color: colors.text }}>문제 검토</span>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: colors.muted }}>
          {includedCount}/{items.length}개 포함
        </span>
        <button onClick={() => selectAll(true)}
          style={{ fontSize: 11, padding: '3px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, background: 'transparent', color: colors.muted, cursor: 'pointer' }}>
          전체 포함
        </button>
        <button onClick={() => selectAll(false)}
          style={{ fontSize: 11, padding: '3px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, background: 'transparent', color: colors.muted, cursor: 'pointer' }}>
          전체 제외
        </button>
      </div>

      {/* 본문: 크롭 이미지 + 포함/제외 */}
      <div style={{ display: 'flex', minHeight: 400 }}>
        {/* 메인 뷰어 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, gap: 16 }}>
          {current ? (
            <>
              {/* 크롭 이미지 */}
              <div style={{ border: `3px solid ${included ? colors.accent : '#6B7280'}`, borderRadius: 10, overflow: 'hidden', maxWidth: '100%', opacity: included ? 1 : 0.5, transition: 'all .2s' }}>
                {cropUrls[current.id] ? (
                  <img src={cropUrls[current.id]} alt={current.label}
                    style={{ display: 'block', maxWidth: 480, maxHeight: 360, objectFit: 'contain' }} />
                ) : (
                  <div style={{ width: 480, height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.muted, fontSize: 13 }}>
                    로딩 중...
                  </div>
                )}
              </div>

              {/* 라벨 */}
              <div style={{ fontSize: 14, fontWeight: 600, color: colors.text }}>{current.label}</div>

              {/* 포함/제외 버튼 */}
              <div style={{ display: 'flex', gap: 10 }}>
                <button onClick={() => toggleCurrent(true)}
                  style={{ padding: '8px 28px', borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: 'pointer',
                    border: `2px solid ${included ? colors.accent : colors.border}`,
                    background: included ? `${colors.accent}22` : 'transparent',
                    color: included ? colors.accent : colors.muted,
                    transition: 'all .15s' }}>
                  ✓ 포함
                </button>
                <button onClick={() => toggleCurrent(false)}
                  style={{ padding: '8px 28px', borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: 'pointer',
                    border: `2px solid ${!included ? '#EF4444' : colors.border}`,
                    background: !included ? '#EF444422' : 'transparent',
                    color: !included ? '#EF4444' : colors.muted,
                    transition: 'all .15s' }}>
                  ✕ 제외
                </button>
              </div>

              {/* prev/next */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <button onClick={() => setCurrentIdx(i => Math.max(0, i - 1))} disabled={currentIdx === 0}
                  style={{ padding: '6px 18px', borderRadius: 7, fontSize: 13, fontWeight: 600, cursor: currentIdx === 0 ? 'not-allowed' : 'pointer',
                    border: `1px solid ${colors.border}`, background: 'transparent', color: colors.muted, opacity: currentIdx === 0 ? 0.4 : 1 }}>
                  ◀ 이전
                </button>
                <span style={{ fontSize: 12, color: colors.muted }}>{currentIdx + 1} / {items.length}</span>
                <button onClick={() => setCurrentIdx(i => Math.min(items.length - 1, i + 1))} disabled={currentIdx === items.length - 1}
                  style={{ padding: '6px 18px', borderRadius: 7, fontSize: 13, fontWeight: 600, cursor: currentIdx === items.length - 1 ? 'not-allowed' : 'pointer',
                    border: `1px solid ${colors.border}`, background: 'transparent', color: colors.muted, opacity: currentIdx === items.length - 1 ? 0.4 : 1 }}>
                  다음 ▶
                </button>
              </div>
            </>
          ) : (
            <div style={{ color: colors.muted, fontSize: 14 }}>문제가 없습니다.</div>
          )}
        </div>

        {/* 사이드바: 문제 목록 */}
        <div style={{ width: 180, borderLeft: `1px solid ${colors.border}`, overflowY: 'auto', background: colors.bg }}>
          {items.map((bb, idx) => (
            <div key={bb.id} onClick={() => setCurrentIdx(idx)}
              style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', cursor: 'pointer', fontSize: 12,
                borderBottom: `1px solid ${colors.border}`,
                background: idx === currentIdx ? `${colors.accent}15` : 'transparent',
                color: inclusions[bb.id] ? colors.text : colors.muted }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                background: inclusions[bb.id] ? colors.accent : '#6B7280' }} />
              <span style={{ flex: 1 }}>{bb.label}</span>
              {!inclusions[bb.id] && <span style={{ fontSize: 10, color: '#EF4444' }}>제외</span>}
            </div>
          ))}
        </div>
      </div>

      {/* 처리 시작 버튼 */}
      <div style={{ padding: 16, borderTop: `1px solid ${colors.border}`, background: colors.card }}>
        <button onClick={handleConfirm} disabled={includedCount === 0}
          style={{ width: '100%', padding: '12px 0', borderRadius: 9, fontWeight: 700, fontSize: 14, color: 'white',
            background: `linear-gradient(to right, ${colors.accent}, ${isDark ? '#6D28D9' : '#0284C7'})`,
            border: 'none', cursor: includedCount === 0 ? 'not-allowed' : 'pointer', opacity: includedCount === 0 ? 0.4 : 1 }}>
          ✦ {includedCount}개 문제 처리 시작
        </button>
      </div>
    </div>
  )
}

// Canvas로 이미지 영역 크롭 → dataURL
function cropToDataUrl(base64, mediaType, x, y, w, h) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      const sw = img.naturalWidth, sh = img.naturalHeight
      canvas.width = Math.round(sw * w)
      canvas.height = Math.round(sh * h)
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, Math.round(sw * x), Math.round(sh * y), canvas.width, canvas.height, 0, 0, canvas.width, canvas.height)
      resolve(canvas.toDataURL('image/jpeg', 0.92))
    }
    img.onerror = reject
    img.src = `data:${mediaType};base64,${base64}`
  })
}
```

- [ ] **Step 2: 빌드 확인**

```bash
cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution/frontend"
npx vite build --mode development 2>&1 | grep -E "error|Error" | head -10
# Expected: 에러 없음
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/ProblemReviewer.jsx
git commit -m "feat: 문제별 포함/제외 검토 ProblemReviewer 컴포넌트 추가"
```

---

## Task 4: TabScan + ScanResultCard 연결

**Files:**
- Modify: `frontend/src/components/TabScan.jsx`
- Modify: `frontend/src/components/ScanResultCard.jsx`

- [ ] **Step 1: TabScan.jsx에 'reviewing' step + ProblemReviewer 추가**

`frontend/src/components/TabScan.jsx` 상단 import 수정:

```jsx
import { useState, useCallback, useEffect } from 'react'
import CropEditor from './CropEditor'
import ProblemReviewer from './ProblemReviewer'
import ScanResultCard from './ScanResultCard'
```

`step` 주석 업데이트 (line 9):
```jsx
const [step, setStep] = useState('upload')  // upload | detecting | editing | reviewing | processing | done
```

`handleConfirm` 함수를 아래로 교체 (CropEditor에서 '확정' 누르면 reviewing으로 전환):

```jsx
const handleConfirm = (bboxes) => {
  setConfirmedBboxes(bboxes)
  setStep('reviewing')
}
```

`handleProcess` 함수는 그대로 유지 (ProblemReviewer에서 호출).

`handleResultChange` 함수 추가 (ScanResultCard 편집 콜백):

```jsx
const handleResultChange = useCallback((problemId, newResult) => {
  setCards(prev => prev.map(c => c.problemId === problemId ? { ...c, result: newResult } : c))
}, [])
```

JSX에서 `{/* ── 2단계: 크롭 수정 ── */}` 블록 바로 아래에 reviewing 단계 추가:

```jsx
{/* ── 3단계: 문제 검토 ── */}
{step === 'reviewing' && detectData && confirmedBboxes.length > 0 && (
  <>
    <div className="flex items-center gap-3 mb-2">
      <h2 className="text-base font-semibold text-gray-700 dark:text-[#E2E4F0]">문제 검토</h2>
    </div>
    <ProblemReviewer
      pages={detectData.pages}
      bboxes={confirmedBboxes}
      onConfirm={(selected) => handleProcess(selected)}
      onBack={() => setStep('editing')}
    />
  </>
)}
```

`ScanResultCard` 렌더링에 `onResultChange` prop 추가:

```jsx
{cards.map(card => (
  <ScanResultCard
    key={card.problemId}
    {...card}
    model={model}
    grade={grade}
    onResultChange={handleResultChange}
  />
))}
```

- [ ] **Step 2: ScanResultCard.jsx에 FormulaEditor 인라인 편집 추가**

`frontend/src/components/ScanResultCard.jsx` import 수정:

```jsx
import { useState } from 'react'
import SolutionDisplay from './SolutionDisplay'
import FormulaEditor from './FormulaEditor'
```

`export default function ScanResultCard({ ..., onResultChange })` 에 `onResultChange` prop 추가.

컴포넌트 내부에 편집 상태 추가:

```jsx
const [editing, setEditing] = useState(false)
const [draftResult, setDraftResult] = useState(result || '')
```

`result` prop이 바뀔 때 draft 동기화:

```jsx
useEffect(() => {
  setDraftResult(result || '')
}, [result])
```

(이미 `import { useState } from 'react'` 가 있으므로 `useEffect`도 추가 필요)

헤더의 done 상태 버튼 영역에 ✎ 수정 버튼 추가 (기존 `+ 해설 추가`, `+ 유사문항` 버튼 앞에):

```jsx
{status === 'done' && result && (
  <button
    onClick={e => { e.stopPropagation(); setEditing(e => !e) }}
    className="text-xs px-3 py-1 rounded-lg border border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#A0A4B8] hover:bg-gray-100 dark:hover:bg-[#353844]">
    {editing ? '✕ 닫기' : '✎ 수정'}
  </button>
)}
```

본문 `{open && status === 'done' && result && (` 블록에서 SolutionDisplay 위에 FormulaEditor 조건부 추가:

```jsx
{open && status === 'done' && (
  <div className="p-4 bg-white dark:bg-[#22252E]">
    {editing ? (
      <FormulaEditor
        value={draftResult}
        onChange={setDraftResult}
        onSave={() => {
          onResultChange?.(problemId, draftResult)
          setEditing(false)
        }}
        onCancel={() => {
          setDraftResult(result || '')
          setEditing(false)
        }}
      />
    ) : (
      result && <SolutionDisplay solution={result} graphs={graphs} title={label} />
    )}
    {/* ... 기존 extraError, extraResult ... */}
  </div>
)}
```

- [ ] **Step 3: `useEffect` import 추가 (ScanResultCard.jsx)**

ScanResultCard.jsx 상단:
```jsx
import { useState, useEffect } from 'react'
```

- [ ] **Step 4: 개발 서버에서 E2E 흐름 확인**

1. localhost:5173 → 스캔 탭
2. 이미지/PDF 업로드 → 분석 시작
3. CropEditor에서 크롭 확정 → ProblemReviewer 화면 열림 확인
4. 각 문제 prev/next, 포함/제외 토글 동작 확인
5. "처리 시작" → 기존 processing 흐름 확인
6. 결과 카드에서 "✎ 수정" 클릭 → FormulaEditor 열림 확인
7. `[{a} over {b}]` 입력 → 미리보기에 분수 렌더링 확인
8. 저장 → SolutionDisplay로 복귀 확인

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/components/TabScan.jsx frontend/src/components/ScanResultCard.jsx
git commit -m "feat: 스캔 흐름에 ProblemReviewer + FormulaEditor 인라인 편집 연결"
```

---

## 자가 검토

### Spec 커버리지
- [x] 문제 하나씩 크롭 확대 화면 → ProblemReviewer + cropToDataUrl
- [x] 포함/제외 토글 (상호 배타적) → included 상태 단일 boolean
- [x] 전체 포함/전체 제외 → selectAll 함수
- [x] prev/next 화살표 + 사이드바 목록 → currentIdx state
- [x] 결과에서 수정 가능 → ScanResultCard editing mode
- [x] HWP 수식 팔레트 입력 → FormulaEditor 팔레트
- [x] 실시간 수식 렌더링 미리보기 → KaTeX renderMathText
- [x] 보기박스/조건박스 구조 삽입 → BOX_INSERTS + hwpx_service 마커 치환
- [x] HWPX 다운로드 시 편집된 텍스트 사용 → handleResultChange가 cards 업데이트

### Placeholder 없음 확인
- 모든 코드 블록에 실제 구현 포함 ✓
- 테스트 명령어에 예상 결과 포함 ✓

### 타입 일관성
- `onConfirm(selected)` → Task 3 ProblemReviewer → Task 4 TabScan `handleProcess(selected)` ✓
- `onResultChange(problemId, newResult)` → Task 4 ScanResultCard → TabScan handleResultChange ✓
- `cropToDataUrl(base64, mediaType, x, y, w, h)` → Task 3 내부 함수 ✓
