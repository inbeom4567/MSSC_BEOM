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
  const [result, setResult] = useState(null)
  const [usage, setUsage] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

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
    setResult(null); setError(null)
  }

  const handleGenerate = async () => {
    setIsLoading(true); setError(null); setResult(null)
    try {
      const formData = new FormData()
      formData.append('files', problemFile)
      formData.append('files', solutionFile)
      const res = await fetch(`${API}/api/generate?variant_type=${variantType}&difficulty=${difficulty}&model=${model}`, {
        method: 'POST', body: formData,
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '생성 실패')
      const data = await res.json()
      setResult(data.result)
      setUsage(data.usage)
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
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
          <SolutionDisplay solution={result} title="유사문항 & 풀이" />
          <UsageInfo usage={usage} />
        </>
      )}
    </div>
  )
}
