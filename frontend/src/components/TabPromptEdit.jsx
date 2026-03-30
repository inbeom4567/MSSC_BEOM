import { useState } from 'react'

const API = 'http://localhost:8001'

export default function TabPromptEdit() {
  const [feedback, setFeedback] = useState('')
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])

  const handleSubmit = async () => {
    if (!feedback.trim()) return
    setIsLoading(true); setError(null); setResult(null)
    try {
      const res = await fetch(`${API}/api/prompt-feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback: feedback.trim() }),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '실패')
      const data = await res.json()
      setResult(data.result)
      setHistory(prev => [...prev, { feedback: feedback.trim(), rule: data.result }])
      setFeedback('')
    } catch (err) { setError(err.message) }
    finally { setIsLoading(false) }
  }

  return (
    <div className="space-y-4">
      <div className="p-4 bg-yellow-50 rounded-xl border border-yellow-200">
        <h3 className="font-bold text-yellow-800 mb-2">프롬프트 수정</h3>
        <p className="text-yellow-700 text-sm mb-3">
          출력에서 잘못된 부분을 알려주면 프롬프트에 자동으로 규칙이 추가됩니다.
        </p>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="예: 플러스마이너스는 pm이 아니라 +- 로 써야 합니다"
          className="w-full p-3 border border-yellow-300 rounded-lg text-sm resize-none h-24 focus:outline-none focus:ring-2 focus:ring-yellow-400"
        />
        <button onClick={handleSubmit} disabled={isLoading || !feedback.trim()}
          className="mt-2 px-5 py-2 bg-yellow-500 text-white rounded-lg font-medium hover:bg-yellow-600 disabled:opacity-50 transition-colors">
          {isLoading ? '반영 중...' : '프롬프트에 반영'}
        </button>
      </div>

      {error && <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm">{error}</div>}

      {result && (
        <div className="p-4 bg-green-50 rounded-xl border border-green-200">
          <h3 className="font-bold text-green-800 mb-2">추가된 규칙</h3>
          <p className="text-green-700 text-sm whitespace-pre-wrap">{result}</p>
        </div>
      )}

      {history.length > 0 && (
        <div className="p-4 bg-white rounded-xl border border-gray-200">
          <h3 className="font-bold text-gray-800 mb-2">수정 이력</h3>
          <div className="space-y-2">
            {history.map((h, i) => (
              <div key={i} className="text-sm border-b border-gray-100 pb-2">
                <p className="text-gray-500">피드백: {h.feedback}</p>
                <p className="text-gray-700">→ {h.rule}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
