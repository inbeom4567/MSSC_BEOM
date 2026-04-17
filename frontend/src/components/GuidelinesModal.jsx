import { useState } from 'react'

export default function GuidelinesModal({ currentGuidelines, currentName, savedGuidelines, onApply, onSave, onDelete, onClose }) {
  const [name, setName] = useState(currentName || '')
  const [content, setContent] = useState(currentGuidelines || '')
  const [selectedId, setSelectedId] = useState(null)

  const handleSelectSaved = (g) => {
    setSelectedId(g.id)
    setName(g.name)
    setContent(g.content)
  }

  const handleApply = () => {
    if (!content.trim()) return
    onApply(name.trim(), content.trim())
  }

  const handleSaveToList = () => {
    if (!name.trim() || !content.trim()) return
    onSave(name.trim(), content.trim())
    setName('')
    setContent('')
    setSelectedId(null)
  }

  const handleClearAll = () => {
    setName('')
    setContent('')
    setSelectedId(null)
    onApply('', '')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white dark:bg-[#0f1011] rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex overflow-hidden border border-gray-200 dark:border-[rgba(255,255,255,0.06)]" onClick={e => e.stopPropagation()}>
        {/* 왼쪽: 저장된 지침 목록 */}
        <div className="w-48 bg-gray-50 dark:bg-[#0c0c0e] border-r border-gray-200 dark:border-[rgba(255,255,255,0.06)] flex flex-col shrink-0">
          <div className="p-4 border-b border-gray-200 dark:border-[rgba(255,255,255,0.06)]">
            <h3 className="font-bold text-gray-800 dark:text-[#f7f8f8] text-sm">내 지침</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {savedGuidelines.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-[#4a4a52] text-center mt-8 px-2">내 지침을 추가하세요.</p>
            ) : (
              savedGuidelines.map((g) => (
                <div key={g.id}
                  className={`group flex items-center justify-between p-2 rounded-lg cursor-pointer text-sm mb-1 transition-colors ${
                    selectedId === g.id
                      ? 'bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300'
                      : 'hover:bg-gray-100 dark:hover:bg-[#141516] text-gray-700 dark:text-[#d0d0d5]'
                  }`}
                  onClick={() => handleSelectSaved(g)}
                >
                  <span className="truncate flex-1">{g.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(g.id) }}
                    className="text-gray-300 dark:text-[#4a4a52] hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity ml-1"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 오른쪽: 지침 편집 */}
        <div className="flex-1 flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-[rgba(255,255,255,0.06)]">
            <h2 className="font-bold text-gray-800 dark:text-[#f7f8f8]">지침 설정</h2>
            <button onClick={onClose} className="text-gray-400 dark:text-[#8a8f98] hover:text-gray-600 dark:hover:text-[#f7f8f8]">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="flex-1 p-4 space-y-4 overflow-y-auto">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-[#d0d0d5] block mb-1">이름</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="지침의 이름을 입력하세요."
                className="w-full p-3 border border-gray-200 dark:border-[rgba(255,255,255,0.08)] rounded-xl text-sm bg-gray-50 dark:bg-[#141516] text-gray-800 dark:text-[#f7f8f8] placeholder:text-gray-400 dark:placeholder:text-[#4a4a52] focus:outline-none focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500 focus:bg-white dark:focus:bg-[#1a1a1c]"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-[#d0d0d5] block mb-1">지침</label>
              <p className="text-xs text-gray-400 dark:text-[#4a4a52] mb-2">지침의 내용에 따라 문제풀이 성능이 달라질 수 있습니다.</p>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="예: 언제나 친절하고 신뢰할 수 있는 태도로 응답하며, 설명은 먼저 핵심을 간단히 제시한 뒤, 필요한 경우 추가 설명이나 예시, 표 등을 제공합니다."
                rows={8}
                className="w-full p-3 border border-gray-200 dark:border-[rgba(255,255,255,0.08)] rounded-xl text-sm bg-gray-50 dark:bg-[#141516] text-gray-800 dark:text-[#f7f8f8] placeholder:text-gray-400 dark:placeholder:text-[#4a4a52] focus:outline-none focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500 focus:bg-white dark:focus:bg-[#1a1a1c] resize-none"
              />
            </div>
          </div>

          <div className="p-4 border-t border-gray-200 dark:border-[rgba(255,255,255,0.06)] flex items-center justify-between">
            <button onClick={handleClearAll} className="text-sm text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300">
              모두지우기
            </button>
            <div className="flex items-center gap-2">
              <button onClick={handleSaveToList} disabled={!name.trim() || !content.trim()}
                className="text-sm text-gray-600 dark:text-[#8a8f98] hover:text-gray-800 dark:hover:text-[#f7f8f8] disabled:text-gray-300 dark:disabled:text-[rgba(255,255,255,0.08)] px-3 py-2">
                내 지침에 추가하기
              </button>
              <button onClick={handleApply} disabled={!content.trim()}
                className="text-sm bg-gradient-to-r from-indigo-600 to-violet-600 text-white px-5 py-2 rounded-lg font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all shadow-[0_2px_8px_rgba(108,127,255,0.2)]">
                적용하기
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
