import { useState } from 'react'

export default function GraphImage({ base64Data, index }) {
  const [copied, setCopied] = useState(false)
  const src = `data:image/png;base64,${base64Data}`

  const handleDownload = () => {
    const link = document.createElement('a')
    link.href = src
    link.download = `graph_${index + 1}.png`
    link.click()
  }

  const handleCopy = async () => {
    const res = await fetch(src)
    const blob = await res.blob()
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="my-4 relative group">
      <img src={src} alt={`그래프 ${index + 1}`} className="mx-auto rounded-lg border border-gray-200 shadow-sm max-w-full" />
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
