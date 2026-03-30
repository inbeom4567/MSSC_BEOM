import { useState } from 'react'

export default function HwpCodeBlock({ code, inline = false }) {
  const [copied, setCopied] = useState(false)
  const [showCode, setShowCode] = useState(false)

  const handleCopy = async (e) => {
    e.stopPropagation()
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (inline) {
    return (
      <span
        onClick={handleCopy}
        onMouseEnter={() => setShowCode(true)}
        onMouseLeave={() => setShowCode(false)}
        className="relative inline-block"
      >
        <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-sm cursor-pointer hover:bg-blue-200 border border-blue-300 transition-colors font-medium">
          {copied ? '✓복사됨' : '[수식]'}
        </span>
        {showCode && !copied && (
          <span className="absolute bottom-full left-0 mb-1 px-2 py-1 bg-gray-900 text-green-300 text-xs rounded whitespace-nowrap font-mono z-10">
            {code}
          </span>
        )}
      </span>
    )
  }

  return (
    <div className="relative my-3 group">
      <pre className="bg-gray-900 text-green-300 p-4 rounded-lg text-sm overflow-x-auto font-mono">
        {code}
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 px-2.5 py-1 bg-gray-700 text-gray-200 rounded text-xs hover:bg-gray-600 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {copied ? '✓ 복사됨' : '복사'}
      </button>
    </div>
  )
}
