import { useState, useRef, useCallback, useEffect } from 'react'

// 다크/브라이트 테마 색상
// 브라이트(B3): bg #F4F5F7, sidebar #E8EAEF, accent #0EA5E9
// 다크(D3): bg #22252E, sidebar #2A2D38, accent #8B5CF6

const HANDLE_SIZE = 9  // px, bbox 핸들 크기

/**
 * CropEditor
 * props:
 *   pages: [{page_index, image_base64, media_type, bboxes: [{id,x,y,w,h,label}]}]
 *   onConfirm: (confirmedBboxes) => void
 *     confirmedBboxes: [{id, page_index, x, y, w, h, label, selected}]
 */
export default function CropEditor({ pages, onConfirm }) {
  const [currentPage, setCurrentPage] = useState(0)
  const [tool, setTool] = useState('select')  // 'select' | 'add'
  const [selectedId, setSelectedId] = useState(null)

  // 전체 bbox 상태: {[id]: {id, page_index, x, y, w, h, label, selected}}
  const [bboxMap, setBboxMap] = useState(() => {
    const map = {}
    pages.forEach(pg => {
      pg.bboxes.forEach(bb => {
        map[bb.id] = { ...bb, page_index: pg.page_index, selected: true }
      })
    })
    return map
  })

  const [zoom, setZoom] = useState(1)

  const imgRef = useRef(null)
  const containerRef = useRef(null)
  const dragState = useRef(null)  // { type, id, startX, startY, origBbox, isNewBox, newId }

  // MutationObserver for reactive dark mode detection
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains('dark'))
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])

  const page = pages[currentPage]
  const pageItems = Object.values(bboxMap).filter(b => b.page_index === currentPage)
  const allItems = Object.values(bboxMap)

  // 렌더링 크기 → 비율 변환 헬퍼
  const toRatio = useCallback((px, py) => {
    const rect = imgRef.current?.getBoundingClientRect()
    if (!rect) return { rx: 0, ry: 0 }
    return { rx: (px - rect.left) / rect.width, ry: (py - rect.top) / rect.height }
  }, [])

  // 마우스 다운: 박스 선택/이동 또는 새 박스 그리기
  const onMouseDown = useCallback((e, bboxId = null, handleDir = null) => {
    e.preventDefault()
    e.stopPropagation()
    const { rx, ry } = toRatio(e.clientX, e.clientY)

    if (tool === 'add' && !bboxId) {
      // 새 박스 그리기 시작
      const newId = `p${currentPage}_b${Date.now()}`
      dragState.current = { type: 'create', newId, startX: rx, startY: ry }
      setBboxMap(prev => ({
        ...prev,
        [newId]: { id: newId, page_index: currentPage, x: rx, y: ry, w: 0, h: 0, label: `문제 ${allItems.length + 1}`, selected: true }
      }))
      setSelectedId(newId)
      return
    }

    if (bboxId) {
      setSelectedId(bboxId)
      const orig = bboxMap[bboxId]
      if (handleDir) {
        dragState.current = { type: 'resize', id: bboxId, handleDir, startX: rx, startY: ry, origBbox: { ...orig } }
      } else {
        dragState.current = { type: 'move', id: bboxId, startX: rx, startY: ry, origBbox: { ...orig } }
      }
    } else {
      setSelectedId(null)
    }
  }, [tool, currentPage, bboxMap, allItems.length, toRatio])

  const onMouseMove = useCallback((e) => {
    if (!dragState.current) return
    const { rx, ry } = toRatio(e.clientX, e.clientY)
    const ds = dragState.current

    if (ds.type === 'move') {
      const dx = rx - ds.startX, dy = ry - ds.startY
      setBboxMap(prev => ({
        ...prev,
        [ds.id]: {
          ...prev[ds.id],
          x: Math.max(0, Math.min(1 - ds.origBbox.w, ds.origBbox.x + dx)),
          y: Math.max(0, Math.min(1 - ds.origBbox.h, ds.origBbox.y + dy)),
        }
      }))
    } else if (ds.type === 'resize') {
      const ob = ds.origBbox
      let { x, y, w, h } = ob
      const dx = rx - ds.startX, dy = ry - ds.startY
      const dir = ds.handleDir
      if (dir.includes('e')) w = Math.max(0.02, ob.w + dx)
      if (dir.includes('s')) h = Math.max(0.02, ob.h + dy)
      if (dir.includes('w')) { x = Math.min(ob.x + ob.w - 0.02, ob.x + dx); w = ob.w - dx }
      if (dir.includes('n')) { y = Math.min(ob.y + ob.h - 0.02, ob.y + dy); h = ob.h - dy }
      setBboxMap(prev => ({ ...prev, [ds.id]: { ...prev[ds.id], x: Math.max(0, x), y: Math.max(0, y), w: Math.min(1 - x, Math.max(0.02, w)), h: Math.min(1 - y, Math.max(0.02, h)) } }))
    } else if (ds.type === 'create') {
      const x = Math.min(ds.startX, rx), y = Math.min(ds.startY, ry)
      const w = Math.abs(rx - ds.startX), h = Math.abs(ry - ds.startY)
      setBboxMap(prev => ({ ...prev, [ds.newId]: { ...prev[ds.newId], x, y, w, h } }))
    }
  }, [toRatio])

  const onMouseUp = useCallback(() => {
    const ds = dragState.current
    if (ds?.type === 'create') {
      // 너무 작으면 제거
      const bb = bboxMap[ds.newId]
      if (bb && (bb.w < 0.02 || bb.h < 0.02)) {
        setBboxMap(prev => { const next = { ...prev }; delete next[ds.newId]; return next })
        setSelectedId(null)
      }
    }
    dragState.current = null
  }, [bboxMap])

  // Delete 키로 선택된 박스 삭제
  useEffect(() => {
    const onKey = (e) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId) {
        setBboxMap(prev => { const next = { ...prev }; delete next[selectedId]; return next })
        setSelectedId(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedId])

  const deleteSelected = () => {
    if (!selectedId) return
    setBboxMap(prev => { const next = { ...prev }; delete next[selectedId]; return next })
    setSelectedId(null)
  }

  const toggleSelection = (id) => {
    setBboxMap(prev => ({ ...prev, [id]: { ...prev[id], selected: !prev[id].selected } }))
  }

  const selectAll = (v) => {
    setBboxMap(prev => Object.fromEntries(Object.entries(prev).map(([k, b]) => [k, { ...b, selected: v }])))
  }

  const handleConfirm = () => {
    onConfirm(Object.values(bboxMap))
  }

  const goToPage = (idx) => {
    const clamped = Math.max(0, Math.min(pages.length - 1, idx))
    setCurrentPage(clamped)
    setSelectedId(null)
  }

  const colors = isDark
    ? { bg: '#22252E', toolbar: '#2A2D38', border: '#353844', page: '#1E2028', sidebar: '#2A2D38', accent: '#8B5CF6', text: '#E2E4F0', muted: '#5A5E70' }
    : { bg: '#F4F5F7', toolbar: '#E8EAEF', border: '#DDE1E9', page: '#FFFFFF', sidebar: '#E8EAEF', accent: '#0EA5E9', text: '#374151', muted: '#9AA0B0' }

  return (
    <div style={{ border: `1px solid ${colors.border}`, borderRadius: 12, overflow: 'hidden', background: colors.bg }}>
      {/* 툴바 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px', background: colors.toolbar, borderBottom: `1px solid ${colors.border}`, flexWrap: 'wrap' }}>
        {/* 도구 버튼 */}
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            { key: 'select', label: '🖱 선택/이동' },
            { key: 'add', label: '➕ 박스 추가' },
          ].map(t => (
            <button key={t.key} onClick={() => setTool(t.key)}
              style={{ padding: '5px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer', border: `1px solid ${tool === t.key ? colors.accent : colors.border}`, background: tool === t.key ? `${colors.accent}22` : colors.toolbar, color: tool === t.key ? colors.accent : colors.muted }}>
              {t.label}
            </button>
          ))}
          <button onClick={deleteSelected} disabled={!selectedId}
            style={{ padding: '5px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: selectedId ? 'pointer' : 'not-allowed', border: '1px solid #f87171', background: 'transparent', color: '#f87171', opacity: selectedId ? 1 : 0.4 }}>
            🗑 삭제
          </button>
        </div>
        <div style={{ width: 1, height: 22, background: colors.border, margin: '0 4px' }} />
        {/* 줌 컨트롤 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button onClick={() => setZoom(z => Math.max(0.5, +(z - 0.25).toFixed(2)))}
            style={{ padding: '4px 10px', borderRadius: 5, fontSize: 13, fontWeight: 700, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.toolbar, color: colors.text }}>−</button>
          <span style={{ fontSize: 11, minWidth: 38, textAlign: 'center', color: colors.muted }}>{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom(z => Math.min(3, +(z + 0.25).toFixed(2)))}
            style={{ padding: '4px 10px', borderRadius: 5, fontSize: 13, fontWeight: 700, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.toolbar, color: colors.text }}>＋</button>
          {zoom !== 1 && (
            <button onClick={() => setZoom(1)}
              style={{ padding: '4px 8px', borderRadius: 5, fontSize: 11, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.toolbar, color: colors.muted }}>원본</button>
          )}
        </div>
        <div style={{ width: 1, height: 22, background: colors.border, margin: '0 4px' }} />
        {/* 페이지 네비 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: colors.muted }}>
          {[
            { label: '|◀ 처음', action: () => goToPage(0) },
            { label: '◀ 이전', action: () => goToPage(currentPage - 1) },
          ].map(b => (
            <button key={b.label} onClick={b.action}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.toolbar, color: colors.muted }}>
              {b.label}
            </button>
          ))}
          <input
            type="number" min={1} max={pages.length}
            value={currentPage + 1}
            onChange={e => goToPage(Number(e.target.value) - 1)}
            style={{ width: 44, textAlign: 'center', background: colors.bg, border: `1px solid ${colors.border}`, borderRadius: 5, color: colors.text, fontSize: 12, padding: '3px 4px' }}
          />
          <span>/ {pages.length}</span>
          {[
            { label: '다음 ▶', action: () => goToPage(currentPage + 1) },
            { label: '마지막 ▶|', action: () => goToPage(pages.length - 1) },
          ].map(b => (
            <button key={b.label} onClick={b.action}
              style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.toolbar, color: colors.muted }}>
              {b.label}
            </button>
          ))}
        </div>
      </div>

      {/* 본문 */}
      <div style={{ display: 'flex', height: 620 }}>
        {/* 페이지 뷰어 (줌 시 스크롤 가능) */}
        <div ref={containerRef} style={{ flex: 1.3, display: 'flex', alignItems: zoom > 1 ? 'flex-start' : 'center', justifyContent: 'center', padding: '20px 12px', background: isDark ? '#080A12' : '#ECEEF2', overflow: 'auto' }}
          onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexShrink: 0 }}>
            <button onClick={() => goToPage(currentPage - 1)} disabled={currentPage === 0}
              style={{ width: 38, height: 38, borderRadius: '50%', border: `1px solid ${colors.border}`, background: colors.sidebar, color: colors.muted, cursor: currentPage === 0 ? 'not-allowed' : 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: currentPage === 0 ? 0.4 : 1 }}>
              ◀
            </button>
            <div>
              {/* 페이지 이미지 + bbox 오버레이 */}
              <div style={{ position: 'relative', display: 'inline-block', cursor: tool === 'add' ? 'crosshair' : 'default' }}
                onMouseDown={(e) => onMouseDown(e)}>
                <img ref={imgRef}
                  src={`data:${page.media_type};base64,${page.image_base64}`}
                  alt={`페이지 ${currentPage + 1}`}
                  style={{ display: 'block', width: `${420 * zoom}px`, maxWidth: 'none', height: 'auto', borderRadius: 6, border: `1px solid ${colors.border}`, userSelect: 'none', pointerEvents: 'none' }}
                  draggable={false}
                />
                {/* bbox 오버레이 */}
                {pageItems.map(bb => {
                  const isSel = bb.id === selectedId
                  return (
                    <div key={bb.id}
                      onMouseDown={(e) => onMouseDown(e, bb.id)}
                      style={{ position: 'absolute', left: `${bb.x * 100}%`, top: `${bb.y * 100}%`, width: `${bb.w * 100}%`, height: `${bb.h * 100}%`, border: `2px solid ${isSel ? '#f59e0b' : colors.accent}`, borderRadius: 3, background: isSel ? 'rgba(245,158,11,0.08)' : `${colors.accent}14`, cursor: tool === 'select' ? 'move' : 'default', boxSizing: 'border-box' }}>
                      {/* 라벨 */}
                      <div style={{ position: 'absolute', top: -20, left: 0, background: isSel ? '#f59e0b' : colors.accent, color: isSel ? '#0D0F1A' : 'white', fontSize: 10, padding: '1px 7px', borderRadius: 4, whiteSpace: 'nowrap' }}>
                        {bb.label}
                      </div>
                      {/* 리사이즈 핸들 (선택됐을 때만) */}
                      {isSel && [
                        { dir: 'nw', style: { top: -5, left: -5, cursor: 'nw-resize' } },
                        { dir: 'ne', style: { top: -5, right: -5, cursor: 'ne-resize' } },
                        { dir: 'sw', style: { bottom: -5, left: -5, cursor: 'sw-resize' } },
                        { dir: 'se', style: { bottom: -5, right: -5, cursor: 'se-resize' } },
                        { dir: 'n', style: { top: -5, left: 'calc(50% - 4px)', cursor: 'n-resize' } },
                        { dir: 's', style: { bottom: -5, left: 'calc(50% - 4px)', cursor: 's-resize' } },
                        { dir: 'w', style: { left: -5, top: 'calc(50% - 4px)', cursor: 'w-resize' } },
                        { dir: 'e', style: { right: -5, top: 'calc(50% - 4px)', cursor: 'e-resize' } },
                      ].map(h => (
                        <div key={h.dir} onMouseDown={(e) => { e.stopPropagation(); onMouseDown(e, bb.id, h.dir) }}
                          style={{ position: 'absolute', width: HANDLE_SIZE, height: HANDLE_SIZE, background: 'white', border: `2px solid #f59e0b`, borderRadius: 2, ...h.style }} />
                      ))}
                    </div>
                  )
                })}
              </div>
              <div style={{ textAlign: 'center', fontSize: 12, color: colors.muted, marginTop: 10 }}>
                {currentPage + 1} / {pages.length} 페이지
              </div>
            </div>
            <button onClick={() => goToPage(currentPage + 1)} disabled={currentPage === pages.length - 1}
              style={{ width: 38, height: 38, borderRadius: '50%', border: `1px solid ${colors.border}`, background: colors.sidebar, color: colors.muted, cursor: currentPage === pages.length - 1 ? 'not-allowed' : 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: currentPage === pages.length - 1 ? 0.4 : 1 }}>
              ▶
            </button>
          </div>
        </div>

        {/* 사이드바 */}
        <div style={{ flex: 1, borderLeft: `1px solid ${colors.border}`, display: 'flex', flexDirection: 'column', background: colors.bg }}>
          <div style={{ padding: '12px 16px', background: colors.sidebar, borderBottom: `1px solid ${colors.border}`, fontSize: 12, fontWeight: 700, color: colors.muted, textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center' }}>
            감지 문제 목록
            <span style={{ marginLeft: 'auto', background: `${colors.accent}22`, color: colors.accent, padding: '2px 9px', borderRadius: 20, fontSize: 11, fontWeight: 700 }}>
              {allItems.length}개
            </span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
            {/* 현재 페이지 문제 */}
            {pageItems.length > 0 && (
              <>
                <div style={{ fontSize: 10, fontWeight: 700, color: colors.accent, marginBottom: 4, paddingLeft: 4 }}>● 현재 페이지</div>
                {pageItems.map(bb => (
                  <div key={bb.id} onClick={() => setSelectedId(bb.id)}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 7, marginBottom: 4, cursor: 'pointer', border: `1px solid ${bb.id === selectedId ? '#f59e0b44' : 'transparent'}`, background: bb.id === selectedId ? '#f59e0b11' : 'transparent', fontSize: 12, color: colors.text }}>
                    <input type="checkbox" checked={bb.selected} onChange={() => toggleSelection(bb.id)} onClick={e => e.stopPropagation()} />
                    <div style={{ width: 10, height: 10, borderRadius: 3, background: colors.accent, flexShrink: 0 }} />
                    <span>{bb.label}</span>
                    <span style={{ marginLeft: 'auto', fontSize: 10, color: colors.muted, background: colors.sidebar, padding: '1px 6px', borderRadius: 10 }}>{currentPage + 1}p</span>
                  </div>
                ))}
              </>
            )}
            {/* 다른 페이지 문제 */}
            {allItems.filter(b => b.page_index !== currentPage).length > 0 && (
              <>
                <div style={{ fontSize: 10, fontWeight: 700, color: colors.muted, margin: '12px 0 4px', paddingLeft: 4 }}>다른 페이지</div>
                {allItems.filter(b => b.page_index !== currentPage).map(bb => (
                  <div key={bb.id} onClick={() => { goToPage(bb.page_index); setSelectedId(bb.id) }}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 7, marginBottom: 4, cursor: 'pointer', border: `1px solid ${colors.border}`, fontSize: 12, color: colors.muted }}>
                    <input type="checkbox" checked={bb.selected} onChange={() => toggleSelection(bb.id)} onClick={e => e.stopPropagation()} />
                    <div style={{ width: 10, height: 10, borderRadius: 3, background: colors.muted, flexShrink: 0 }} />
                    <span>{bb.label}</span>
                    <span style={{ marginLeft: 'auto', fontSize: 10, color: colors.muted, background: colors.sidebar, padding: '1px 6px', borderRadius: 10 }}>{bb.page_index + 1}p</span>
                  </div>
                ))}
              </>
            )}
            {allItems.length === 0 && (
              <div style={{ textAlign: 'center', color: colors.muted, fontSize: 12, paddingTop: 20 }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>🔍</div>
                <p>문제를 감지하지 못했습니다.</p>
                <p style={{ marginTop: 4 }}>"박스 추가" 도구로 직접 그려주세요.</p>
              </div>
            )}
            {/* 전체 선택/해제 */}
            <div style={{ display: 'flex', gap: 6, marginTop: 12, paddingTop: 12, borderTop: `1px solid ${colors.border}` }}>
              <button onClick={() => selectAll(true)} style={{ flex: 1, padding: '4px 0', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.sidebar, color: colors.muted }}>전체 선택</button>
              <button onClick={() => selectAll(false)} style={{ flex: 1, padding: '4px 0', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${colors.border}`, background: colors.sidebar, color: colors.muted }}>전체 해제</button>
            </div>
          </div>
          <div style={{ padding: 12, borderTop: `1px solid ${colors.border}` }}>
            <div style={{ fontSize: 11, color: colors.muted, marginBottom: 8 }}>
              {allItems.filter(b => b.selected).length}개 선택됨
            </div>
            <button onClick={handleConfirm} disabled={allItems.filter(b => b.selected).length === 0}
              style={{ width: '100%', padding: '10px 0', borderRadius: 8, fontWeight: 600, fontSize: 13, color: 'white', background: `linear-gradient(to right, ${colors.accent}, ${isDark ? '#6D28D9' : '#0284C7'})`, border: 'none', cursor: allItems.filter(b => b.selected).length === 0 ? 'not-allowed' : 'pointer', opacity: allItems.filter(b => b.selected).length === 0 ? 0.4 : 1 }}>
              크롭 확정 → 처리 방식 선택
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
