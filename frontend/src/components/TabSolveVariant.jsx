import { useState, useCallback } from 'react'
import ImageUploadBox from './ImageUploadBox'
import SolutionDisplay from './SolutionDisplay'
import UsageInfo from './UsageInfo'

const API = 'http://localhost:8001'

export default function TabSolveVariant() {
  const [problemPreview, setProblemPreview] = useState(null)
  const [problemFile, setProblemFile] = useState(null)
  const [solutionPreview, setSolutionPreview] = useState(null)
  const [solutionFile, setSolutionFile] = useState(null)
  const [variantPreview, setVariantPreview] = useState(null)
  const [variantFile, setVariantFile] = useState(null)
  const [dragging, setDragging] = useState(null)

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
    } else if (type === 'solution') {
      setSolutionFile(f); reader.onload = (e) => setSolutionPreview(e.target.result)
    } else {
      setVariantFile(f); reader.onload = (e) => setVariantPreview(e.target.result)
    }
    reader.readAsDataURL(f)
    setResult(null)
  }, [])

  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const type = !problemFile ? 'problem' : !solutionFile ? 'solution' : 'variant'
        handleFile(item.getAsFile(), type)
        break
      }
    }
  }, [handleFile, problemFile, solutionFile])

  const handleReset = () => {
    setProblemPreview(null); setProblemFile(null)
    setSolutionPreview(null); setSolutionFile(null)
    setVariantPreview(null); setVariantFile(null)
    setResult(null); setError(null)
  }

  const handleSolve = async () => {
    setIsLoading(true); setError(null); setResult(null)
    try {
      const formData = new FormData()
      formData.append('files', problemFile)
      formData.append('files', solutionFile)
      formData.append('files', variantFile)
      const res = await fetch(`${API}/api/solve-variant?model=${model}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '풀이 생성 실패')
      const data = await res.json()
      setResult(data.result)
      setUsage(data.usage)
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
  }

  const ready = problemFile && solutionFile && variantFile

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
        <ImageUploadBox
          preview={variantPreview} label="변형문항" icon="✏️"
          isDragging={dragging === 'variant'}
          onFile={(f) => handleFile(f, 'variant')}
          onDragState={(v) => setDragging(v ? 'variant' : null)}
        />
      </div>

      {ready && (
        <div className="space-y-3">
        <div className="flex items-center gap-3 justify-center">
          <span className="text-sm font-medium text-gray-600">모델:</span>
          <button onClick={() => setModel('sonnet')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${model === 'sonnet' ? 'bg-sky-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            Sonnet (빠름, ~100원)</button>
          <button onClick={() => setModel('opus')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${model === 'opus' ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            Opus (고품질, ~500원)</button>
        </div>
        <div className="flex gap-3 justify-center">
          <button onClick={handleSolve} disabled={isLoading}
            className="px-6 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors">
            {isLoading ? '해설 작성 중... (30초~1분)' : '해설 작성'}
          </button>
          <button onClick={handleReset}
            className="px-6 py-2.5 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors">
            초기화
          </button>
        </div>
        </div>
      )}

      {error && <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm">{error}</div>}

      {isLoading && (
        <div className="text-center py-6">
          <div className="inline-block w-8 h-8 border-4 border-green-200 border-t-green-600 rounded-full animate-spin" />
          <p className="text-gray-500 text-sm mt-3">원본 해설 방향 그대로 변형문항 풀이 작성 중...</p>
        </div>
      )}

      {result && (
        <>
          <SolutionDisplay solution={result} title="변형문항 풀이" />
          <UsageInfo usage={usage} />
        </>
      )}
    </div>
  )
}
