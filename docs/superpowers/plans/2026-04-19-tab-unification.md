# Tab Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "유사문항 생성" 탭과 "한글 파일" 탭을 하나의 탭으로 통합 — 첫 화면에서 입력 방식(이미지 vs 한글 파일)을 선택한 뒤 해당 UI로 진입.

**Architecture:** `TabCreateVariant.jsx`를 모드 선택 shell로 재작성. 기존 이미지 입력 UI는 `ImageInputMode.jsx`로 추출. 기존 `TabHwpx.jsx` 내용은 `HwpxInputMode.jsx`로 이동 (HWP 자동 변환 지원 추가). `App.jsx`에서 `hwpx` 탭 항목 제거. 백엔드에 `/api/hwpx-convert` + `/api/system-info` 엔드포인트 추가.

**Tech Stack:** React 18, Vite, FastAPI, python-docx/win32com (HWP→HWPX 변환)

---

## File Map

| 파일 | 변경 내용 |
|------|-----------|
| `frontend/src/components/TabCreateVariant.jsx` | 완전 재작성 — 모드 선택 shell |
| `frontend/src/components/ImageInputMode.jsx` | 신규 — 기존 TabCreateVariant 내용 이동 |
| `frontend/src/components/HwpxInputMode.jsx` | 신규 — 기존 TabHwpx 내용 이동 + HWP 지원 |
| `frontend/src/App.jsx` | hwpx 탭 제거, TabHwpx import 제거 |
| `backend/main.py` | `/api/hwpx-convert`, `/api/system-info` 추가 |

---

### Task 1: ImageInputMode.jsx 생성 (기존 TabCreateVariant 내용 이동)

**Files:**
- Create: `frontend/src/components/ImageInputMode.jsx`

현재 `TabCreateVariant.jsx`의 전체 로직(이미지 업로드, 유사문항 생성, 수정 요청)을 그대로 새 파일로 옮긴다. props 시그니처는 `{ grade, model, guidelines }`로 동일.

- [ ] **Step 1: ImageInputMode.jsx 생성**

```jsx
import { useState, useCallback } from 'react'
import ImageUploadBox from './ImageUploadBox'
import SolutionDisplay from './SolutionDisplay'
import UsageInfo from './UsageInfo'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const TYPES = [
  { value: 'number', label: '숫자 변형' },
  { value: 'idea', label: '아이디어 변형' },
]
const DIFFS = [
  { value: 'easier', label: '더 쉽게' },
  { value: 'similar', label: '비슷하게' },
  { value: 'harder', label: '더 어렵게' },
]

export default function ImageInputMode({ grade, model, guidelines }) {
  const [problemPreview, setProblemPreview] = useState(null)
  const [problemFile, setProblemFile] = useState(null)
  const [solutionPreview, setSolutionPreview] = useState(null)
  const [solutionFile, setSolutionFile] = useState(null)
  const [dragging, setDragging] = useState(null)

  const [variantType, setVariantType] = useState('idea')
  const [difficulty, setDifficulty] = useState('similar')
  const [customPrompt, setCustomPrompt] = useState('')
  const [result, setResult] = useState(null)
  const [graphs, setGraphs] = useState([])
  const [usage, setUsage] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const [refineText, setRefineText] = useState('')
  const [isRefining, setIsRefining] = useState(false)

  const handleFile = useCallback((f, type) => {
    if (!f || !f.type.startsWith('image/')) return
    const reader = new FileReader()
    if (type === 'problem') {
      setProblemFile(f); reader.onload = (e) => setProblemPreview(e.target.result)
    } else {
      setSolutionFile(f); reader.onload = (e) => setSolutionPreview(e.target.result)
    }
    reader.readAsDataURL(f)
    setResult(null)
  }, [])

  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        handleFile(item.getAsFile(), !problemFile ? 'problem' : 'solution')
        break
      }
    }
  }, [handleFile, problemFile])

  const handleReset = () => {
    setProblemPreview(null); setProblemFile(null)
    setSolutionPreview(null); setSolutionFile(null)
    setResult(null); setGraphs([]); setUsage(null); setError(null)
    setRefineText('')
  }

  const handleGenerate = async () => {
    setIsLoading(true); setError(null); setResult(null)
    try {
      const formData = new FormData()
      formData.append('files', problemFile)
      formData.append('files', solutionFile)
      const params = new URLSearchParams({ variant_type: variantType, difficulty, model, grade })
      const fullPrompt = [guidelines, customPrompt.trim()].filter(Boolean).join('\n\n')
      if (fullPrompt) params.set('custom_prompt', fullPrompt)

      const res = await fetch(`${API}/api/generate?${params}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '생성 실패')
      const data = await res.json()
      setResult(data.result)
      setGraphs(data.graphs || [])
      setUsage(data.usage)
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
  }

  const handleRefine = async () => {
    if (!refineText.trim() || !result) return
    setIsRefining(true); setError(null)
    try {
      const res = await fetch(`${API}/api/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ original_result: result, instruction: refineText.trim(), model }),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '수정 실패')
      const data = await res.json()
      setResult(data.result)
      setGraphs(data.graphs || [])
      setUsage(data.usage)
      setRefineText('')
    } catch (err) { setError(err.message) }
    finally { setIsRefining(false) }
  }

  const ready = problemFile && solutionFile

  return (
    <div className="space-y-4" onPaste={handlePaste} tabIndex={0}>
      <div className="flex gap-3">
        <ImageUploadBox
          preview={problemPreview} label="원본 문제" icon="📝"
          isDragging={dragging === 'problem'}
          onFile={(f) => handleFile(f, 'problem')}
          onDragState={(v) => setDragging(v ? 'problem' : null)}
        />
        <ImageUploadBox
          preview={solutionPreview} label="원본 해설" icon="📖"
          isDragging={dragging === 'solution'}
          onFile={(f) => handleFile(f, 'solution')}
          onDragState={(v) => setDragging(v ? 'solution' : null)}
        />
      </div>

      {ready && (
        <div className="p-4 bg-indigo-50 dark:bg-indigo-500/5 rounded-xl border border-indigo-200 dark:border-indigo-500/20 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs font-semibold text-gray-500 dark:text-[#8a8f98] uppercase tracking-wide">변형 유형</span>
            {TYPES.map((t) => (
              <button key={t.value} onClick={() => setVariantType(t.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  variantType === t.value
                    ? 'bg-indigo-600 dark:bg-indigo-500 text-white'
                    : 'bg-white dark:bg-[#141516] text-gray-600 dark:text-[#8a8f98] border border-gray-200 dark:border-[rgba(255,255,255,0.08)] hover:bg-gray-50 dark:hover:bg-[#1a1a1c]'
                }`}>{t.label}</button>
            ))}
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs font-semibold text-gray-500 dark:text-[#8a8f98] uppercase tracking-wide">난이도</span>
            {DIFFS.map((d) => (
              <button key={d.value} onClick={() => setDifficulty(d.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  difficulty === d.value
                    ? 'bg-violet-600 dark:bg-violet-500 text-white'
                    : 'bg-white dark:bg-[#141516] text-gray-600 dark:text-[#8a8f98] border border-gray-200 dark:border-[rgba(255,255,255,0.08)] hover:bg-gray-50 dark:hover:bg-[#1a1a1c]'
                }`}>{d.label}</button>
            ))}
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-500 dark:text-[#8a8f98] uppercase tracking-wide block mb-1.5">
              추가 지시사항 <span className="normal-case font-normal text-gray-400">(선택)</span>
            </label>
            <input type="text"
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="예: 로그 밑을 3 대신 2로 바꿔서 / 조건에 절댓값 추가"
              className="w-full px-3 py-2.5 border border-indigo-200 dark:border-[rgba(255,255,255,0.08)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500 bg-white dark:bg-[#141516] text-gray-700 dark:text-[#f7f8f8] placeholder:text-gray-400 dark:placeholder:text-[#4a4a52] transition-colors"
            />
          </div>

          <div className="flex gap-2.5">
            <button onClick={handleGenerate} disabled={isLoading}
              className="flex-1 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg font-semibold text-sm hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all shadow-[0_2px_12px_rgba(108,127,255,0.25)] hover:shadow-[0_4px_20px_rgba(108,127,255,0.35)] disabled:shadow-none">
              {isLoading ? '생성 중... (30초~1분)' : '✦ 유사문항 생성'}
            </button>
            <button onClick={handleReset}
              className="px-4 py-2.5 bg-gray-100 dark:bg-[#141516] text-gray-600 dark:text-[#8a8f98] border border-gray-200 dark:border-[rgba(255,255,255,0.08)] rounded-lg text-sm font-medium hover:bg-gray-200 dark:hover:bg-[#1a1a1c] transition-colors">
              초기화
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 rounded-lg text-sm border border-red-200 dark:border-red-500/20">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="text-center py-10">
          <div className="inline-block w-8 h-8 border-[3px] border-indigo-200 dark:border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
          <p className="text-gray-400 dark:text-[#8a8f98] text-sm mt-3">원본 해설 방향 그대로 유사문항 풀이 작성 중...</p>
        </div>
      )}

      {result && (
        <>
          <SolutionDisplay solution={result} graphs={graphs} title="유사문항 & 해설" />
          <UsageInfo usage={usage} />

          <div className="p-4 bg-amber-50 dark:bg-amber-500/5 rounded-xl border border-amber-200 dark:border-amber-500/20">
            <label className="text-xs font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wide block mb-2">
              수정 요청
            </label>
            <div className="flex gap-2">
              <input type="text"
                value={refineText}
                onChange={(e) => setRefineText(e.target.value)}
                placeholder="예: 조건을 더 단순하게 / 답을 다른 값으로"
                className="flex-1 px-3 py-2.5 border border-amber-200 dark:border-amber-500/20 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/30 bg-white dark:bg-[#141516] text-gray-700 dark:text-[#f7f8f8] placeholder:text-gray-400 dark:placeholder:text-[#4a4a52]"
              />
              <button onClick={handleRefine} disabled={isRefining || !refineText.trim()}
                className="px-4 py-2 bg-amber-500 dark:bg-amber-600 text-white rounded-lg text-sm font-semibold hover:bg-amber-600 dark:hover:bg-amber-500 disabled:opacity-50 transition-colors whitespace-nowrap">
                {isRefining ? '수정 중...' : '수정'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/ImageInputMode.jsx
git commit -m "feat: extract ImageInputMode from TabCreateVariant"
```

---

### Task 2: 백엔드 — /api/system-info + /api/hwpx-convert 추가

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: main.py 상단에 win32com 가용성 확인 코드 추가**

`backend/main.py` 파일 상단의 import 블록 아래(app 생성 전)에 추가:

```python
# HWP 변환기 가용성 사전 확인 (서버 시작 시 1회)
_hwp_converter_available = False
try:
    import win32com.client  # noqa: F401
    _hwp_converter_available = True
except ImportError:
    pass
```

- [ ] **Step 2: /api/system-info 엔드포인트 추가**

`backend/main.py`의 라우터 섹션(첫 번째 `@app.get` 또는 `@app.post` 직전)에 추가:

```python
@app.get("/api/system-info")
async def system_info():
    return {"hwp_converter_available": _hwp_converter_available}
```

- [ ] **Step 3: /api/hwpx-convert 엔드포인트 추가**

같은 위치에 추가:

```python
@app.post("/api/hwpx-convert")
async def hwpx_convert(file: UploadFile = File(...)):
    if not _hwp_converter_available:
        raise HTTPException(status_code=400, detail="HWP 변환기를 사용할 수 없습니다. 한글 프로그램이 설치된 Windows 환경에서만 지원됩니다.")
    import tempfile, shutil, win32com.client
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ('.hwp',):
        raise HTTPException(status_code=400, detail="HWP 파일만 변환 가능합니다.")
    tmp_dir = tempfile.mkdtemp()
    try:
        src = Path(tmp_dir) / file.filename
        with open(src, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        dst = src.with_suffix('.hwpx')
        hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        hwp.Open(str(src), "HWP", "forceopen:true")
        hwp.SaveAs(str(dst), "HWPX")
        hwp.Quit()
        if not dst.exists():
            raise HTTPException(status_code=500, detail="HWP → HWPX 변환 실패")
        hwpx_bytes = dst.read_bytes()
        filename = dst.name
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    from fastapi.responses import Response
    return Response(
        content=hwpx_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: 서버 재시작 후 /api/system-info 동작 확인**

터미널에서:
```bash
curl http://localhost:8001/api/system-info
```
Expected: `{"hwp_converter_available": true}` 또는 `{"hwp_converter_available": false}`

- [ ] **Step 5: 커밋**

```bash
git add backend/main.py
git commit -m "feat: add /api/system-info and /api/hwpx-convert endpoints"
```

---

### Task 3: HwpxInputMode.jsx 생성 (TabHwpx 내용 이동 + HWP 지원 추가)

**Files:**
- Create: `frontend/src/components/HwpxInputMode.jsx`

기존 `TabHwpx.jsx`의 전체 내용을 이동하되, 두 가지를 추가한다:
1. 파일 수락을 `.hwpx,.hwp`으로 확장
2. `.hwp` 파일 업로드 시 `/api/hwpx-convert`를 먼저 호출해 HWPX Blob을 받은 뒤 기존 분석 흐름 진행
3. `hwpConverterAvailable` prop으로 win32com 가용성 배너 제어

- [ ] **Step 1: HwpxInputMode.jsx 생성**

```jsx
import { useState } from 'react'
import LatexRenderer from './LatexRenderer'
import UsageInfo from './UsageInfo'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const TYPES = [
  { value: 'number', label: '숫자 변형' },
  { value: 'idea', label: '아이디어 변형' },
]
const DIFFS = [
  { value: 'easier', label: '더 쉽게' },
  { value: 'similar', label: '비슷하게' },
  { value: 'harder', label: '더 어렵게' },
]

function hwpToLatex(text) {
  return text.replace(/\[([^\]]+)\]/g, (_, code) => {
    let latex = code
      .replace(/\{([^}]*)\}\s*over\s*\{([^}]*)\}/g, '\\frac{$1}{$2}')
      .replace(/sqrt\{([^}]*)\}/g, '\\sqrt{$1}')
      .replace(/left\s*\(/g, '\\left(').replace(/right\s*\)/g, '\\right)')
      .replace(/left\s*\|/g, '\\left|').replace(/right\s*\|/g, '\\right|')
      .replace(/left\s*\{/g, '\\left\\{').replace(/right\s*\}/g, '\\right\\}')
      .replace(/left\s*\[/g, '\\left[').replace(/right\s*\]/g, '\\right]')
      .replace(/\ble\b/g, '\\leq').replace(/\bge\b/g, '\\geq').replace(/\bne\b/g, '\\neq')
      .replace(/\btherefore~/g, '\\therefore\\;')
      .replace(/\bbecause~/g, '\\because\\;')
      .replace(/\bcdotscdots\b/g, '\\cdots\\cdots').replace(/\bcdots\b/g, '\\cdots')
      .replace(/\bpi\b/g, '\\pi').replace(/\btheta\b/g, '\\theta')
      .replace(/\bsigma\b/g, '\\sigma').replace(/\binf\b/g, '\\infty')
      .replace(/\balpha\b/g, '\\alpha').replace(/\bbeta\b/g, '\\beta')
      .replace(/\bgamma\b/g, '\\gamma').replace(/\bdelta\b/g, '\\delta')
      .replace(/\bomega\b/g, '\\omega')
      .replace(/\bsin`/g, '\\sin\\,').replace(/\bcos`/g, '\\cos\\,').replace(/\btan`/g, '\\tan\\,')
      .replace(/\bsin\b/g, '\\sin').replace(/\bcos\b/g, '\\cos').replace(/\btan\b/g, '\\tan')
      .replace(/\blog_\{/g, '\\log_{').replace(/\blog`/g, '\\log\\,')
      .replace(/\bln`/g, '\\ln\\,')
      .replace(/\bsum_/g, '\\sum_').replace(/\blim_/g, '\\lim_')
      .replace(/\bint_/g, '\\int_').replace(/\bint\b/g, '\\int')
      .replace(/\+-/g, '\\pm')
      .replace(/\bDEG\b/g, '^{\\circ}')
      .replace(/\bTIMES\b/g, '\\times')
      .replace(/\bLEFT\s*\(/g, '\\left(').replace(/\bRIGHT\s*\)/g, '\\right)')
      .replace(/\bLRARROW\b/g, '\\Leftrightarrow').replace(/\bRARROW\b/g, '\\Rightarrow')
      .replace(/\bTHEREFORE\b/g, '\\therefore')
      .replace(/->/g, '\\to')
      .replace(/`/g, '\\,')
      .replace(/~/g, '\\;')
    return `$${latex}$`
  })
}

export default function HwpxInputMode({ grade, model, guidelines, hwpConverterAvailable }) {
  const [file, setFile] = useState(null)
  const [fileName, setFileName] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [isConverting, setIsConverting] = useState(false)

  const [problems, setProblems] = useState(null)
  const [selectedNumbers, setSelectedNumbers] = useState(new Set())
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const [variantType, setVariantType] = useState('idea')
  const [difficulty, setDifficulty] = useState('similar')
  const [customPrompt, setCustomPrompt] = useState('')

  const [batchResults, setBatchResults] = useState(null)
  const [usage, setUsage] = useState(null)
  const [downloadId, setDownloadId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const [refineText, setRefineText] = useState('')
  const [isRefining, setIsRefining] = useState(false)

  const analyzeFile = async (f) => {
    setIsAnalyzing(true); setError(null)
    try {
      const formData = new FormData()
      formData.append('file', f)
      const res = await fetch(`${API}/api/hwpx-analyze`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '분석 실패')
      const data = await res.json()
      setProblems(data.problems)
      setSelectedNumbers(new Set(data.problems.map(p => p.number)))
    } catch (err) { setError(err.message) }
    finally { setIsAnalyzing(false) }
  }

  const convertHwpToHwpx = async (hwpFile) => {
    setIsConverting(true); setError(null)
    try {
      const formData = new FormData()
      formData.append('file', hwpFile)
      const res = await fetch(`${API}/api/hwpx-convert`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'HWP 변환 실패')
      const blob = await res.blob()
      const hwpxName = hwpFile.name.replace(/\.hwp$/i, '.hwpx')
      return new File([blob], hwpxName, { type: 'application/octet-stream' })
    } catch (err) { setError(err.message); return null }
    finally { setIsConverting(false) }
  }

  const handleFileInput = async (f) => {
    if (!f) return
    const name = f.name.toLowerCase()
    if (!name.endsWith('.hwpx') && !name.endsWith('.hwp')) return
    setBatchResults(null); setError(null); setDownloadId(null); setProblems(null)

    if (name.endsWith('.hwp')) {
      if (!hwpConverterAvailable) {
        setError('HWP 변환을 지원하지 않는 환경입니다. 한글에서 "다른 이름으로 저장 → HWPX" 후 업로드해 주세요.')
        return
      }
      setFileName(f.name)
      const converted = await convertHwpToHwpx(f)
      if (!converted) return
      setFile(converted); setFileName(converted.name)
      analyzeFile(converted)
    } else {
      setFile(f); setFileName(f.name)
      analyzeFile(f)
    }
  }

  const handleDrop = (e) => { e.preventDefault(); setIsDragging(false); handleFileInput(e.dataTransfer.files[0]) }

  const toggleNumber = (num) => {
    setSelectedNumbers(prev => { const next = new Set(prev); next.has(num) ? next.delete(num) : next.add(num); return next })
  }

  const handleGenerate = async () => {
    if (!file || selectedNumbers.size === 0) return
    setIsLoading(true); setError(null); setBatchResults(null); setDownloadId(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const params = new URLSearchParams({ variant_type: variantType, difficulty, model, grade, selected_numbers: [...selectedNumbers].join(',') })
      const fullPrompt = [guidelines, customPrompt.trim()].filter(Boolean).join('\n\n')
      if (fullPrompt) params.set('custom_prompt', fullPrompt)
      const res = await fetch(`${API}/api/hwpx-batch?${params}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '생성 실패')
      const data = await res.json()
      setBatchResults(data.results)
      setUsage(data.usage)
      setDownloadId(data.download_id)
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
  }

  const handleRefine = async (resultIndex) => {
    if (!refineText.trim() || !batchResults) return
    setIsRefining(true); setError(null)
    try {
      const res = await fetch(`${API}/api/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ original_result: batchResults[resultIndex].result, instruction: refineText.trim(), model }),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '수정 실패')
      const data = await res.json()
      setBatchResults(prev => prev.map((r, i) => i === resultIndex ? { ...r, result: data.result, usage: data.usage } : r))
      setRefineText('')
    } catch (err) { setError(err.message) }
    finally { setIsRefining(false) }
  }

  const handleDownload = () => {
    if (!downloadId) return
    window.open(`${API}/api/hwpx-download/${downloadId}`, '_blank')
  }

  const handleReset = () => {
    setFile(null); setFileName(''); setProblems(null)
    setSelectedNumbers(new Set()); setBatchResults(null); setUsage(null)
    setDownloadId(null); setError(null); setCustomPrompt(''); setRefineText('')
  }

  const acceptTypes = hwpConverterAvailable ? '.hwpx,.hwp' : '.hwpx'

  return (
    <div className="space-y-4">
      {/* HWP 미지원 안내 배너 */}
      {!hwpConverterAvailable && (
        <div className="p-3 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 rounded-lg text-xs border border-amber-200 dark:border-amber-500/20">
          이 환경에서는 HWP 직접 변환을 지원하지 않습니다. 한글에서 <strong>파일 → 다른 이름으로 저장 → HWPX</strong>로 저장 후 업로드해 주세요.
        </div>
      )}

      {/* 파일 업로드 */}
      <div
        className={`p-6 border-2 border-dashed rounded-xl text-center transition-colors ${
          isDragging
            ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10'
            : 'border-gray-300 dark:border-[rgba(255,255,255,0.08)] hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-gray-50 dark:hover:bg-indigo-500/5'
        }`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input type="file" accept={acceptTypes} onChange={(e) => handleFileInput(e.target.files[0])} className="hidden" id="hwpx-input" />
        <label htmlFor="hwpx-input" className="cursor-pointer">
          {fileName ? (
            <div>
              <p className="text-lg font-medium text-indigo-500 dark:text-indigo-400">{fileName}</p>
              {isConverting && <p className="text-sm text-amber-500 dark:text-amber-400 mt-1">HWP → HWPX 변환 중...</p>}
              {isAnalyzing && <p className="text-sm text-gray-500 dark:text-[#8a8f98] mt-1">파일 분석 중...</p>}
              {problems && <p className="text-sm text-emerald-600 dark:text-emerald-400 mt-1">{problems.length}개 문제 감지됨</p>}
            </div>
          ) : (
            <div className="py-4">
              <div className="text-3xl mb-2">📄</div>
              <p className="text-gray-600 dark:text-[#8a8f98] font-medium">
                한글 파일({hwpConverterAvailable ? '.hwp / ' : ''}.hwpx)을 드래그하거나 클릭
              </p>
              <p className="text-gray-400 dark:text-[#4a4a52] text-xs mt-2">미주 형식 자동 인식 · 여러 문제 동시 처리</p>
            </div>
          )}
        </label>
      </div>

      {/* 문제 선택 */}
      {problems && problems.length > 0 && (
        <div className="p-4 bg-white dark:bg-[#0f1011] rounded-xl border border-gray-200 dark:border-[rgba(255,255,255,0.06)] shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-gray-800 dark:text-[#f7f8f8]">문제 선택 ({selectedNumbers.size}/{problems.length})</h3>
            <div className="flex gap-2">
              <button onClick={() => setSelectedNumbers(new Set(problems.map(p => p.number)))} className="text-xs text-indigo-500 dark:text-indigo-400 hover:underline">전체 선택</button>
              <button onClick={() => setSelectedNumbers(new Set())} className="text-xs text-gray-400 dark:text-[#8a8f98] hover:underline">전체 해제</button>
            </div>
          </div>
          {problems.map((p) => (
            <label key={p.number} className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
              selectedNumbers.has(p.number)
                ? 'bg-indigo-50 dark:bg-indigo-500/10'
                : 'hover:bg-gray-50 dark:hover:bg-[#141516]'
            }`}>
              <input type="checkbox" checked={selectedNumbers.has(p.number)} onChange={() => toggleNumber(p.number)} className="mt-1 w-4 h-4 accent-indigo-500" />
              <div className="min-w-0">
                <span className="text-sm font-medium text-gray-700 dark:text-[#d0d0d5]">{p.number}번</span>
                <p className="text-xs text-gray-500 dark:text-[#8a8f98] mt-0.5 line-clamp-2 leading-relaxed">
                  {p.preview}
                </p>
              </div>
            </label>
          ))}
        </div>
      )}

      {/* 옵션 */}
      {problems && selectedNumbers.size > 0 && (
        <div className="p-4 bg-indigo-50 dark:bg-indigo-500/5 rounded-xl border border-indigo-200 dark:border-indigo-500/20 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs font-semibold text-gray-500 dark:text-[#8a8f98] uppercase tracking-wide">변형 유형</span>
            {TYPES.map((t) => (
              <button key={t.value} onClick={() => setVariantType(t.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  variantType === t.value
                    ? 'bg-indigo-600 dark:bg-indigo-500 text-white'
                    : 'bg-white dark:bg-[#141516] text-gray-600 dark:text-[#8a8f98] border border-gray-200 dark:border-[rgba(255,255,255,0.08)] hover:bg-gray-50 dark:hover:bg-[#1a1a1c]'
                }`}>{t.label}</button>
            ))}
            <span className="text-xs font-semibold text-gray-500 dark:text-[#8a8f98] uppercase tracking-wide ml-2">난이도</span>
            {DIFFS.map((d) => (
              <button key={d.value} onClick={() => setDifficulty(d.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  difficulty === d.value
                    ? 'bg-violet-600 dark:bg-violet-500 text-white'
                    : 'bg-white dark:bg-[#141516] text-gray-600 dark:text-[#8a8f98] border border-gray-200 dark:border-[rgba(255,255,255,0.08)] hover:bg-gray-50 dark:hover:bg-[#1a1a1c]'
                }`}>{d.label}</button>
            ))}
          </div>
          <input type="text" value={customPrompt} onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder="추가 지시사항 (선택)"
            className="w-full px-3 py-2.5 border border-indigo-200 dark:border-[rgba(255,255,255,0.08)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500 bg-white dark:bg-[#141516] text-gray-700 dark:text-[#f7f8f8] placeholder:text-gray-400 dark:placeholder:text-[#4a4a52] transition-colors" />
          <div className="flex gap-2.5">
            <button onClick={handleGenerate} disabled={isLoading}
              className="flex-1 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg font-semibold text-sm hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all shadow-[0_2px_12px_rgba(108,127,255,0.25)]">
              {isLoading ? `생성 중... (${selectedNumbers.size}문제)` : `✦ ${selectedNumbers.size}문제 유사문항 생성`}
            </button>
            <button onClick={handleReset}
              className="px-4 py-2.5 bg-gray-100 dark:bg-[#141516] text-gray-600 dark:text-[#8a8f98] border border-gray-200 dark:border-[rgba(255,255,255,0.08)] rounded-lg text-sm font-medium hover:bg-gray-200 dark:hover:bg-[#1a1a1c] transition-colors">
              초기화
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 rounded-lg text-sm border border-red-200 dark:border-red-500/20">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="text-center py-6">
          <div className="inline-block w-8 h-8 border-[3px] border-indigo-200 dark:border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
          <p className="text-gray-400 dark:text-[#8a8f98] text-sm mt-3">{selectedNumbers.size}개 문제 유사문항 생성 중...</p>
        </div>
      )}

      {/* 결과 */}
      {batchResults && (
        <div className="space-y-6">
          {batchResults.map((r, i) => (
            <div key={i} className="bg-white dark:bg-[#0f1011] rounded-xl border border-gray-200 dark:border-[rgba(255,255,255,0.06)] p-5 shadow-sm">
              <h3 className="font-bold text-gray-800 dark:text-[#f7f8f8] mb-3">{r.number}번 유사문항</h3>
              <div className="text-gray-700 dark:text-[#d0d0d5] text-sm leading-relaxed">
                <LatexRenderer text={hwpToLatex(r.result)} />
              </div>
              <UsageInfo usage={r.usage} />

              <div className="mt-3 pt-3 border-t border-gray-100 dark:border-[rgba(255,255,255,0.06)]">
                <div className="flex gap-2">
                  <input type="text" value={i === batchResults.length - 1 ? refineText : ''}
                    onChange={(e) => setRefineText(e.target.value)}
                    placeholder="수정 요청 (예: 답을 다른 값으로, 조건을 단순하게)"
                    className="flex-1 px-3 py-2 border border-amber-200 dark:border-amber-500/20 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-amber-400/30 bg-white dark:bg-[#141516] text-gray-700 dark:text-[#f7f8f8] placeholder:text-gray-400 dark:placeholder:text-[#4a4a52]" />
                  <button onClick={() => handleRefine(i)} disabled={isRefining || !refineText.trim()}
                    className="px-3 py-2 bg-amber-500 dark:bg-amber-600 text-white rounded-lg text-xs font-medium hover:bg-amber-600 dark:hover:bg-amber-500 disabled:opacity-50 transition-colors">
                    {isRefining ? '수정 중...' : '수정'}
                  </button>
                </div>
              </div>
            </div>
          ))}

          {usage && (
            <div className="p-3 bg-gray-50 dark:bg-[#141516] rounded-lg border border-gray-200 dark:border-[rgba(255,255,255,0.08)] text-xs text-gray-500 dark:text-[#8a8f98]">
              총 비용: ${usage.cost_usd?.toFixed(4)} (약 {Math.round(usage.cost_krw || 0).toLocaleString()}원) | 총 토큰: {(usage.total_tokens || 0).toLocaleString()}
            </div>
          )}
        </div>
      )}

      {downloadId && (
        <button onClick={handleDownload}
          className="w-full py-2.5 bg-gradient-to-r from-orange-500 to-amber-500 text-white rounded-lg font-semibold text-sm hover:from-orange-400 hover:to-amber-400 transition-all shadow-[0_2px_12px_rgba(245,158,11,0.25)]">
          한글 파일(.hwpx) 다운로드
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/HwpxInputMode.jsx
git commit -m "feat: create HwpxInputMode with HWP auto-conversion support"
```

---

### Task 4: TabCreateVariant.jsx를 모드 선택 shell로 재작성

**Files:**
- Modify: `frontend/src/components/TabCreateVariant.jsx`

이 파일을 완전히 재작성. 앱 시작 시 `/api/system-info`를 fetch해 `hwpConverterAvailable`을 결정. `mode` state가 `null`이면 두 카드 버튼 표시, `'image'`이면 `ImageInputMode`, `'hwpx'`이면 `HwpxInputMode`.

- [ ] **Step 1: TabCreateVariant.jsx 재작성**

```jsx
import { useState, useEffect } from 'react'
import ImageInputMode from './ImageInputMode'
import HwpxInputMode from './HwpxInputMode'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

export default function TabCreateVariant({ grade, model, guidelines }) {
  const [mode, setMode] = useState(null)
  const [hwpConverterAvailable, setHwpConverterAvailable] = useState(false)

  useEffect(() => {
    fetch(`${API}/api/system-info`)
      .then(r => r.json())
      .then(d => setHwpConverterAvailable(!!d.hwp_converter_available))
      .catch(() => {})
  }, [])

  if (mode === 'image') {
    return (
      <div className="space-y-4">
        <button
          onClick={() => setMode(null)}
          className="text-xs text-gray-400 dark:text-[#8a8f98] hover:text-gray-600 dark:hover:text-[#f7f8f8] flex items-center gap-1"
        >
          ← 입력 방식 다시 선택
        </button>
        <ImageInputMode grade={grade} model={model} guidelines={guidelines} />
      </div>
    )
  }

  if (mode === 'hwpx') {
    return (
      <div className="space-y-4">
        <button
          onClick={() => setMode(null)}
          className="text-xs text-gray-400 dark:text-[#8a8f98] hover:text-gray-600 dark:hover:text-[#f7f8f8] flex items-center gap-1"
        >
          ← 입력 방식 다시 선택
        </button>
        <HwpxInputMode grade={grade} model={model} guidelines={guidelines} hwpConverterAvailable={hwpConverterAvailable} />
      </div>
    )
  }

  // 모드 선택 화면
  return (
    <div className="space-y-6 py-4">
      <div className="text-center">
        <h2 className="text-base font-semibold text-gray-700 dark:text-[#d0d0d5]">입력 방식을 선택하세요</h2>
        <p className="text-xs text-gray-400 dark:text-[#8a8f98] mt-1">문제와 해설을 어떻게 입력할지 고르면 됩니다</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={() => setMode('image')}
          className="group flex flex-col items-center gap-4 p-6 bg-white dark:bg-[#0f1011] rounded-2xl border-2 border-gray-200 dark:border-[rgba(255,255,255,0.06)] hover:border-indigo-400 dark:hover:border-indigo-500 hover:shadow-lg dark:hover:shadow-[0_4px_20px_rgba(108,127,255,0.12)] transition-all duration-200"
        >
          <div className="w-14 h-14 bg-indigo-500 rounded-2xl flex items-center justify-center text-2xl text-white shadow-sm group-hover:scale-110 transition-transform">
            📸
          </div>
          <div className="text-center">
            <div className="text-sm font-semibold text-gray-800 dark:text-[#f7f8f8]">이미지로 입력</div>
            <div className="text-xs text-gray-400 dark:text-[#8a8f98] mt-1">문제·해설 이미지를 직접 업로드</div>
          </div>
        </button>

        <button
          onClick={() => setMode('hwpx')}
          className="group flex flex-col items-center gap-4 p-6 bg-white dark:bg-[#0f1011] rounded-2xl border-2 border-gray-200 dark:border-[rgba(255,255,255,0.06)] hover:border-orange-400 dark:hover:border-orange-500 hover:shadow-lg dark:hover:shadow-[0_4px_20px_rgba(245,158,11,0.12)] transition-all duration-200"
        >
          <div className="w-14 h-14 bg-orange-500 rounded-2xl flex items-center justify-center text-2xl text-white shadow-sm group-hover:scale-110 transition-transform">
            📄
          </div>
          <div className="text-center">
            <div className="text-sm font-semibold text-gray-800 dark:text-[#f7f8f8]">한글 파일 입력</div>
            <div className="text-xs text-gray-400 dark:text-[#8a8f98] mt-1">
              {hwpConverterAvailable ? 'HWP / HWPX 파일에서 문제 선택' : 'HWPX 파일에서 문제 선택'}
            </div>
          </div>
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/TabCreateVariant.jsx
git commit -m "feat: rewrite TabCreateVariant as mode-selector shell"
```

---

### Task 5: App.jsx에서 hwpx 탭 항목 제거

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: FEATURES 배열에서 hwpx 항목 삭제**

`frontend/src/App.jsx` 라인 11-18의 FEATURES 배열에서 `{ id: 'hwpx', ... }` 줄을 삭제:

```jsx
// 삭제할 줄:
//   { id: 'hwpx', label: '한글 파일', desc: '.hwpx → 유사문항/해설', icon: '⬡', color: 'bg-orange-500' },
```

결과:
```jsx
const FEATURES = [
  { id: 'create', label: '유사문항 생성', desc: '이미지 → 유사문항', icon: '✦', color: 'bg-indigo-500' },
  { id: 'solve', label: '변형문항 해설', desc: '이미지 → 해설', icon: '✎', color: 'bg-violet-500' },
  { id: 'scan', label: '스캔 처리', desc: '스캔 → HWP + 유사문항', icon: '⊡', color: 'bg-sky-500' },
  { id: 'history', label: '히스토리', desc: '저장 · 비교', icon: '≋', color: 'bg-slate-500' },
  { id: 'prompt', label: '프롬프트 설정', desc: '피드백 반영', icon: '⚙', color: 'bg-slate-500' },
  { id: 'guide', label: '사용설명서', desc: '단계별 사용법', icon: '?', color: 'bg-teal-500' },
]
```

- [ ] **Step 2: TabHwpx import 및 render 제거**

같은 파일에서:
- 라인 4 `import TabHwpx from './components/TabHwpx'` 삭제
- 라인 176 `{activeFeature === 'hwpx' && <TabHwpx {...commonProps} />}` 삭제

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/App.jsx
git commit -m "feat: remove hwpx tab (merged into 유사문항 생성)"
```

---

### Task 6: 통합 동작 확인

- [ ] **Step 1: 프론트엔드 개발 서버 시작 확인**

```bash
# 이미 실행 중이면 불필요
cd frontend && npm run dev
```

- [ ] **Step 2: 홈 화면에서 "한글 파일" 탭 카드가 사라졌는지 확인**

브라우저에서 `http://localhost:5173` 접속. 홈 카드 그리드에서 "한글 파일"이 없고 "유사문항 생성"만 남아있어야 함.

- [ ] **Step 3: 유사문항 생성 탭 클릭 → 모드 선택 화면 확인**

"유사문항 생성" 클릭 시 두 카드("이미지로 입력", "한글 파일 입력")가 표시되어야 함.

- [ ] **Step 4: 이미지 모드 동작 확인**

"이미지로 입력" 클릭 → 기존 이미지 업로드 UI 표시 → "← 입력 방식 다시 선택" 버튼 동작 확인.

- [ ] **Step 5: 한글 파일 모드 동작 확인**

"한글 파일 입력" 클릭 → HWPX 업로드 UI 표시 → 기존 HWPX 파일 업로드 시 문제 목록 표시.

- [ ] **Step 6: 최종 커밋**

```bash
git add -A
git commit -m "chore: tab unification complete — verify all modes working"
```
