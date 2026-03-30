import { useState, useEffect } from 'react'
import SolutionDisplay from './SolutionDisplay'
import UsageInfo from './UsageInfo'

const API = 'http://localhost:8001'

const TYPE_LABELS = { generate: '유사문항 생성', solve: '변형문항 풀이' }
const DIFF_LABELS = { easier: '더 쉽게', similar: '비슷하게', harder: '더 어렵게' }
const VTYPE_LABELS = { number: '숫자 변형', idea: '아이디어 변형' }

export default function TabHistory() {
  const [items, setItems] = useState([])
  const [selected, setSelected] = useState(null)
  const [compareId, setCompareId] = useState(null)
  const [compareData, setCompareData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  const fetchList = async () => {
    const res = await fetch(`${API}/api/history`)
    const data = await res.json()
    setItems(data.items)
  }

  useEffect(() => { fetchList() }, [])

  const handleSelect = async (id) => {
    if (selected?.id === id) { setSelected(null); return }
    const res = await fetch(`${API}/api/history/${id}`)
    const data = await res.json()
    setSelected(data)
    setCompareId(null)
    setCompareData(null)
  }

  const handleCompare = async (id) => {
    if (compareId === id) { setCompareId(null); setCompareData(null); return }
    const res = await fetch(`${API}/api/history/${id}`)
    const data = await res.json()
    setCompareId(id)
    setCompareData(data)
  }

  const handleDelete = async (id, e) => {
    e.stopPropagation()
    if (selected?.id === id) setSelected(null)
    if (compareId === id) { setCompareId(null); setCompareData(null) }
    await fetch(`${API}/api/history/${id}`, { method: 'DELETE' })
    fetchList()
  }

  const isCompareMode = selected !== null

  return (
    <div className="space-y-4">
      {items.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          아직 히스토리가 없습니다. 유사문항을 생성하면 자동으로 저장됩니다.
        </div>
      ) : (
        <>
          <div className="space-y-2">
            {items.map((item) => (
              <div
                key={item.id}
                onClick={() => isCompareMode && selected?.id !== item.id ? handleCompare(item.id) : handleSelect(item.id)}
                className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                  selected?.id === item.id
                    ? 'border-blue-500 bg-blue-50'
                    : compareId === item.id
                    ? 'border-green-500 bg-green-50'
                    : 'border-gray-200 bg-white hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      item.model?.includes('opus') ? 'bg-purple-100 text-purple-700' : 'bg-sky-100 text-sky-700'
                    }`}>
                      {item.model?.includes('opus') ? 'Opus' : 'Sonnet'}
                    </span>
                    <span className="text-xs text-gray-500">{TYPE_LABELS[item.type] || item.type}</span>
                    {item.variant_type && (
                      <span className="text-xs text-gray-400">{VTYPE_LABELS[item.variant_type]}</span>
                    )}
                    {item.difficulty && (
                      <span className="text-xs text-gray-400">{DIFF_LABELS[item.difficulty]}</span>
                    )}
                    {item.cost_krw > 0 && (
                      <span className="text-xs text-gray-400">약 {item.cost_krw.toLocaleString()}원</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">
                      {new Date(item.created_at).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <button
                      onClick={(e) => handleDelete(item.id, e)}
                      className="text-gray-300 hover:text-red-500 text-xs transition-colors"
                    >
                      삭제
                    </button>
                  </div>
                </div>
                <p className="text-sm text-gray-600 mt-1 truncate">{item.preview}</p>
                {isCompareMode && selected?.id !== item.id && compareId !== item.id && (
                  <p className="text-xs text-blue-500 mt-1">클릭하여 비교</p>
                )}
              </div>
            ))}
          </div>

          {isCompareMode && !compareData && (
            <p className="text-center text-sm text-blue-500">다른 항목을 클릭하면 비교할 수 있습니다</p>
          )}
        </>
      )}

      {/* 단일 보기 또는 비교 보기 */}
      {selected && !compareData && (
        <div>
          <SolutionDisplay solution={selected.result} title={TYPE_LABELS[selected.type] || '결과'} />
          <UsageInfo usage={selected.usage} />
        </div>
      )}

      {selected && compareData && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                selected.model?.includes('opus') ? 'bg-purple-100 text-purple-700' : 'bg-sky-100 text-sky-700'
              }`}>
                {selected.model?.includes('opus') ? 'Opus' : 'Sonnet'}
              </span>
              <span className="text-xs text-gray-500">{new Date(selected.created_at).toLocaleString('ko-KR')}</span>
            </div>
            <SolutionDisplay solution={selected.result} title="A" />
            <UsageInfo usage={selected.usage} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                compareData.model?.includes('opus') ? 'bg-purple-100 text-purple-700' : 'bg-sky-100 text-sky-700'
              }`}>
                {compareData.model?.includes('opus') ? 'Opus' : 'Sonnet'}
              </span>
              <span className="text-xs text-gray-500">{new Date(compareData.created_at).toLocaleString('ko-KR')}</span>
            </div>
            <SolutionDisplay solution={compareData.result} title="B" />
            <UsageInfo usage={compareData.usage} />
          </div>
        </div>
      )}
    </div>
  )
}
