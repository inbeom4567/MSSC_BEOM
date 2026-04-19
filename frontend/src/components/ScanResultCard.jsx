import { useState, useEffect } from 'react'
import SolutionDisplay from './SolutionDisplay'
import FormulaEditor from './FormulaEditor'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

export default function ScanResultCard({ problemId, label, status, result, graphs, ocrData, outputMode, error, model, grade, onResultChange }) {
  const [open, setOpen] = useState(true)
  const [editing, setEditing] = useState(false)
  const [draftResult, setDraftResult] = useState(result || '')
  const [extraMode, setExtraMode] = useState(null)

  useEffect(() => {
    setDraftResult(result || '')
  }, [result])
  const [extraResult, setExtraResult] = useState(null)
  const [extraGraphs, setExtraGraphs] = useState([])
  const [extraLoading, setExtraLoading] = useState(false)
  const [extraError, setExtraError] = useState(null)

  const handleExtra = async (mode) => {
    if (!ocrData) return
    setExtraMode(mode)
    setExtraLoading(true)
    setExtraError(null)
    try {
      const res = await fetch(`${API}/api/scan-generate-variants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ocr_data: ocrData,
          scan_mode: 'general',
          variant_count: 1,
          model,
          grade,
          output_mode: mode === 'solution' ? 'type_with_solution' : 'variant',
        }),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '실패') }
      const data = await res.json()
      setExtraResult(data.result)
      setExtraGraphs(data.graphs || [])
    } catch (e) {
      setExtraError(e.message)
    } finally {
      setExtraLoading(false)
    }
  }

  const statusBadge = {
    pending: { label: '대기 중', color: '#6B7280', bg: '#6B728022' },
    processing: { label: '처리 중...', color: '#F59E0B', bg: '#F59E0B22' },
    done: { label: '완료', color: '#22C55E', bg: '#22C55E22' },
    error: { label: '오류', color: '#EF4444', bg: '#EF444422' },
  }[status] || { label: status, color: '#6B7280', bg: '#6B728022' }

  return (
    <div className="rounded-xl border border-gray-200 dark:border-[#353844] overflow-hidden">
      {/* 헤더 */}
      <div
        onClick={() => status === 'done' && setOpen(o => !o)}
        className="flex items-center gap-3 px-4 py-3 bg-gray-50 dark:bg-[#2A2D38] cursor-pointer select-none"
      >
        <span className="font-semibold text-sm text-gray-800 dark:text-[#E2E4F0]">{label}</span>
        <span style={{ background: statusBadge.bg, color: statusBadge.color }} className="text-xs font-semibold px-2 py-0.5 rounded-full">
          {statusBadge.label}
          {status === 'processing' && (
            <svg className="inline animate-spin h-3 w-3 ml-1" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          )}
        </span>
        {status === 'done' && result && (
          <button
            onClick={e => { e.stopPropagation(); setEditing(prev => !prev) }}
            className="text-xs px-3 py-1 rounded-lg border border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#A0A4B8] hover:bg-gray-100 dark:hover:bg-[#353844]">
            {editing ? '✕ 닫기' : '✎ 수정'}
          </button>
        )}
        {status === 'done' && outputMode === 'type_only' && !extraResult && (
          <div className="ml-auto flex gap-2">
            <button
              onClick={e => { e.stopPropagation(); handleExtra('solution') }}
              disabled={extraLoading}
              className="text-xs px-3 py-1 rounded-lg border border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#A0A4B8] hover:bg-gray-100 dark:hover:bg-[#353844] disabled:opacity-40"
            >
              {extraLoading && extraMode === 'solution' ? '생성 중...' : '+ 해설 추가'}
            </button>
            <button
              onClick={e => { e.stopPropagation(); handleExtra('variant') }}
              disabled={extraLoading}
              className="text-xs px-3 py-1 rounded-lg border border-gray-200 dark:border-[#353844] text-gray-600 dark:text-[#A0A4B8] hover:bg-gray-100 dark:hover:bg-[#353844] disabled:opacity-40"
            >
              {extraLoading && extraMode === 'variant' ? '생성 중...' : '+ 유사문항'}
            </button>
          </div>
        )}
        {status === 'done' && (
          <svg className={`w-4 h-4 transition-transform text-gray-400 dark:text-[#5A5E70] ${open ? '' : 'rotate-180'} ${status === 'done' && outputMode === 'type_only' ? '' : 'ml-auto'}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </div>

      {/* 본문 */}
      {open && status === 'done' && (
        <div className="p-4 bg-white dark:bg-[#22252E]">
          {editing ? (
            <FormulaEditor
              value={draftResult}
              onChange={setDraftResult}
              onSave={() => {
                onResultChange?.(problemId, draftResult)
                setEditing(false)
              }}
              onCancel={() => {
                setDraftResult(result || '')
                setEditing(false)
              }}
            />
          ) : (
            result && <SolutionDisplay solution={result} graphs={graphs} title={label} />
          )}
          {extraError && (
            <div className="mt-3 p-2 text-xs text-red-500 bg-red-50 dark:bg-red-500/10 rounded-lg">{extraError}</div>
          )}
          {extraResult && (
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-[#353844]">
              <SolutionDisplay solution={extraResult} graphs={extraGraphs} title={extraMode === 'solution' ? '해설' : '유사문항'} />
            </div>
          )}
        </div>
      )}
      {status === 'error' && error && (
        <div className="px-4 py-3 text-sm text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-500/5">
          {error}
        </div>
      )}
    </div>
  )
}
