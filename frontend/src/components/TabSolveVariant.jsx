import { useState, useCallback } from 'react'
import ImageUploadBox from './ImageUploadBox'
import SolutionDisplay from './SolutionDisplay'
import UsageInfo from './UsageInfo'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

export default function TabSolveVariant({ grade, model, guidelines }) {
  const [problemPreview, setProblemPreview] = useState(null)
  const [problemFile, setProblemFile] = useState(null)
  const [solutionPreview, setSolutionPreview] = useState(null)
  const [solutionFile, setSolutionFile] = useState(null)
  const [variantPreview, setVariantPreview] = useState(null)
  const [variantFile, setVariantFile] = useState(null)
  const [dragging, setDragging] = useState(null)

  const [result, setResult] = useState(null)
  const [graphs, setGraphs] = useState([])
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
      const params = new URLSearchParams({ model, grade })
      if (guidelines) params.set('custom_prompt', guidelines)
      const res = await fetch(`${API}/api/solve-variant?${params}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '풀이 생성 실패')
      const data = await res.json()
      setResult(data.result)
      setGraphs(data.graphs || [])
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
        <div className="flex gap-2.5 justify-center">
          <button onClick={handleSolve} disabled={isLoading}
            className="px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg font-semibold text-sm hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all shadow-[0_2px_12px_rgba(108,127,255,0.25)]">
            {isLoading ? '해설 작성 중... (30초~1분)' : '✦ 해설 작성'}
          </button>
          <button onClick={handleReset}
            className="px-5 py-2.5 bg-gray-100 dark:bg-[#141516] text-gray-600 dark:text-[#8a8f98] border border-gray-200 dark:border-[rgba(255,255,255,0.08)] rounded-lg text-sm font-medium hover:bg-gray-200 dark:hover:bg-[#1a1a1c] transition-colors">
            초기화
          </button>
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
          <p className="text-gray-400 dark:text-[#8a8f98] text-sm mt-3">원본 해설 방향 그대로 변형문항 풀이 작성 중...</p>
        </div>
      )}

      {result && (
        <>
          <SolutionDisplay solution={result} graphs={graphs} title="변형문항 해설" />
          <UsageInfo usage={usage} />
        </>
      )}
    </div>
  )
}
