import { useState, useCallback } from 'react'
import ImageUploadBox from './ImageUploadBox'
import SolutionDisplay from './SolutionDisplay'

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

export default function TabCreateVariant() {
  const [problemPreview, setProblemPreview] = useState(null)
  const [problemFile, setProblemFile] = useState(null)
  const [solutionPreview, setSolutionPreview] = useState(null)
  const [solutionFile, setSolutionFile] = useState(null)
  const [dragging, setDragging] = useState(null)

  const [verifyResult, setVerifyResult] = useState(null)
  const [isVerifying, setIsVerifying] = useState(false)

  const [variantType, setVariantType] = useState('idea')
  const [difficulty, setDifficulty] = useState('similar')
  const [generateResult, setGenerateResult] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)

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
    // 새 이미지 올리면 결과 초기화
    setVerifyResult(null)
    setGenerateResult(null)
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
    setVerifyResult(null); setGenerateResult(null); setError(null)
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

  const handleGenerate = async () => {
    setIsGenerating(true); setError(null); setGenerateResult(null)
    try {
      const formData = new FormData()
      formData.append('files', problemFile)
      formData.append('files', solutionFile)
      const res = await fetch(`${API}/api/generate?variant_type=${variantType}&difficulty=${difficulty}`, {
        method: 'POST', body: formData,
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '생성 실패')
      const data = await res.json()
      setGenerateResult(data.result)
    } catch (err) { setError(err.message) }
    finally { setIsGenerating(false) }
  }

  const ready = problemFile && solutionFile

  return (
    <div className="space-y-4" onPaste={handlePaste} tabIndex={0}>
      <div className="flex gap-3">
        <ImageUploadBox
          preview={problemPreview} label="원본 문제 (필수)" icon="📝"
          isDragging={dragging === 'problem'}
          onFile={(f) => handleFile(f, 'problem')}
          onDragState={(v) => setDragging(v ? 'problem' : null)}
        />
        <ImageUploadBox
          preview={solutionPreview} label="원본 해설 (필수)" icon="📖"
          isDragging={dragging === 'solution'}
          onFile={(f) => handleFile(f, 'solution')}
          onDragState={(v) => setDragging(v ? 'solution' : null)}
        />
      </div>

      {ready && (
        <div className="flex gap-3 justify-center">
          <button onClick={handleVerify} disabled={isVerifying || isGenerating}
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
        <div className="p-4 bg-blue-50 rounded-xl border border-blue-200 space-y-3">
          <h3 className="font-bold text-blue-800">2단계: 유사문항 생성 옵션</h3>
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
          <button onClick={handleGenerate} disabled={isGenerating}
            className="w-full py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {isGenerating ? '유사문항 생성 중... (Opus, 1~2분 소요)' : '유사문항 생성'}
          </button>
        </div>
      )}

      {isGenerating && (
        <div className="text-center py-4">
          <div className="inline-block w-6 h-6 border-3 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
          <p className="text-gray-500 text-sm mt-2">Opus 모델로 유사문항 생성 중...</p>
        </div>
      )}

      {generateResult && <SolutionDisplay solution={generateResult} title="유사문항 & 풀이" />}
    </div>
  )
}
