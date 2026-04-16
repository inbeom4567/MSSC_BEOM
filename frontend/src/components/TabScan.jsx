import { useState, useCallback } from 'react'
import SolutionDisplay from './SolutionDisplay'
import UsageInfo from './UsageInfo'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const MODES = [
  { value: 'general', label: '일반 스캔', desc: '문제지, 교재, 시험지' },
  { value: 'student', label: '학생 시험지', desc: '손필기 / 인쇄 구분' },
]

export default function TabScan({ grade, model }) {
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [mode, setMode] = useState('general')
  const [variantCount, setVariantCount] = useState(1)
  const [dragging, setDragging] = useState(false)

  const [result, setResult] = useState(null)
  const [graphs, setGraphs] = useState([])
  const [ocrData, setOcrData] = useState(null)
  const [usage, setUsage] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFile = useCallback((f) => {
    if (!f || !f.type.startsWith('image/')) return
    setImageFile(f)
    const reader = new FileReader()
    reader.onload = (e) => setImagePreview(e.target.result)
    reader.readAsDataURL(f)
    setResult(null)
    setOcrData(null)
    setError(null)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }, [handleFile])

  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        handleFile(item.getAsFile())
        break
      }
    }
  }, [handleFile])

  const handleSubmit = async () => {
    if (!imageFile) { setError('이미지를 업로드하세요.'); return }
    setIsLoading(true); setError(null); setResult(null)

    const fd = new FormData()
    fd.append('files', imageFile)
    fd.append('mode', mode)
    fd.append('variant_count', variantCount)
    fd.append('model', model)
    fd.append('grade', grade)

    try {
      const res = await fetch(`${API}/api/scan-process`, { method: 'POST', body: fd })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '처리 실패')
      }
      const data = await res.json()
      setResult(data.result)
      setGraphs(data.graphs || [])
      setOcrData(data.ocr_data)
      setUsage(data.usage)
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }

  const parseSections = (text) => {
    if (!text) return {}
    const sections = {}
    const tagPattern = /-(문제|해설|정답|유사문항\d+|유사해설\d+|유사정답\d+)-\n([\s\S]*?)(?=\n-[가-힣\d]+-\n|$)/g
    let m
    while ((m = tagPattern.exec(text)) !== null) {
      sections[m[1]] = m[2].trim()
    }
    return sections
  }

  const sections = parseSections(result)
  const variantNums = Array.from({ length: variantCount }, (_, i) => i + 1)

  return (
    <div onPaste={handlePaste} tabIndex={0} className="outline-none space-y-4">
      {/* 이미지 업로드 */}
      <div className="bg-white dark:bg-[#11131F] rounded-xl border border-gray-200 dark:border-[#222644] p-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-700 dark:text-[#E8EAFF] mb-4">스캔 이미지 업로드</h2>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('scan-file-input').click()}
          className={`relative border-2 border-dashed rounded-xl cursor-pointer transition-all ${
            dragging
              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10'
              : 'border-gray-300 dark:border-[#2E3356] hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-gray-50 dark:hover:bg-indigo-500/5'
          } ${imagePreview ? 'p-2' : 'p-10'}`}
        >
          <input id="scan-file-input" type="file" accept="image/*" className="hidden"
            onChange={(e) => handleFile(e.target.files[0])} />
          {imagePreview ? (
            <div className="relative">
              <img src={imagePreview} alt="업로드된 스캔" className="max-h-72 mx-auto rounded-lg object-contain" />
              <button
                onClick={(e) => { e.stopPropagation(); setImageFile(null); setImagePreview(null); setResult(null) }}
                className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 text-xs flex items-center justify-center hover:bg-red-600"
              >
                ×
              </button>
            </div>
          ) : (
            <div className="text-center text-gray-400 dark:text-[#444A6E]">
              <div className="text-4xl mb-2">📷</div>
              <p className="text-sm font-medium">클릭하거나 이미지를 드래그하세요</p>
              <p className="text-xs mt-1">붙여넣기(Ctrl+V)도 가능합니다</p>
            </div>
          )}
        </div>
      </div>

      {/* 옵션 */}
      <div className="bg-white dark:bg-[#11131F] rounded-xl border border-gray-200 dark:border-[#222644] p-5 shadow-sm">
        <div className="flex flex-wrap gap-6">
          <div>
            <p className="text-xs font-semibold text-gray-500 dark:text-[#7880AA] uppercase tracking-wide mb-2">처리 모드</p>
            <div className="flex gap-2">
              {MODES.map((m) => (
                <button key={m.value} onClick={() => setMode(m.value)}
                  className={`px-3 py-2 rounded-lg text-sm border transition-colors ${
                    mode === m.value
                      ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 font-medium'
                      : 'border-gray-200 dark:border-[#2E3356] text-gray-600 dark:text-[#7880AA] hover:bg-gray-50 dark:hover:bg-[#191C2E]'
                  }`}
                >
                  <div className="font-medium">{m.label}</div>
                  <div className="text-xs opacity-70">{m.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold text-gray-500 dark:text-[#7880AA] uppercase tracking-wide mb-2">유사문항 수</p>
            <div className="flex gap-2">
              {[1, 2].map((n) => (
                <button key={n} onClick={() => setVariantCount(n)}
                  className={`px-4 py-2 rounded-lg text-sm border transition-colors ${
                    variantCount === n
                      ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 font-medium'
                      : 'border-gray-200 dark:border-[#2E3356] text-gray-600 dark:text-[#7880AA] hover:bg-gray-50 dark:hover:bg-[#191C2E]'
                  }`}
                >
                  {n}개
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 실행 버튼 */}
      <button onClick={handleSubmit} disabled={!imageFile || isLoading}
        className="w-full py-3 rounded-xl font-semibold text-white transition-all bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_2px_12px_rgba(108,127,255,0.25)]">
        {isLoading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            처리 중...
          </span>
        ) : '✦ 스캔 처리 시작'}
      </button>

      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 rounded-xl text-sm">
          {error}
        </div>
      )}

      {ocrData && <OcrPreview ocrData={ocrData} mode={mode} />}

      {result && (
        <div className="space-y-4">
          {sections['문제'] && (
            <SolutionDisplay solution={sections['문제']} graphs={graphs} title="문제 (HWP 형식)" />
          )}
          {sections['해설'] && (
            <SolutionDisplay
              solution={(sections['정답'] ? `-정답-\n${sections['정답']}\n\n` : '') + sections['해설']}
              graphs={graphs}
              title="해설"
            />
          )}
          {variantNums.map((n) => (
            sections[`유사문항${n}`] && (
              <SolutionDisplay
                key={n}
                solution={
                  sections[`유사문항${n}`] +
                  (sections[`유사정답${n}`] ? `\n\n-정답-\n${sections[`유사정답${n}`]}` : '') +
                  (sections[`유사해설${n}`] ? `\n\n-해설-\n${sections[`유사해설${n}`]}` : '')
                }
                graphs={graphs}
                title={`유사문항 ${n}`}
              />
            )
          ))}
          {usage && <UsageInfo usage={usage} />}
        </div>
      )}
    </div>
  )
}

function OcrPreview({ ocrData, mode }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="bg-gray-50 dark:bg-[#191C2E] rounded-xl border border-gray-200 dark:border-[#222644] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-600 dark:text-[#7880AA] hover:bg-gray-100 dark:hover:bg-[#212540] transition-colors"
      >
        <span>OCR 인식 결과 보기</span>
        <svg className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="px-4 pb-4 text-xs text-gray-600 dark:text-[#7880AA] space-y-3 font-mono">
          {mode === 'student' ? (
            <>
              {ocrData.printed && (
                <div>
                  <p className="font-semibold text-gray-500 dark:text-[#7880AA] mb-1 font-sans">인쇄 텍스트</p>
                  <pre className="whitespace-pre-wrap bg-white dark:bg-[#11131F] border border-gray-200 dark:border-[#222644] rounded p-2">{ocrData.printed}</pre>
                </div>
              )}
              {ocrData.handwriting && (
                <div>
                  <p className="font-semibold text-gray-500 dark:text-[#7880AA] mb-1 font-sans">손필기 (학생 답안)</p>
                  <pre className="whitespace-pre-wrap bg-amber-50 dark:bg-amber-500/5 border border-amber-200 dark:border-amber-500/20 rounded p-2">{ocrData.handwriting}</pre>
                </div>
              )}
              {ocrData.student_answer && (
                <div>
                  <p className="font-semibold text-gray-500 dark:text-[#7880AA] mb-1 font-sans">학생 최종 답</p>
                  <pre className="whitespace-pre-wrap bg-emerald-50 dark:bg-emerald-500/5 border border-emerald-200 dark:border-emerald-500/20 rounded p-2">{ocrData.student_answer}</pre>
                </div>
              )}
            </>
          ) : (
            <>
              {ocrData.problem && (
                <div>
                  <p className="font-semibold text-gray-500 dark:text-[#7880AA] mb-1 font-sans">문제</p>
                  <pre className="whitespace-pre-wrap bg-white dark:bg-[#11131F] border border-gray-200 dark:border-[#222644] rounded p-2">{ocrData.problem}</pre>
                </div>
              )}
              {ocrData.solution && (
                <div>
                  <p className="font-semibold text-gray-500 dark:text-[#7880AA] mb-1 font-sans">해설 (원본)</p>
                  <pre className="whitespace-pre-wrap bg-white dark:bg-[#11131F] border border-gray-200 dark:border-[#222644] rounded p-2">{ocrData.solution}</pre>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
