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
const MODELS = [
  { value: 'sonnet', label: 'Sonnet (빠름, ~100원)', color: 'bg-sky-600' },
  { value: 'opus', label: 'Opus (고품질, ~500원)', color: 'bg-purple-600' },
]

export default function TabCreateVariant() {
  const [problemPreview, setProblemPreview] = useState(null)
  const [problemFile, setProblemFile] = useState(null)
  const [solutionPreview, setSolutionPreview] = useState(null)
  const [solutionFile, setSolutionFile] = useState(null)
  const [dragging, setDragging] = useState(null)

  const [variantType, setVariantType] = useState('idea')
  const [difficulty, setDifficulty] = useState('similar')
  const [model, setModel] = useState('sonnet')
  const [customPrompt, setCustomPrompt] = useState('')
  const [result, setResult] = useState(null)
  const [graphs, setGraphs] = useState([])
  const [usage, setUsage] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  // 수정 요청 상태
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
      const params = new URLSearchParams({ variant_type: variantType, difficulty, model })
      if (customPrompt.trim()) params.set('custom_prompt', customPrompt.trim())

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
        <div className="p-4 bg-blue-50 rounded-xl border border-blue-200 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium text-gray-600">변형 유형:</span>
            {TYPES.map((t) => (
              <button key={t.value} onClick={() => setVariantType(t.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  variantType === t.value ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'
                }`}>{t.label}</button>
            ))}
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium text-gray-600">난이도:</span>
            {DIFFS.map((d) => (
              <button key={d.value} onClick={() => setDifficulty(d.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  difficulty === d.value ? 'bg-green-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'
                }`}>{d.label}</button>
            ))}
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium text-gray-600">모델:</span>
            {MODELS.map((m) => (
              <button key={m.value} onClick={() => setModel(m.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  model === m.value ? `${m.color} text-white` : 'bg-white text-gray-600 hover:bg-gray-100'
                }`}>{m.label}</button>
            ))}
          </div>

          <div>
            <label className="text-sm font-medium text-gray-600 block mb-1">
              문제 제작 지시사항 (선택):
            </label>
            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="예: 로그 밑을 3 대신 2로 바꿔서 만들어줘 / 조건에 절댓값을 추가해줘 / 답이 정수가 되도록 만들어줘"
              className="w-full p-2.5 border border-blue-200 rounded-lg text-sm resize-none h-16 focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
            />
          </div>

          <div className="flex gap-3">
            <button onClick={handleGenerate} disabled={isLoading}
              className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {isLoading ? '유사문항 생성 중... (30초~1분)' : '유사문항 생성'}
            </button>
            <button onClick={handleReset}
              className="px-5 py-2.5 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors">
              초기화
            </button>
          </div>
        </div>
      )}

      {error && <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm">{error}</div>}

      {isLoading && (
        <div className="text-center py-6">
          <div className="inline-block w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
          <p className="text-gray-500 text-sm mt-3">원본 해설 방향 그대로 유사문항 풀이 작성 중...</p>
        </div>
      )}

      {result && (
        <>
          <SolutionDisplay solution={result} graphs={graphs} title="유사문항 & 풀이" />
          <UsageInfo usage={usage} />

          {/* 수정 요청 영역 */}
          <div className="p-4 bg-amber-50 rounded-xl border border-amber-200">
            <label className="text-sm font-bold text-amber-800 block mb-2">
              수정 요청
            </label>
            <div className="flex gap-2">
              <textarea
                value={refineText}
                onChange={(e) => setRefineText(e.target.value)}
                placeholder="예: 문제의 조건을 좀 더 단순하게 / 답을 78에서 다른 값으로 / 풀이 3단계를 더 자세하게"
                className="flex-1 p-2.5 border border-amber-200 rounded-lg text-sm resize-none h-12 focus:outline-none focus:ring-2 focus:ring-amber-400 bg-white"
              />
              <button onClick={handleRefine} disabled={isRefining || !refineText.trim()}
                className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors whitespace-nowrap">
                {isRefining ? '수정 중...' : '수정'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
