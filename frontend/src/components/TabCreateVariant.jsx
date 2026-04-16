import { useState, useCallback } from 'react'
import ImageUploadBox from './ImageUploadBox'
import SolutionDisplay from './SolutionDisplay'
import UsageInfo from './UsageInfo'

const API = 'http://localhost:8001'

const TYPES = [
  { value: 'number', label: '숫자 변형' },
  { value: 'idea', label: '아이디어 변형' },
]
const DIFFS = [
  { value: 'easier', label: '더 쉽게' },
  { value: 'similar', label: '비슷하게' },
  { value: 'harder', label: '더 어렵게' },
]

export default function TabCreateVariant({ grade, model, guidelines }) {
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
            <span className="text-xs font-semibold text-gray-500 dark:text-[#7880AA] uppercase tracking-wide">변형 유형</span>
            {TYPES.map((t) => (
              <button key={t.value} onClick={() => setVariantType(t.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  variantType === t.value
                    ? 'bg-indigo-600 dark:bg-indigo-500 text-white'
                    : 'bg-white dark:bg-[#191C2E] text-gray-600 dark:text-[#7880AA] border border-gray-200 dark:border-[#2E3356] hover:bg-gray-50 dark:hover:bg-[#212540]'
                }`}>{t.label}</button>
            ))}
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs font-semibold text-gray-500 dark:text-[#7880AA] uppercase tracking-wide">난이도</span>
            {DIFFS.map((d) => (
              <button key={d.value} onClick={() => setDifficulty(d.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  difficulty === d.value
                    ? 'bg-violet-600 dark:bg-violet-500 text-white'
                    : 'bg-white dark:bg-[#191C2E] text-gray-600 dark:text-[#7880AA] border border-gray-200 dark:border-[#2E3356] hover:bg-gray-50 dark:hover:bg-[#212540]'
                }`}>{d.label}</button>
            ))}
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-500 dark:text-[#7880AA] uppercase tracking-wide block mb-1.5">
              추가 지시사항 <span className="normal-case font-normal text-gray-400">(선택)</span>
            </label>
            <input type="text"
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="예: 로그 밑을 3 대신 2로 바꿔서 / 조건에 절댓값 추가"
              className="w-full px-3 py-2.5 border border-indigo-200 dark:border-[#2E3356] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500 bg-white dark:bg-[#191C2E] text-gray-700 dark:text-[#E8EAFF] placeholder:text-gray-400 dark:placeholder:text-[#444A6E] transition-colors"
            />
          </div>

          <div className="flex gap-2.5">
            <button onClick={handleGenerate} disabled={isLoading}
              className="flex-1 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg font-semibold text-sm hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all shadow-[0_2px_12px_rgba(108,127,255,0.25)] hover:shadow-[0_4px_20px_rgba(108,127,255,0.35)] disabled:shadow-none">
              {isLoading ? '생성 중... (30초~1분)' : '✦ 유사문항 생성'}
            </button>
            <button onClick={handleReset}
              className="px-4 py-2.5 bg-gray-100 dark:bg-[#191C2E] text-gray-600 dark:text-[#7880AA] border border-gray-200 dark:border-[#2E3356] rounded-lg text-sm font-medium hover:bg-gray-200 dark:hover:bg-[#212540] transition-colors">
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
          <p className="text-gray-400 dark:text-[#7880AA] text-sm mt-3">원본 해설 방향 그대로 유사문항 풀이 작성 중...</p>
        </div>
      )}

      {result && (
        <>
          <SolutionDisplay solution={result} graphs={graphs} title="유사문항 & 해설" />
          <UsageInfo usage={usage} />

          {/* 수정 요청 */}
          <div className="p-4 bg-amber-50 dark:bg-amber-500/5 rounded-xl border border-amber-200 dark:border-amber-500/20">
            <label className="text-xs font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wide block mb-2">
              수정 요청
            </label>
            <div className="flex gap-2">
              <input type="text"
                value={refineText}
                onChange={(e) => setRefineText(e.target.value)}
                placeholder="예: 조건을 더 단순하게 / 답을 다른 값으로"
                className="flex-1 px-3 py-2.5 border border-amber-200 dark:border-amber-500/20 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/30 bg-white dark:bg-[#191C2E] text-gray-700 dark:text-[#E8EAFF] placeholder:text-gray-400 dark:placeholder:text-[#444A6E]"
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
