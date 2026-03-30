import { useState, useCallback } from 'react'
import ImageUploadBox from './ImageUploadBox'
import SolutionDisplay from './SolutionDisplay'

const API = 'http://localhost:8001'

export default function TabSolveVariant() {
  const [problemPreview, setProblemPreview] = useState(null)
  const [problemFile, setProblemFile] = useState(null)
  const [solutionPreview, setSolutionPreview] = useState(null)
  const [solutionFile, setSolutionFile] = useState(null)
  const [variantPreview, setVariantPreview] = useState(null)
  const [variantFile, setVariantFile] = useState(null)
  const [dragging, setDragging] = useState(null)

  const [verifyResult, setVerifyResult] = useState(null)
  const [isVerifying, setIsVerifying] = useState(false)

  const [solveResult, setSolveResult] = useState(null)
  const [isSolving, setIsSolving] = useState(false)

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
    setVerifyResult(null); setSolveResult(null)
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
    setVerifyResult(null); setSolveResult(null); setError(null)
  }

  const handleVerify = async () => {
    setIsVerifying(true); setError(null); setVerifyResult(null)
    try {
      const formData = new FormData()
      formData.append('files', problemFile)
      formData.append('files', solutionFile)
      const res = await fetch(`${API}/api/verify`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '검증 실패')
      const data = await res.json()
      setVerifyResult(data.result)
    } catch (err) { setError(err.message) }
    finally { setIsVerifying(false) }
  }

  const handleSolve = async () => {
    setIsSolving(true); setError(null); setSolveResult(null)
    try {
      const formData = new FormData()
      formData.append('files', problemFile)
      formData.append('files', solutionFile)
      formData.append('files', variantFile)
      const res = await fetch(`${API}/api/solve-variant`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '풀이 생성 실패')
      const data = await res.json()
      setSolveResult(data.result)
    } catch (err) { setError(err.message) }
    finally { setIsSolving(false) }
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
        <div className="flex gap-3 justify-center">
          <button onClick={handleVerify} disabled={isVerifying || isSolving}
            className="px-5 py-2 bg-amber-500 text-white rounded-lg font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors">
            {isVerifying ? '검증 중...' : '1단계: 검증'}
          </button>
          <button onClick={handleReset}
            className="px-5 py-2 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors">
            초기화
          </button>
        </div>
      )}

      {error && <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm">{error}</div>}

      {isVerifying && (
        <div className="text-center py-4">
          <div className="inline-block w-6 h-6 border-3 border-amber-200 border-t-amber-500 rounded-full animate-spin" />
          <p className="text-gray-500 text-sm mt-2">검증 중... (Sonnet)</p>
        </div>
      )}

      {verifyResult && (
        <div className="p-4 bg-white rounded-xl border border-gray-200 shadow-sm">
          <h3 className="font-bold text-gray-800 mb-2">검증 결과</h3>
          <p className="text-gray-700 whitespace-pre-wrap">{verifyResult}</p>
        </div>
      )}

      {verifyResult && (
        <button onClick={handleSolve} disabled={isSolving}
          className="w-full py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors">
          {isSolving ? '해설 작성 중... (Opus, 1~2분 소요)' : '2단계: 해설 작성'}
        </button>
      )}

      {isSolving && (
        <div className="text-center py-4">
          <div className="inline-block w-6 h-6 border-3 border-green-200 border-t-green-600 rounded-full animate-spin" />
          <p className="text-gray-500 text-sm mt-2">Opus 모델로 해설 작성 중...</p>
        </div>
      )}

      {solveResult && <SolutionDisplay solution={solveResult} title="변형문항 풀이" />}
    </div>
  )
}
