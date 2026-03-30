import { useState } from 'react'
import SolutionDisplay from './SolutionDisplay'

const API = 'http://localhost:8001'

const DIFFICULTIES = [
  { value: 'similar', label: '비슷하게' },
  { value: 'harder', label: '조금 어렵게' },
  { value: 'much_harder', label: '많이 어렵게' },
]

export default function VariantSection({ problemText }) {
  const [difficulty, setDifficulty] = useState('similar')
  const [variant, setVariant] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleGenerate = async () => {
    if (!problemText) return
    setIsLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API}/api/variant`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem_text: problemText, difficulty }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || '변형문제 생성에 실패했습니다.')
      }

      const data = await res.json()
      setVariant(data.variant)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  if (!problemText) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-medium text-gray-600">난이도:</span>
        {DIFFICULTIES.map((d) => (
          <button
            key={d.value}
            onClick={() => setDifficulty(d.value)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              difficulty === d.value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {d.label}
          </button>
        ))}
        <button
          onClick={handleGenerate}
          disabled={isLoading}
          className="px-5 py-1.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ml-auto"
        >
          {isLoading ? '생성 중...' : '변형문제 생성'}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm">
          {error}
        </div>
      )}

      {variant && <SolutionDisplay solution={variant} title="변형문제 + 풀이" />}
    </div>
  )
}
