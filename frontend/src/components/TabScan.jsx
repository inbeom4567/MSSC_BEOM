import { useState, useCallback, useEffect } from 'react'
import CropEditor from './CropEditor'
import ScanResultCard from './ScanResultCard'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'


export default function TabScan({ grade, model, onStatusChange }) {
  const [step, setStep] = useState('upload')  // upload | detecting | editing | selecting | processing | done
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [detectData, setDetectData] = useState(null)
  const [confirmedBboxes, setConfirmedBboxes] = useState([])
  const outputMode = 'type_only'
  const [cards, setCards] = useState([])
  const [error, setError] = useState(null)
  const [hwpxUrl, setHwpxUrl] = useState(null)

  // 부모에게 처리 상태 알림
  useEffect(() => {
    if (!onStatusChange) return
    if (step === 'processing') {
      const completed = cards.filter(c => c.status === 'done' || c.status === 'error').length
      onStatusChange({ processing: true, step, total: cards.length, completed })
    } else if (step === 'done') {
      onStatusChange({ processing: false, step, total: cards.length, completed: cards.length })
    } else {
      onStatusChange(null)
    }
  }, [step, cards, onStatusChange])

  const handleFile = useCallback((f) => {
    if (!f) return
    const isPdf = f.type === 'application/pdf' || f.name?.toLowerCase().endsWith('.pdf')
    const isImage = f.type.startsWith('image/')
    if (!isPdf && !isImage) return
    setFile(f)
    setStep('upload')
    setDetectData(null)
    setCards([])
    setError(null)
    setHwpxUrl(null)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }, [handleFile])

  const handlePaste = useCallback((e) => {
    for (const item of e.clipboardData?.items || []) {
      if (item.type.startsWith('image/')) { handleFile(item.getAsFile()); break }
    }
  }, [handleFile])

  const handleDetect = async () => {
    if (!file) return
    setStep('detecting')
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${API}/api/scan-detect`, { method: 'POST', body: fd })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '감지 실패') }
      const data = await res.json()
      setDetectData(data)
      setStep('editing')
    } catch (e) {
      setError(e.message)
      setStep('upload')
    }
  }

  const handleConfirm = (bboxes) => {
    setConfirmedBboxes(bboxes)
    handleProcess(bboxes)
  }

  const handleProcess = async (bboxes) => {
    const resolved = bboxes || confirmedBboxes
    const selected = resolved.filter(b => b.selected)
    if (selected.length === 0) return

    setCards(selected.map(bb => ({
      problemId: bb.id, label: bb.label, status: 'pending',
      result: null, graphs: [], ocrData: null, outputMode, error: null,
    })))
    setStep('processing')
    setError(null)

    try {
      const res = await fetch(`${API}/api/scan-crop-process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pages: detectData.pages,
          confirmed_bboxes: resolved,
          output_mode: 'type_only',
          variant_count: 1,
          model,
          grade,
          is_student_paper: false,
        }),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '처리 실패') }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'progress') {
              setCards(prev => prev.map(c => c.problemId === event.problem_id ? { ...c, status: 'processing' } : c))
            } else if (event.type === 'result') {
              setCards(prev => prev.map(c => c.problemId === event.problem_id ? {
                ...c, status: 'done', result: event.result, graphs: event.graphs || [],
                ocrData: event.ocr_data, outputMode: event.output_mode,
              } : c))
            } else if (event.type === 'error') {
              setCards(prev => prev.map(c => c.problemId === event.problem_id ? { ...c, status: 'error', error: event.error } : c))
            } else if (event.type === 'done') {
              setStep('done')
            }
          } catch { /* JSON 파싱 실패 무시 */ }
        }
      }
    } catch (e) {
      setError(e.message)
    }
  }

  const handleHwpxDownload = async () => {
    const doneCards = cards.filter(c => c.status === 'done' && c.result)
    if (doneCards.length === 0) return
    try {
      const res = await fetch(`${API}/api/text-to-hwpx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          texts: doneCards.map(c => c.result),
          filename: 'scan_result',
        }),
      })
      if (!res.ok) throw new Error('HWPX 생성 실패')
      const data = await res.json()
      window.location.href = `${API}/api/hwpx-download/${data.download_id}`
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div onPaste={handlePaste} tabIndex={0} className="outline-none space-y-4">

      {/* ── 1단계: 업로드 ── */}
      {(step === 'upload' || step === 'detecting') && (
        <>
          <div className="bg-white dark:bg-[#22252E] rounded-xl border border-gray-200 dark:border-[#353844] p-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-700 dark:text-[#E2E4F0] mb-4">스캔 이미지 업로드</h2>
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => document.getElementById('scan-file-input').click()}
              className={`relative border-2 border-dashed rounded-xl cursor-pointer transition-all ${dragging ? 'border-sky-500 bg-sky-50 dark:bg-sky-500/10' : 'border-gray-300 dark:border-[#353844] hover:border-sky-400 dark:hover:border-violet-500 hover:bg-gray-50 dark:hover:bg-violet-500/5'} ${file ? 'p-2' : 'p-10'}`}
            >
              <input id="scan-file-input" type="file" accept="image/*,application/pdf" className="hidden"
                onChange={e => handleFile(e.target.files[0])} />
              {file ? (
                <div className="flex items-center gap-3 p-3">
                  <div className="text-3xl">{file.type === 'application/pdf' ? '📄' : '🖼'}</div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-700 dark:text-[#E2E4F0]">{file.name}</p>
                    <p className="text-xs text-gray-400 dark:text-[#5A5E70]">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
                  </div>
                  <button onClick={e => { e.stopPropagation(); setFile(null) }}
                    className="bg-red-500 text-white rounded-full w-6 h-6 text-xs flex items-center justify-center hover:bg-red-600">×</button>
                </div>
              ) : (
                <div className="text-center text-gray-400 dark:text-[#5A5E70]">
                  <div className="text-4xl mb-2">📷</div>
                  <p className="text-sm font-medium">클릭하거나 이미지/PDF를 드래그하세요</p>
                  <p className="text-xs mt-1">붙여넣기(Ctrl+V)도 가능합니다 · JPG, PNG, PDF 지원</p>
                </div>
              )}
            </div>
          </div>

          <button onClick={handleDetect} disabled={!file || step === 'detecting'}
            className="w-full py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-sky-500 to-blue-600 dark:from-violet-600 dark:to-purple-700 hover:from-sky-400 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed shadow-md transition-all">
            {step === 'detecting' ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                AI가 문제 영역을 감지하는 중...
              </span>
            ) : '✦ 분석 시작'}
          </button>
        </>
      )}

      {/* ── 2단계: 크롭 수정 ── */}
      {step === 'editing' && detectData && (
        <>
          <div className="flex items-center gap-3 mb-2">
            <button onClick={() => setStep('upload')} className="text-sm text-gray-500 dark:text-[#5A5E70] hover:underline">← 다시 업로드</button>
            <h2 className="text-base font-semibold text-gray-700 dark:text-[#E2E4F0]">문제 영역 수정</h2>
          </div>
          <CropEditor pages={detectData.pages} onConfirm={handleConfirm} />
        </>
      )}


      {/* 에러 */}
      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* ── 4단계: 처리 결과 ── */}
      {(step === 'processing' || step === 'done') && cards.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-700 dark:text-[#E2E4F0]">처리 결과</h2>
            {step === 'done' && (
              <div className="flex gap-2">
                <button onClick={() => { setStep('upload'); setFile(null); setCards([]) }}
                  className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#5A5E70] hover:bg-gray-50 dark:hover:bg-[#2A2D38]">
                  처음부터
                </button>
                <button onClick={handleHwpxDownload}
                  className="text-sm px-3 py-1.5 rounded-lg font-semibold text-white bg-gradient-to-r from-sky-500 to-blue-600 dark:from-violet-600 dark:to-purple-700">
                  📥 전체 다운로드
                </button>
              </div>
            )}
          </div>
          {cards.map(card => (
            <ScanResultCard key={card.problemId} {...card} model={model} grade={grade} />
          ))}
        </div>
      )}
    </div>
  )
}
