import { useState } from 'react'
import LatexRenderer from './LatexRenderer'
import UsageInfo from './UsageInfo'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const TYPES = [
  { value: 'number', label: '숫자 변형' },
  { value: 'idea', label: '아이디어 변형' },
]
const DIFFS = [
  { value: 'easier', label: '더 쉽게' },
  { value: 'similar', label: '비슷하게' },
  { value: 'harder', label: '더 어렵게' },
]

function hwpToLatex(text) {
  return text.replace(/\[([^\]]+)\]/g, (_, code) => {
    let latex = code
      .replace(/\{([^}]*)\}\s*over\s*\{([^}]*)\}/g, '\\frac{$1}{$2}')
      .replace(/sqrt\{([^}]*)\}/g, '\\sqrt{$1}')
      .replace(/left\s*\(/g, '\\left(').replace(/right\s*\)/g, '\\right)')
      .replace(/left\s*\|/g, '\\left|').replace(/right\s*\|/g, '\\right|')
      .replace(/left\s*\{/g, '\\left\\{').replace(/right\s*\}/g, '\\right\\}')
      .replace(/left\s*\[/g, '\\left[').replace(/right\s*\]/g, '\\right]')
      .replace(/\ble\b/g, '\\leq').replace(/\bge\b/g, '\\geq').replace(/\bne\b/g, '\\neq')
      .replace(/\btherefore~/g, '\\therefore\\;')
      .replace(/\bbecause~/g, '\\because\\;')
      .replace(/\bcdotscdots\b/g, '\\cdots\\cdots').replace(/\bcdots\b/g, '\\cdots')
      .replace(/\bpi\b/g, '\\pi').replace(/\btheta\b/g, '\\theta')
      .replace(/\bsigma\b/g, '\\sigma').replace(/\binf\b/g, '\\infty')
      .replace(/\balpha\b/g, '\\alpha').replace(/\bbeta\b/g, '\\beta')
      .replace(/\bgamma\b/g, '\\gamma').replace(/\bdelta\b/g, '\\delta')
      .replace(/\bomega\b/g, '\\omega')
      .replace(/\bsin`/g, '\\sin\\,').replace(/\bcos`/g, '\\cos\\,').replace(/\btan`/g, '\\tan\\,')
      .replace(/\bsin\b/g, '\\sin').replace(/\bcos\b/g, '\\cos').replace(/\btan\b/g, '\\tan')
      .replace(/\blog_\{/g, '\\log_{').replace(/\blog`/g, '\\log\\,')
      .replace(/\bln`/g, '\\ln\\,')
      .replace(/\bsum_/g, '\\sum_').replace(/\blim_/g, '\\lim_')
      .replace(/\bint_/g, '\\int_').replace(/\bint\b/g, '\\int')
      .replace(/\+-/g, '\\pm')
      .replace(/\bDEG\b/g, '^{\\circ}')
      .replace(/\bTIMES\b/g, '\\times')
      .replace(/\bLEFT\s*\(/g, '\\left(').replace(/\bRIGHT\s*\)/g, '\\right)')
      .replace(/\bLRARROW\b/g, '\\Leftrightarrow').replace(/\bRARROW\b/g, '\\Rightarrow')
      .replace(/\bTHEREFORE\b/g, '\\therefore')
      .replace(/->/g, '\\to')
      .replace(/`/g, '\\,')
      .replace(/~/g, '\\;')
    return `$${latex}$`
  })
}

export default function TabHwpx({ grade, model, guidelines }) {
  const [file, setFile] = useState(null)
  const [fileName, setFileName] = useState('')
  const [isDragging, setIsDragging] = useState(false)

  const [problems, setProblems] = useState(null)
  const [selectedNumbers, setSelectedNumbers] = useState(new Set())
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const [variantType, setVariantType] = useState('idea')
  const [difficulty, setDifficulty] = useState('similar')
  const [customPrompt, setCustomPrompt] = useState('')

  const [batchResults, setBatchResults] = useState(null)
  const [usage, setUsage] = useState(null)
  const [downloadId, setDownloadId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const [refineText, setRefineText] = useState('')
  const [isRefining, setIsRefining] = useState(false)

  const analyzeFile = async (f) => {
    setIsAnalyzing(true); setError(null)
    try {
      const formData = new FormData()
      formData.append('file', f)
      const res = await fetch(`${API}/api/hwpx-analyze`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '분석 실패')
      const data = await res.json()
      setProblems(data.problems)
      setSelectedNumbers(new Set(data.problems.map(p => p.number)))
    } catch (err) { setError(err.message) }
    finally { setIsAnalyzing(false) }
  }

  const handleFileInput = (f) => {
    if (!f || !f.name.endsWith('.hwpx')) return
    setFile(f); setFileName(f.name)
    setBatchResults(null); setError(null); setDownloadId(null)
    analyzeFile(f)
  }

  const handleDrop = (e) => { e.preventDefault(); setIsDragging(false); handleFileInput(e.dataTransfer.files[0]) }

  const toggleNumber = (num) => {
    setSelectedNumbers(prev => { const next = new Set(prev); next.has(num) ? next.delete(num) : next.add(num); return next })
  }

  const handleGenerate = async () => {
    if (!file || selectedNumbers.size === 0) return
    setIsLoading(true); setError(null); setBatchResults(null); setDownloadId(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const params = new URLSearchParams({ variant_type: variantType, difficulty, model, grade, selected_numbers: [...selectedNumbers].join(',') })
      const fullPrompt = [guidelines, customPrompt.trim()].filter(Boolean).join('\n\n')
      if (fullPrompt) params.set('custom_prompt', fullPrompt)
      const res = await fetch(`${API}/api/hwpx-batch?${params}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '생성 실패')
      const data = await res.json()
      setBatchResults(data.results)
      setUsage(data.usage)
      setDownloadId(data.download_id)
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
  }

  const handleRefine = async (resultIndex) => {
    if (!refineText.trim() || !batchResults) return
    setIsRefining(true); setError(null)
    try {
      const res = await fetch(`${API}/api/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ original_result: batchResults[resultIndex].result, instruction: refineText.trim(), model }),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '수정 실패')
      const data = await res.json()
      setBatchResults(prev => prev.map((r, i) => i === resultIndex ? { ...r, result: data.result, usage: data.usage } : r))
      setRefineText('')
    } catch (err) { setError(err.message) }
    finally { setIsRefining(false) }
  }

  const handleDownload = () => {
    if (!downloadId) return
    window.open(`${API}/api/hwpx-download/${downloadId}`, '_blank')
  }

  const handleReset = () => {
    setFile(null); setFileName(''); setProblems(null)
    setSelectedNumbers(new Set()); setBatchResults(null); setUsage(null)
    setDownloadId(null); setError(null); setCustomPrompt(''); setRefineText('')
  }

  return (
    <div className="space-y-4">
      {/* 파일 업로드 */}
      <div
        className={`p-6 border-2 border-dashed rounded-xl text-center transition-colors ${
          isDragging
            ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10'
            : 'border-gray-300 dark:border-[#2E3356] hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-gray-50 dark:hover:bg-indigo-500/5'
        }`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input type="file" accept=".hwpx" onChange={(e) => handleFileInput(e.target.files[0])} className="hidden" id="hwpx-input" />
        <label htmlFor="hwpx-input" className="cursor-pointer">
          {fileName ? (
            <div>
              <p className="text-lg font-medium text-indigo-500 dark:text-indigo-400">{fileName}</p>
              {isAnalyzing && <p className="text-sm text-gray-500 dark:text-[#7880AA] mt-1">파일 분석 중...</p>}
              {problems && <p className="text-sm text-emerald-600 dark:text-emerald-400 mt-1">{problems.length}개 문제 감지됨</p>}
            </div>
          ) : (
            <div className="py-4">
              <div className="text-3xl mb-2">📄</div>
              <p className="text-gray-600 dark:text-[#7880AA] font-medium">한글 파일(.hwpx)을 드래그하거나 클릭</p>
              <p className="text-gray-400 dark:text-[#444A6E] text-xs mt-2">미주 형식 자동 인식 · 여러 문제 동시 처리</p>
            </div>
          )}
        </label>
      </div>

      {/* 문제 선택 */}
      {problems && problems.length > 0 && (
        <div className="p-4 bg-white dark:bg-[#11131F] rounded-xl border border-gray-200 dark:border-[#222644] shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-gray-800 dark:text-[#E8EAFF]">문제 선택 ({selectedNumbers.size}/{problems.length})</h3>
            <div className="flex gap-2">
              <button onClick={() => setSelectedNumbers(new Set(problems.map(p => p.number)))} className="text-xs text-indigo-500 dark:text-indigo-400 hover:underline">전체 선택</button>
              <button onClick={() => setSelectedNumbers(new Set())} className="text-xs text-gray-400 dark:text-[#7880AA] hover:underline">전체 해제</button>
            </div>
          </div>
          {problems.map((p) => (
            <label key={p.number} className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
              selectedNumbers.has(p.number)
                ? 'bg-indigo-50 dark:bg-indigo-500/10'
                : 'hover:bg-gray-50 dark:hover:bg-[#191C2E]'
            }`}>
              <input type="checkbox" checked={selectedNumbers.has(p.number)} onChange={() => toggleNumber(p.number)} className="mt-1 w-4 h-4 accent-indigo-500" />
              <div className="min-w-0">
                <span className="text-sm font-medium text-gray-700 dark:text-[#C8CADF]">{p.number}번</span>
                <div className="text-xs text-gray-500 dark:text-[#7880AA] mt-0.5 overflow-hidden">
                  <LatexRenderer text={hwpToLatex(p.preview)} />
                </div>
              </div>
            </label>
          ))}
        </div>
      )}

      {/* 옵션 */}
      {problems && selectedNumbers.size > 0 && (
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
            <span className="text-xs font-semibold text-gray-500 dark:text-[#7880AA] uppercase tracking-wide ml-2">난이도</span>
            {DIFFS.map((d) => (
              <button key={d.value} onClick={() => setDifficulty(d.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  difficulty === d.value
                    ? 'bg-violet-600 dark:bg-violet-500 text-white'
                    : 'bg-white dark:bg-[#191C2E] text-gray-600 dark:text-[#7880AA] border border-gray-200 dark:border-[#2E3356] hover:bg-gray-50 dark:hover:bg-[#212540]'
                }`}>{d.label}</button>
            ))}
          </div>
          <input type="text" value={customPrompt} onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder="추가 지시사항 (선택)"
            className="w-full px-3 py-2.5 border border-indigo-200 dark:border-[#2E3356] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500 bg-white dark:bg-[#191C2E] text-gray-700 dark:text-[#E8EAFF] placeholder:text-gray-400 dark:placeholder:text-[#444A6E] transition-colors" />
          <div className="flex gap-2.5">
            <button onClick={handleGenerate} disabled={isLoading}
              className="flex-1 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg font-semibold text-sm hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all shadow-[0_2px_12px_rgba(108,127,255,0.25)]">
              {isLoading ? `생성 중... (${selectedNumbers.size}문제)` : `✦ ${selectedNumbers.size}문제 유사문항 생성`}
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
        <div className="text-center py-6">
          <div className="inline-block w-8 h-8 border-[3px] border-indigo-200 dark:border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
          <p className="text-gray-400 dark:text-[#7880AA] text-sm mt-3">{selectedNumbers.size}개 문제 유사문항 생성 중...</p>
        </div>
      )}

      {/* 결과 */}
      {batchResults && (
        <div className="space-y-6">
          {batchResults.map((r, i) => (
            <div key={i} className="bg-white dark:bg-[#11131F] rounded-xl border border-gray-200 dark:border-[#222644] p-5 shadow-sm">
              <h3 className="font-bold text-gray-800 dark:text-[#E8EAFF] mb-3">{r.number}번 유사문항</h3>
              <div className="text-gray-700 dark:text-[#C8CADF] text-sm leading-relaxed">
                <LatexRenderer text={hwpToLatex(r.result)} />
              </div>
              <UsageInfo usage={r.usage} />

              {/* 수정 요청 */}
              <div className="mt-3 pt-3 border-t border-gray-100 dark:border-[#222644]">
                <div className="flex gap-2">
                  <input type="text" value={i === batchResults.length - 1 ? refineText : ''}
                    onChange={(e) => setRefineText(e.target.value)}
                    placeholder="수정 요청 (예: 답을 다른 값으로, 조건을 단순하게)"
                    className="flex-1 px-3 py-2 border border-amber-200 dark:border-amber-500/20 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-amber-400/30 bg-white dark:bg-[#191C2E] text-gray-700 dark:text-[#E8EAFF] placeholder:text-gray-400 dark:placeholder:text-[#444A6E]" />
                  <button onClick={() => handleRefine(i)} disabled={isRefining || !refineText.trim()}
                    className="px-3 py-2 bg-amber-500 dark:bg-amber-600 text-white rounded-lg text-xs font-medium hover:bg-amber-600 dark:hover:bg-amber-500 disabled:opacity-50 transition-colors">
                    {isRefining ? '수정 중...' : '수정'}
                  </button>
                </div>
              </div>
            </div>
          ))}

          {usage && (
            <div className="p-3 bg-gray-50 dark:bg-[#191C2E] rounded-lg border border-gray-200 dark:border-[#2E3356] text-xs text-gray-500 dark:text-[#7880AA]">
              총 비용: ${usage.cost_usd?.toFixed(4)} (약 {Math.round(usage.cost_krw || 0).toLocaleString()}원) | 총 토큰: {(usage.total_tokens || 0).toLocaleString()}
            </div>
          )}
        </div>
      )}

      {downloadId && (
        <button onClick={handleDownload}
          className="w-full py-2.5 bg-gradient-to-r from-orange-500 to-amber-500 text-white rounded-lg font-semibold text-sm hover:from-orange-400 hover:to-amber-400 transition-all shadow-[0_2px_12px_rgba(245,158,11,0.25)]">
          한글 파일(.hwpx) 다운로드
        </button>
      )}
    </div>
  )
}
