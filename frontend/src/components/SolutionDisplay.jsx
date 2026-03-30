import { useState } from 'react'
import HwpCodeBlock from './HwpCodeBlock'

function parseSolution(text) {
  const parts = []
  const regex = /\[([^\]]+)\]/g
  let lastIndex = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    // 대괄호 앞의 일반 텍스트
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.slice(lastIndex, match.index) })
    }

    parts.push({ type: 'formula', content: match[1] })

    lastIndex = regex.lastIndex
  }

  // 남은 텍스트
  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIndex) })
  }

  return parts
}

export default function SolutionDisplay({ solution, title = '풀이' }) {
  const [fullCopied, setFullCopied] = useState(false)
  const [listCopied, setListCopied] = useState(false)

  if (!solution) return null

  const parts = parseSolution(solution)
  const formulas = parts.filter(p => p.type === 'formula')

  const handleFullCopy = () => {
    // 원본 텍스트 그대로 복사 (수식은 [코드] 형태 유지)
    navigator.clipboard.writeText(solution)
    setFullCopied(true)
    setTimeout(() => setFullCopied(false), 1500)
  }

  const handleListCopy = () => {
    const text = formulas.map((f, i) => `[수식${i + 1}] ${f.content}`).join('\n')
    navigator.clipboard.writeText(text)
    setListCopied(true)
    setTimeout(() => setListCopied(false), 1500)
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-800">{title}</h2>
        <div className="flex gap-2">
          <button
            onClick={handleListCopy}
            className="px-3 py-1.5 text-sm bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors"
          >
            {listCopied ? '✓ 복사됨' : '수식 목록 복사'}
          </button>
          <button
            onClick={handleFullCopy}
            className="px-3 py-1.5 text-sm bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition-colors"
          >
            {fullCopied ? '✓ 복사됨' : '전체 복사'}
          </button>
        </div>
      </div>

      <div className="text-gray-700 leading-relaxed whitespace-pre-wrap">
        {parts.map((part, i) => {
          if (part.type === 'formula') {
            return <HwpCodeBlock key={i} code={part.content} inline />
          }
          return <span key={i}>{part.content}</span>
        })}
      </div>
    </div>
  )
}
