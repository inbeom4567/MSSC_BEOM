import { useMemo } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'

function renderLatexText(text) {
  // $$...$$ 블록 수식과 $...$ 인라인 수식을 HTML로 변환
  const parts = []
  let remaining = text

  while (remaining.length > 0) {
    // 블록 수식 $$...$$ 찾기
    const blockMatch = remaining.match(/\$\$([\s\S]*?)\$\$/)
    // 인라인 수식 $...$ 찾기 ($$가 아닌 것)
    const inlineMatch = remaining.match(/(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/)

    if (!blockMatch && !inlineMatch) {
      parts.push({ type: 'text', content: remaining })
      break
    }

    const blockIdx = blockMatch ? remaining.indexOf(blockMatch[0]) : Infinity
    const inlineIdx = inlineMatch ? remaining.indexOf(inlineMatch[0]) : Infinity

    if (blockIdx <= inlineIdx) {
      if (blockIdx > 0) parts.push({ type: 'text', content: remaining.slice(0, blockIdx) })
      try {
        const html = katex.renderToString(blockMatch[1].trim(), { displayMode: true, throwOnError: false })
        parts.push({ type: 'latex-block', html })
      } catch { parts.push({ type: 'text', content: blockMatch[0] }) }
      remaining = remaining.slice(blockIdx + blockMatch[0].length)
    } else {
      if (inlineIdx > 0) parts.push({ type: 'text', content: remaining.slice(0, inlineIdx) })
      try {
        const html = katex.renderToString(inlineMatch[1].trim(), { displayMode: false, throwOnError: false })
        parts.push({ type: 'latex-inline', html })
      } catch { parts.push({ type: 'text', content: inlineMatch[0] }) }
      remaining = remaining.slice(inlineIdx + inlineMatch[0].length)
    }
  }

  return parts
}

export default function LatexRenderer({ text }) {
  const parts = useMemo(() => renderLatexText(text), [text])

  return (
    <div className="text-gray-700 leading-relaxed whitespace-pre-wrap">
      {parts.map((part, i) => {
        if (part.type === 'latex-block') {
          return <div key={i} className="my-2" dangerouslySetInnerHTML={{ __html: part.html }} />
        }
        if (part.type === 'latex-inline') {
          return <span key={i} dangerouslySetInnerHTML={{ __html: part.html }} />
        }
        return <span key={i}>{part.content}</span>
      })}
    </div>
  )
}
