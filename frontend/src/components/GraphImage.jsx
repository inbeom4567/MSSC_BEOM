import { useState } from 'react'
import DOMPurify from 'dompurify'

export default function GraphImage({ base64Data, index }) {
  const [copied, setCopied] = useState(false)

  const isSvg = typeof base64Data === 'string' && base64Data.trimStart().startsWith('<svg')

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
          className="mx-auto rounded-lg border border-gray-200 shadow-sm max-w-full"
        />
      )}
      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
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
