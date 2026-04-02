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
  const [fileName, setFileName] = useState('')
  const [previewText, setPreviewText] = useState(null)

  const [mode, setMode] = useState(null) // 'generate' | 'solve' | 'batch'
  const [variantType, setVariantType] = useState('idea')
  const [difficulty, setDifficulty] = useState('similar')
  const [model, setModel] = useState('sonnet')
  const [customPrompt, setCustomPrompt] = useState('')

  const [result, setResult] = useState(null)
  const [batchResults, setBatchResults] = useState(null)
  const [graphs, setGraphs] = useState([])
  const [usage, setUsage] = useState(null)
  const [hwpxDownload, setHwpxDownload] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState(null)

  const handleFile = (e) => {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setFileName(f.name)
    setResult(null); setBatchResults(null); setError(null); setMode(null)
    setPreviewText('HWPX 파일이 업로드되었습니다.')
  }

  const handleGenerate = async () => {
    if (!file) return
    setIsLoading(true); setError(null); setResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const params = new URLSearchParams({ variant_type: variantType, difficulty, model })
      if (customPrompt.trim()) params.set('custom_prompt', customPrompt.trim())
      const res = await fetch(`${API}/api/hwpx-generate?${params}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '생성 실패')
      const data = await res.json()
      setResult(data.result); setGraphs(data.graphs || []); setUsage(data.usage); setHwpxDownload(data.hwpx_download)
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
  }

  const handleSolve = async () => {
    if (!file) return
    setIsLoading(true); setError(null); setResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const params = new URLSearchParams({ model })
      const res = await fetch(`${API}/api/hwpx-solve?${params}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '생성 실패')
      const data = await res.json()
      setResult(data.result); setGraphs(data.graphs || []); setUsage(data.usage); setHwpxDownload(data.hwpx_download)
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
  }

  const handleBatch = async () => {
    if (!file) return
    setIsLoading(true); setError(null); setBatchResults(null); setResult(null)
    setProgress('파일 분석 중...')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const params = new URLSearchParams({ variant_type: variantType, difficulty, model })
      if (customPrompt.trim()) params.set('custom_prompt', customPrompt.trim())
      const res = await fetch(`${API}/api/hwpx-batch?${params}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '생성 실패')
      const data = await res.json()
      setBatchResults(data.results)
      setResult(data.combined_text)
      setUsage(data.usage)
      setHwpxDownload(data.hwpx_download)
      setProgress(`${data.problem_count}개 문제 처리 완료`)
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
  }

  const handleDownloadHwpx = () => {
    if (!hwpxDownload) return
    const blob = new Blob([Uint8Array.from(atob(hwpxDownload), c => c.charCodeAt(0))], { type: 'application/hwp+zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `result_${Date.now()}.hwpx`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleReset = () => {
    setFile(null); setFileName(''); setPreviewText(null); setMode(null)
    setResult(null); setBatchResults(null); setGraphs([]); setUsage(null)
    setHwpxDownload(null); setError(null); setCustomPrompt(''); setProgress('')
  }

  const renderOptions = (onSubmit, submitLabel) => (
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
        placeholder="문제 제작 지시사항 (선택)" className="w-full p-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white" />
      <div className="flex gap-3">
        <button onClick={onSubmit} disabled={isLoading}
          className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
          {isLoading ? '처리 중...' : submitLabel}
        </button>
        <button onClick={handleReset} className="px-5 py-2.5 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors">초기화</button>
      </div>
    </div>
  )

  const [isDragging, setIsDragging] = useState(false)

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const f = e.dataTransfer.files[0]
    if (f && f.name.endsWith('.hwpx')) {
      setFile(f); setFileName(f.name); setResult(null); setBatchResults(null); setError(null); setMode(null)
      setPreviewText('HWPX 파일이 업로드되었습니다.')
    }
  }

  return (
    <div className="space-y-4">
      {/* 파일 업로드 (드래그앤드롭 + 클릭) */}
      <div
        className={`p-6 border-2 border-dashed rounded-xl text-center transition-colors ${
          isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
        }`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input type="file" accept=".hwpx" onChange={handleFile} className="hidden" id="hwpx-input" />
        <label htmlFor="hwpx-input" className="cursor-pointer">
          {fileName ? (
            <div>
              <p className="text-lg font-medium text-blue-600">{fileName}</p>
              <p className="text-sm text-gray-500 mt-1">{previewText}</p>
            </div>
          ) : (
            <div className="py-4">
              <div className="text-3xl mb-2">📄</div>
              <p className="text-gray-600 font-medium">한글 파일(.hwpx)을 드래그하거나 클릭</p>
              <p className="text-gray-400 text-xs mt-2">
                미주 형식 / -문제-해설- 형식 모두 지원<br/>
                여러 문제: -1번- -문제- -해설- / -2번- ...
              </p>
            </div>
          )}
        </label>
      </div>

      {/* 모드 선택 */}
      {file && !mode && (
        <div className="flex gap-3 justify-center">
          <button onClick={() => setMode('generate')}
            className="px-5 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors">
            유사문항 생성
            <span className="block text-xs opacity-75 mt-0.5">단일 문제</span>
          </button>
          <button onClick={() => setMode('batch')}
            className="px-5 py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 transition-colors">
            일괄 생성
            <span className="block text-xs opacity-75 mt-0.5">여러 문제 동시 처리</span>
          </button>
          <button onClick={() => setMode('solve')}
            className="px-5 py-3 bg-green-600 text-white rounded-xl font-medium hover:bg-green-700 transition-colors">
            해설 작성
            <span className="block text-xs opacity-75 mt-0.5">유사문제 포함 파일</span>
          </button>
          <button onClick={handleReset}
            className="px-5 py-3 bg-gray-200 text-gray-700 rounded-xl font-medium hover:bg-gray-300 transition-colors">
            초기화
          </button>
        </div>
      )}

      {/* 단일 생성 */}
      {mode === 'generate' && renderOptions(handleGenerate, '유사문항 생성')}

      {/* 일괄 생성 */}
      {mode === 'batch' && renderOptions(handleBatch, '일괄 유사문항 생성')}

      {/* 해설 작성 */}
      {mode === 'solve' && (
        <div className="p-4 bg-green-50 rounded-xl border border-green-200 space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-gray-600">모델:</span>
            {MODELS.map((m) => (
              <button key={m.value} onClick={() => setModel(m.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  model === m.value ? `${m.color} text-white` : 'bg-white text-gray-600 hover:bg-gray-100'
                }`}>{m.label}</button>
            ))}
          </div>
          <div className="flex gap-3">
            <button onClick={handleSolve} disabled={isLoading}
              className="flex-1 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors">
              {isLoading ? '해설 작성 중...' : '해설 작성'}
            </button>
            <button onClick={handleReset} className="px-5 py-2.5 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors">초기화</button>
          </div>
        </div>
      )}

      {error && <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm">{error}</div>}

      {isLoading && (
        <div className="text-center py-6">
          <div className="inline-block w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
          <p className="text-gray-500 text-sm mt-3">{progress || '처리 중... (텍스트 모드)'}</p>
        </div>
      )}

      {/* 일괄 결과 */}
      {batchResults && (
        <div className="space-y-4">
          <p className="text-sm font-medium text-indigo-600">{batchResults.length}개 문제 처리 완료</p>
          {batchResults.map((r, i) => (
            <div key={i} className="border-l-4 border-indigo-400 pl-4">
              <p className="text-sm font-bold text-gray-600 mb-2">{r.number}번</p>
              <SolutionDisplay solution={r.result} graphs={r.graphs} title={`${r.number}번 유사문항 & 해설`} />
              <UsageInfo usage={r.usage} />
            </div>
          ))}
        </div>
      )}

      {/* 단일 결과 */}
      {result && !batchResults && (
        <SolutionDisplay solution={result} graphs={graphs} title={mode === 'generate' ? '유사문항 & 해설' : '변형문항 해설'} />
      )}

      {usage && !batchResults && <UsageInfo usage={usage} />}
      {batchResults && usage && (
        <div className="p-3 bg-gray-50 rounded-lg text-xs text-gray-500">
          총 비용: ${usage.cost_usd} (약 {usage.cost_krw?.toLocaleString()}원) | 총 토큰: {usage.total_tokens?.toLocaleString()}
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
