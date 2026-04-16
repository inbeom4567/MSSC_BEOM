import { useState } from 'react'
import DOMPurify from 'dompurify'

export default function GraphImage({ base64Data, index, onRetry }) {
  const [copied, setCopied] = useState(false)

  const isSvg = typeof base64Data === 'string' && base64Data.trimStart().startsWith('<svg')
  const hasData = typeof base64Data === 'string' && base64Data.trim().length > 0

  const handleDownload = () => {
    if (isSvg) {
      const blob = new Blob([base64Data], { type: 'image/svg+xml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `graph_${index + 1}.svg`
      link.click()
      URL.revokeObjectURL(url)
    } else {
      const src = `data:image/png;base64,${base64Data}`
      const link = document.createElement('a')
      link.href = src
      link.download = `graph_${index + 1}.png`
      link.click()
    }
  }

  const handleCopy = async () => {
    if (isSvg) {
      await navigator.clipboard.writeText(base64Data)
    } else {
      const src = `data:image/png;base64,${base64Data}`
      const res = await fetch(src)
      const blob = await res.blob()
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (!hasData) {
    return (
      <div className="my-4 flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/10 p-6 text-center">
        <p className="text-sm text-red-600 dark:text-red-400">그래프 {index + 1} 생성 실패</p>
        {onRetry && (
          <button
            onClick={() => onRetry(index)}
            className="px-3 py-1 text-xs rounded-md bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors"
          >
            다시 시도
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="my-4 relative group">
      {isSvg ? (
        <div
          className="mx-auto max-w-full flex justify-center"
          dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(base64Data) }}
        />
      ) : (
        <img
          src={`data:image/png;base64,${base64Data}`}
          alt={`그래프 ${index + 1}`}
          className="mx-auto rounded-lg border border-gray-200 dark:border-[#2E3356] shadow-sm max-w-full"
        />
      )}
      <div className="absolute top-2 right-2 flex gap-1">
        <button onClick={handleCopy}
          className="px-2 py-1 bg-gray-700 text-gray-200 rounded text-xs hover:bg-gray-600">
          {copied ? '✓' : '복사'}
        </button>
        <button onClick={handleDownload}
          className="px-2 py-1 bg-gray-700 text-gray-200 rounded text-xs hover:bg-gray-600">
          저장
        </button>
      </div>
    </div>
  )
}
