import { useState } from 'react'
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
  { value: 'sonnet', label: 'Sonnet (~100원)', color: 'bg-sky-600' },
  { value: 'opus', label: 'Opus (~500원)', color: 'bg-purple-600' },
]

export default function TabHwpx() {
  const [file, setFile] = useState(null)
  const [fileBytes, setFileBytes] = useState(null)
  const [fileName, setFileName] = useState('')
  const [isDragging, setIsDragging] = useState(false)

  // 분석 결과
  const [problems, setProblems] = useState(null)
  const [selectedNumbers, setSelectedNumbers] = useState(new Set())
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  // 옵션
  const [variantType, setVariantType] = useState('idea')
  const [difficulty, setDifficulty] = useState('similar')
  const [model, setModel] = useState('sonnet')
  const [customPrompt, setCustomPrompt] = useState('')

  // 결과
  const [batchResults, setBatchResults] = useState(null)
  const [usage, setUsage] = useState(null)
  const [hwpxDownload, setHwpxDownload] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const analyzeFile = async (f) => {
    setIsAnalyzing(true); setError(null)
    try {
      const formData = new FormData()
      formData.append('file', f)
      const res = await fetch(`${API}/api/hwpx-analyze`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '분석 실패')
      const data = await res.json()
      setProblems(data.problems)
      // 기본: 전체 선택
      setSelectedNumbers(new Set(data.problems.map(p => p.number)))
    } catch (err) { setError(err.message) }
    finally { setIsAnalyzing(false) }
  }

  const handleFileInput = async (f) => {
    if (!f || !f.name.endsWith('.hwpx')) return
    setFile(f)
    setFileName(f.name)
    setBatchResults(null); setError(null); setHwpxDownload(null)

    const bytes = await f.arrayBuffer()
    setFileBytes(new Blob([bytes]))
    analyzeFile(f)
  }

  const handleDrop = (e) => {
    e.preventDefault(); setIsDragging(false)
    handleFileInput(e.dataTransfer.files[0])
  }

  const toggleNumber = (num) => {
    setSelectedNumbers(prev => {
      const next = new Set(prev)
      next.has(num) ? next.delete(num) : next.add(num)
      return next
    })
  }

  const selectAll = () => setSelectedNumbers(new Set(problems.map(p => p.number)))
  const selectNone = () => setSelectedNumbers(new Set())

  const handleGenerate = async () => {
    if (!file || selectedNumbers.size === 0) return
    setIsLoading(true); setError(null); setBatchResults(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const params = new URLSearchParams({ variant_type: variantType, difficulty, model })
      if (customPrompt.trim()) params.set('custom_prompt', customPrompt.trim())
      params.set('selected_numbers', [...selectedNumbers].join(','))

      const res = await fetch(`${API}/api/hwpx-batch?${params}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '생성 실패')
      const data = await res.json()
      setBatchResults(data.results)
      setUsage(data.usage)
      setHwpxDownload(data.hwpx_download)
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
  }

  const handleDownloadHwpx = () => {
    if (!hwpxDownload) return
    const blob = new Blob([Uint8Array.from(atob(hwpxDownload), c => c.charCodeAt(0))], { type: 'application/hwp+zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `유사문항_${Date.now()}.hwpx`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleReset = () => {
    setFile(null); setFileBytes(null); setFileName(''); setProblems(null)
    setSelectedNumbers(new Set()); setBatchResults(null); setUsage(null)
    setHwpxDownload(null); setError(null); setCustomPrompt('')
  }

  return (
    <div className="space-y-4">
      {/* 파일 업로드 */}
      <div
        className={`p-6 border-2 border-dashed rounded-xl text-center transition-colors ${
          isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
        }`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input type="file" accept=".hwpx" onChange={(e) => handleFileInput(e.target.files[0])} className="hidden" id="hwpx-input" />
        <label htmlFor="hwpx-input" className="cursor-pointer">
          {fileName ? (
            <div>
              <p className="text-lg font-medium text-blue-600">{fileName}</p>
              {isAnalyzing && <p className="text-sm text-gray-500 mt-1">파일 분석 중...</p>}
              {problems && <p className="text-sm text-green-600 mt-1">{problems.length}개 문제 감지됨</p>}
            </div>
          ) : (
            <div className="py-4">
              <div className="text-3xl mb-2">📄</div>
              <p className="text-gray-600 font-medium">한글 파일(.hwpx)을 드래그하거나 클릭</p>
              <p className="text-gray-400 text-xs mt-2">미주 형식 자동 인식 · 여러 문제 동시 처리</p>
            </div>
          )}
        </label>
      </div>

      {/* 문제 선택 */}
      {problems && problems.length > 0 && (
        <div className="p-4 bg-white rounded-xl border border-gray-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-gray-800">문제 선택 ({selectedNumbers.size}/{problems.length})</h3>
            <div className="flex gap-2">
              <button onClick={selectAll} className="text-xs text-blue-600 hover:underline">전체 선택</button>
              <button onClick={selectNone} className="text-xs text-gray-500 hover:underline">전체 해제</button>
            </div>
          </div>
          {problems.map((p) => (
            <label key={p.number} className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
              selectedNumbers.has(p.number) ? 'bg-blue-50' : 'hover:bg-gray-50'
            }`}>
              <input type="checkbox" checked={selectedNumbers.has(p.number)} onChange={() => toggleNumber(p.number)}
                className="mt-1 w-4 h-4 text-blue-600" />
              <div>
                <span className="text-sm font-medium text-gray-700">{p.number}번</span>
                <p className="text-xs text-gray-500 mt-0.5">{p.preview}</p>
              </div>
            </label>
          ))}
        </div>
      )}

      {/* 옵션 + 생성 버튼 */}
      {problems && selectedNumbers.size > 0 && (
        <div className="p-4 bg-blue-50 rounded-xl border border-blue-200 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium text-gray-600">변형:</span>
            {TYPES.map((t) => (
              <button key={t.value} onClick={() => setVariantType(t.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  variantType === t.value ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'
                }`}>{t.label}</button>
            ))}
            <span className="text-sm font-medium text-gray-600 ml-2">난이도:</span>
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
          <input type="text" value={customPrompt} onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder="문제 제작 지시사항 (선택)"
            className="w-full p-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white" />
          <div className="flex gap-3">
            <button onClick={handleGenerate} disabled={isLoading}
              className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {isLoading ? `생성 중... (${selectedNumbers.size}문제)` : `${selectedNumbers.size}문제 유사문항 생성`}
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
          <p className="text-gray-500 text-sm mt-3">{selectedNumbers.size}개 문제 유사문항 생성 중...</p>
        </div>
      )}

      {/* 결과 */}
      {batchResults && (
        <div className="space-y-4">
          {batchResults.map((r, i) => (
            <div key={i} className="border-l-4 border-blue-400 pl-4">
              <p className="text-sm font-bold text-gray-600 mb-2">{r.number}번 유사문항</p>
              <SolutionDisplay solution={r.result} graphs={r.graphs} title={`${r.number}번`} />
              <UsageInfo usage={r.usage} />
            </div>
          ))}
          {usage && (
            <div className="p-3 bg-gray-50 rounded-lg text-xs text-gray-500">
              총 비용: ${usage.cost_usd?.toFixed(4)} (약 {Math.round(usage.cost_krw || 0).toLocaleString()}원) | 총 토큰: {(usage.total_tokens || 0).toLocaleString()}
            </div>
          )}
        </div>
      )}

      {hwpxDownload && (
        <button onClick={handleDownloadHwpx}
          className="w-full py-2.5 bg-orange-500 text-white rounded-lg font-medium hover:bg-orange-600 transition-colors">
          한글 파일(.hwpx) 다운로드
        </button>
      )}
    </div>
  )
}
