import { useState } from 'react'
import HwpCodeBlock from './HwpCodeBlock'
import GraphImage from './GraphImage'

function parseSolution(text) {
  const parts = []
  // [수식] 또는 [GRAPH:N] 패턴 매칭
  const regex = /\[([^\]]+)\]/g
  let lastIndex = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.slice(lastIndex, match.index) })
    }

    const inner = match[1]
    if (inner.startsWith('GRAPH:')) {
      const graphIdx = parseInt(inner.split(':')[1], 10)
      parts.push({ type: 'graph', index: graphIdx })
    } else {
      parts.push({ type: 'formula', content: inner })
    }

    lastIndex = regex.lastIndex
  }

  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIndex) })
  }

  return parts
}

export default function SolutionDisplay({ solution, graphs = [], title = '해설' }) {
  const [fullCopied, setFullCopied] = useState(false)
  const [listCopied, setListCopied] = useState(false)

  if (!solution) return null

  const parts = parseSolution(solution)
  const formulas = parts.filter(p => p.type === 'formula')

  const handleFullCopy = () => {
    // 수식과 한글 텍스트 사이에 띄어쓰기 보정
    let text = solution
    // [수식] 앞: 한글/숫자 바로 뒤에 [ 가 오면 공백 추가
    text = text.replace(/([가-힣a-zA-Z0-9])\[/g, '$1 [')
    // [수식] 뒤: ] 바로 뒤에 한글이 오면 공백 추가 (조사 제외: 은는이가를의와로에서도)
    text = text.replace(/\]([가-힣])/g, (match, char) => {
      const josa = '은는이가를의와로에서도만으며고'
      return josa.includes(char) ? match : `] ${char}`
    })
    navigator.clipboard.writeText(text)
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
          <button onClick={handleListCopy}
            className="px-3 py-1.5 text-sm bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors">
            {listCopied ? '✓ 복사됨' : '수식 목록 복사'}
          </button>
          <button onClick={handleFullCopy}
            className="px-3 py-1.5 text-sm bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition-colors">
            {fullCopied ? '✓ 복사됨' : '전체 복사'}
          </button>
        </div>
      </div>

      <div className="text-gray-700 leading-relaxed whitespace-pre-wrap">
        {parts.map((part, i) => {
          if (part.type === 'graph' && graphs[part.index]) {
            return <GraphImage key={i} base64Data={graphs[part.index]} index={part.index} />
          }
          if (part.type === 'formula') {
            return <HwpCodeBlock key={i} code={part.content} inline />
          }
          return <span key={i}>{part.content}</span>
        })}
      </div>
    </div>
  )
}
