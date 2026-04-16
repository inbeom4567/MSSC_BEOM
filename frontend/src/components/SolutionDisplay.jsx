import { useState } from 'react'
import HwpCodeBlock from './HwpCodeBlock'
import GraphImage from './GraphImage'

function parseSolution(text) {
  const parts = []
  const regex = /\[([^\]]+)\]/g
  let lastIndex = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.slice(lastIndex, match.index) })
    }
    const inner = match[1]
    if (inner.startsWith('GRAPH:')) {
      parts.push({ type: 'graph', index: parseInt(inner.split(':')[1], 10) })
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
    let text = solution
    text = text.replace(/([가-힣a-zA-Z0-9])\[/g, '$1 [')
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
    <div className="bg-white dark:bg-[#11131F] rounded-xl border border-gray-200 dark:border-[#222644] shadow-sm overflow-hidden">
      {/* 툴바 */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 dark:border-[#222644] bg-gray-50/50 dark:bg-[#191C2E]/50">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-[#E8EAFF]">{title}</h2>
        <div className="flex gap-2">
          <button
            onClick={handleListCopy}
            className="px-3 py-1.5 text-xs font-medium bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-500/20 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-colors"
          >
            {listCopied ? '✓ 복사됨' : '수식 목록 복사'}
          </button>
          <button
            onClick={handleFullCopy}
            className="px-3 py-1.5 text-xs font-medium bg-gray-100 dark:bg-[#212540] text-gray-600 dark:text-[#7880AA] border border-gray-200 dark:border-[#2E3356] rounded-lg hover:bg-gray-200 dark:hover:bg-[#2A2E52] transition-colors"
          >
            {fullCopied ? '✓ 복사됨' : '전체 복사'}
          </button>
        </div>
      </div>

      {/* 본문 */}
      <div className="p-5 text-gray-700 dark:text-[#C8CADF] leading-loose text-[14px] whitespace-pre-wrap">
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
