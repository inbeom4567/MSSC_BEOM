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

  const [mode, setMode] = useState(null) // 'generate' | 'solve'
  const [variantType, setVariantType] = useState('idea')
  const [difficulty, setDifficulty] = useState('similar')
  const [model, setModel] = useState('sonnet')
  const [customPrompt, setCustomPrompt] = useState('')

  const [result, setResult] = useState(null)
  const [graphs, setGraphs] = useState([])
  const [usage, setUsage] = useState(null)
  const [hwpxDownload, setHwpxDownload] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFile = async (e) => {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setFileName(f.name)
    setResult(null)
    setError(null)

    // 미리보기: 서버에 파싱 요청 안 하고 일단 파일명만 표시
    // 실제 파싱은 생성 시 서버에서 수행
    const text = await f.text().catch(() => null)
    if (text && text.startsWith('PK')) {
      setPreviewText('HWPX 파일이 업로드되었습니다.')
    } else {
      setPreviewText('파일 형식을 확인해주세요.')
    }

    // -유사문제- 태그가 있으면 solve 모드 제안
    // (실제 파일 내용은 서버에서 파싱하므로 여기서는 판단 불가)
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
      setResult(data.result)
      setGraphs(data.graphs || [])
      setUsage(data.usage)
      setHwpxDownload(data.hwpx_download)
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
      setResult(data.result)
      setGraphs(data.graphs || [])
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
    a.download = `result_${Date.now()}.hwpx`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleReset = () => {
    setFile(null); setFileName(''); setPreviewText(null); setMode(null)
    setResult(null); setGraphs([]); setUsage(null); setHwpxDownload(null); setError(null)
    setCustomPrompt('')
  }

  return (
    <div className="space-y-4">
      {/* 파일 업로드 */}
      <div className="p-6 border-2 border-dashed border-gray-300 rounded-xl text-center hover:border-blue-400 transition-colors">
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
              <p className="text-gray-600 font-medium">한글 파일(.hwpx) 업로드</p>
              <p className="text-gray-400 text-xs mt-1">
                -문제- / -해설- 태그로 구분된 파일<br/>
                유사문제가 포함되면 자동으로 해설 작성 모드
              </p>
            </div>
          )}
        </label>
      </div>

      {/* 모드 선택 */}
      {file && !mode && (
        <div className="flex gap-3 justify-center">
          <button onClick={() => setMode('generate')}
            className="px-6 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors">
            유사문항 생성
            <span className="block text-xs opacity-75 mt-0.5">-문제- + -해설- 파일</span>
          </button>
          <button onClick={() => setMode('solve')}
            className="px-6 py-3 bg-green-600 text-white rounded-xl font-medium hover:bg-green-700 transition-colors">
            변형문항 해설 작성
            <span className="block text-xs opacity-75 mt-0.5">-문제- + -해설- + -유사문제- 파일</span>
          </button>
          <button onClick={handleReset}
            className="px-6 py-3 bg-gray-200 text-gray-700 rounded-xl font-medium hover:bg-gray-300 transition-colors">
            초기화
          </button>
        </div>
      )}

      {/* 유사문항 생성 옵션 */}
      {mode === 'generate' && (
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
          <textarea
            value={customPrompt} onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder="문제 제작 지시사항 (선택)"
            className="w-full p-2.5 border border-blue-200 rounded-lg text-sm resize-none h-12 focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
          />
          <div className="flex gap-3">
            <button onClick={handleGenerate} disabled={isLoading}
              className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {isLoading ? '생성 중...' : '유사문항 생성'}
            </button>
            <button onClick={handleReset}
              className="px-5 py-2.5 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors">
              초기화
            </button>
          </div>
        </div>
      )}

      {/* 변형문항 해설 옵션 */}
      {mode === 'solve' && (
        <div className="p-4 bg-green-50 rounded-xl border border-green-200 space-y-3">
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
            <button onClick={handleSolve} disabled={isLoading}
              className="flex-1 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors">
              {isLoading ? '해설 작성 중...' : '해설 작성'}
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
          <p className="text-gray-500 text-sm mt-3">
            {mode === 'generate' ? '유사문항 생성 중...' : '해설 작성 중...'} (텍스트 모드 - 이미지보다 빠름)
          </p>
        </div>
      )}

      {result && (
        <>
          <SolutionDisplay solution={result} graphs={graphs} title={mode === 'generate' ? '유사문항 & 해설' : '변형문항 해설'} />
          <UsageInfo usage={usage} />
          {hwpxDownload && (
            <button onClick={handleDownloadHwpx}
              className="w-full py-2.5 bg-orange-500 text-white rounded-lg font-medium hover:bg-orange-600 transition-colors">
              한글 파일(.hwpx) 다운로드
            </button>
          )}
        </>
      )}
    </div>
  )
}
