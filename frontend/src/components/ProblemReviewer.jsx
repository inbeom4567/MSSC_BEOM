import { useState, useEffect } from 'react'

/**
 * ProblemReviewer
 * props:
 *   pages: [{page_index, image_base64, media_type, bboxes}]
 *   bboxes: [{id, page_index, x, y, w, h, label, selected}]
 *   onConfirm: (selectedBboxes: array) => void  — 포함된 문제만 전달
 *   onBack: () => void  — 크롭 편집으로 돌아가기
 */
export default function ProblemReviewer({ pages, bboxes, onConfirm, onBack }) {
  const [inclusions, setInclusions] = useState(
    () => Object.fromEntries(bboxes.map(b => [b.id, b.selected !== false]))
  )
  const [currentIdx, setCurrentIdx] = useState(0)
  const [cropUrls, setCropUrls] = useState({})

  const items = bboxes

  // 모든 문제의 크롭 이미지 생성
  useEffect(() => {
    let cancelled = false
    const generate = async () => {
      const urls = {}
      for (const bb of items) {
        if (cancelled) break
        const page = pages.find(p => p.page_index === bb.page_index)
        if (!page) continue
        try {
          const url = await cropToDataUrl(page.image_base64, page.media_type, bb.x, bb.y, bb.w, bb.h)
          urls[bb.id] = url
        } catch { /* 실패 시 로딩 표시 유지 */ }
      }
      if (!cancelled) setCropUrls(urls)
    }
    generate()
    return () => { cancelled = true }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const current = items[currentIdx]
  const included = current ? inclusions[current.id] : false
  const includedCount = Object.values(inclusions).filter(Boolean).length

  const toggleCurrent = (val) => {
    if (!current) return
    setInclusions(prev => ({ ...prev, [current.id]: val }))
  }

  const selectAll = (val) => {
    setInclusions(Object.fromEntries(items.map(b => [b.id, val])))
  }

  const handleConfirm = () => {
    const selected = items.filter(b => inclusions[b.id])
    onConfirm(selected)
  }

  const isDark = document.documentElement.classList.contains('dark')
  const colors = isDark
    ? { bg: '#22252E', card: '#2A2D38', border: '#353844', text: '#E2E4F0', muted: '#5A5E70', accent: '#8B5CF6' }
    : { bg: '#F4F5F7', card: '#FFFFFF', border: '#DDE1E9', text: '#374151', muted: '#9AA0B0', accent: '#0EA5E9' }

  return (
    <div style={{ background: colors.bg, borderRadius: 12, border: `1px solid ${colors.border}`, overflow: 'hidden' }}>
      {/* 헤더 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: colors.card, borderBottom: `1px solid ${colors.border}`, flexWrap: 'wrap' }}>
        <button onClick={onBack}
          style={{ fontSize: 12, color: colors.muted, background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px' }}>
          ← 크롭 수정
        </button>
        <span style={{ fontSize: 14, fontWeight: 700, color: colors.text }}>문제 검토</span>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: colors.muted }}>
          {includedCount}/{items.length}개 포함
        </span>
        <button onClick={() => selectAll(true)}
          style={{ fontSize: 11, padding: '4px 12px', borderRadius: 6, border: `1px solid ${colors.border}`, background: 'transparent', color: colors.muted, cursor: 'pointer' }}>
          전체 포함
        </button>
        <button onClick={() => selectAll(false)}
          style={{ fontSize: 11, padding: '4px 12px', borderRadius: 6, border: `1px solid ${colors.border}`, background: 'transparent', color: colors.muted, cursor: 'pointer' }}>
          전체 제외
        </button>
      </div>

      {/* 본문 */}
      <div style={{ display: 'flex', minHeight: 400 }}>
        {/* 메인 뷰어 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, gap: 16 }}>
          {current ? (
            <>
              {/* 크롭 이미지 */}
              <div style={{
                border: `3px solid ${included ? colors.accent : '#6B7280'}`,
                borderRadius: 10, overflow: 'hidden',
                maxWidth: '100%', opacity: included ? 1 : 0.5,
                transition: 'border-color .2s, opacity .2s'
              }}>
                {cropUrls[current.id] ? (
                  <img
                    src={cropUrls[current.id]}
                    alt={current.label}
                    style={{ display: 'block', maxWidth: 480, maxHeight: 360, objectFit: 'contain' }}
                  />
                ) : (
                  <div style={{ width: 480, height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.muted, fontSize: 13, background: isDark ? '#1A1D24' : '#F4F5F7' }}>
                    이미지 로딩 중...
                  </div>
                )}
              </div>

              {/* 라벨 */}
              <div style={{ fontSize: 14, fontWeight: 600, color: colors.text }}>{current.label}</div>

              {/* 포함/제외 버튼 */}
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={() => toggleCurrent(true)}
                  style={{
                    padding: '8px 28px', borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: 'pointer',
                    border: `2px solid ${included ? colors.accent : colors.border}`,
                    background: included ? `${colors.accent}22` : 'transparent',
                    color: included ? colors.accent : colors.muted,
                    transition: 'all .15s'
                  }}>
                  ✓ 포함
                </button>
                <button
                  onClick={() => toggleCurrent(false)}
                  style={{
                    padding: '8px 28px', borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: 'pointer',
                    border: `2px solid ${!included ? '#EF4444' : colors.border}`,
                    background: !included ? '#EF444422' : 'transparent',
                    color: !included ? '#EF4444' : colors.muted,
                    transition: 'all .15s'
                  }}>
                  ✕ 제외
                </button>
              </div>

              {/* prev/next */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <button
                  onClick={() => setCurrentIdx(i => Math.max(0, i - 1))}
                  disabled={currentIdx === 0}
                  style={{
                    padding: '6px 18px', borderRadius: 7, fontSize: 13, fontWeight: 600,
                    cursor: currentIdx === 0 ? 'not-allowed' : 'pointer',
                    border: `1px solid ${colors.border}`, background: 'transparent',
                    color: colors.muted, opacity: currentIdx === 0 ? 0.4 : 1
                  }}>
                  ◀ 이전
                </button>
                <span style={{ fontSize: 12, color: colors.muted }}>{currentIdx + 1} / {items.length}</span>
                <button
                  onClick={() => setCurrentIdx(i => Math.min(items.length - 1, i + 1))}
                  disabled={currentIdx === items.length - 1}
                  style={{
                    padding: '6px 18px', borderRadius: 7, fontSize: 13, fontWeight: 600,
                    cursor: currentIdx === items.length - 1 ? 'not-allowed' : 'pointer',
                    border: `1px solid ${colors.border}`, background: 'transparent',
                    color: colors.muted, opacity: currentIdx === items.length - 1 ? 0.4 : 1
                  }}>
                  다음 ▶
                </button>
              </div>
            </>
          ) : (
            <div style={{ color: colors.muted, fontSize: 14 }}>감지된 문제가 없습니다.</div>
          )}
        </div>

        {/* 사이드바 */}
        <div style={{ width: 180, borderLeft: `1px solid ${colors.border}`, overflowY: 'auto', background: colors.bg }}>
          {items.map((bb, idx) => (
            <div
              key={bb.id}
              onClick={() => setCurrentIdx(idx)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '10px 12px', cursor: 'pointer', fontSize: 12,
                borderBottom: `1px solid ${colors.border}`,
                background: idx === currentIdx ? `${colors.accent}15` : 'transparent',
                color: inclusions[bb.id] ? colors.text : colors.muted
              }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                background: inclusions[bb.id] ? colors.accent : '#6B7280'
              }} />
              <span style={{ flex: 1 }}>{bb.label}</span>
              {!inclusions[bb.id] && (
                <span style={{ fontSize: 10, color: '#EF4444' }}>제외</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 처리 시작 버튼 */}
      <div style={{ padding: 16, borderTop: `1px solid ${colors.border}`, background: colors.card }}>
        <button
          onClick={handleConfirm}
          disabled={includedCount === 0}
          style={{
            width: '100%', padding: '12px 0', borderRadius: 9,
            fontWeight: 700, fontSize: 14, color: 'white',
            background: `linear-gradient(to right, ${colors.accent}, ${isDark ? '#6D28D9' : '#0284C7'})`,
            border: 'none',
            cursor: includedCount === 0 ? 'not-allowed' : 'pointer',
            opacity: includedCount === 0 ? 0.4 : 1
          }}>
          ✦ {includedCount}개 문제 처리 시작
        </button>
      </div>
    </div>
  )
}

// Canvas로 이미지 영역 크롭 → dataURL
function cropToDataUrl(base64, mediaType, x, y, w, h) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const sw = img.naturalWidth
      const sh = img.naturalHeight
      const canvas = document.createElement('canvas')
      canvas.width = Math.max(1, Math.round(sw * w))
      canvas.height = Math.max(1, Math.round(sh * h))
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, Math.round(sw * x), Math.round(sh * y), canvas.width, canvas.height, 0, 0, canvas.width, canvas.height)
      resolve(canvas.toDataURL('image/jpeg', 0.92))
    }
    img.onerror = reject
    img.src = `data:${mediaType};base64,${base64}`
  })
}
