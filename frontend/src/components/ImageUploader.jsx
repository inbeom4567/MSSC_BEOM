import { useState, useRef, useCallback } from 'react'

export default function ImageUploader({ onSolve, isLoading }) {
  const [problemPreview, setProblemPreview] = useState(null)
  const [problemFile, setProblemFile] = useState(null)
  const [solutionPreview, setSolutionPreview] = useState(null)
  const [solutionFile, setSolutionFile] = useState(null)
  const [variantPreview, setVariantPreview] = useState(null)
  const [variantFile, setVariantFile] = useState(null)
  const [isDragging, setIsDragging] = useState(null)
  const problemInputRef = useRef(null)
  const solutionInputRef = useRef(null)
  const variantInputRef = useRef(null)

  const handleFile = useCallback((f, type) => {
    if (!f || !f.type.startsWith('image/')) return
    const reader = new FileReader()
    if (type === 'problem') {
      setProblemFile(f)
      reader.onload = (e) => setProblemPreview(e.target.result)
    } else if (type === 'solution') {
      setSolutionFile(f)
      reader.onload = (e) => setSolutionPreview(e.target.result)
    } else {
      setVariantFile(f)
      reader.onload = (e) => setVariantPreview(e.target.result)
    }
    reader.readAsDataURL(f)
  }, [])

  const handleDrop = useCallback((e, type) => {
    e.preventDefault()
    setIsDragging(null)
    handleFile(e.dataTransfer.files[0], type)
  }, [handleFile])

  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const type = !problemFile ? 'problem' : !solutionFile ? 'solution' : 'variant'
        handleFile(item.getAsFile(), type)
        break
      }
    }
  }, [handleFile, problemFile, solutionFile])

  const handleSubmit = () => {
    if (!problemFile || !solutionFile) return
    const files = [problemFile, solutionFile]
    if (variantFile) files.push(variantFile)
    onSolve(files)
  }

  const handleReset = () => {
    setProblemPreview(null)
    setProblemFile(null)
    setSolutionPreview(null)
    setSolutionFile(null)
    setVariantPreview(null)
    setVariantFile(null)
  }

  const hasVariant = !!variantFile
  const mode = hasVariant ? '변형문항 풀이 생성' : '유사문항 생성'

  const UploadBox = ({ type, preview, label, inputRef, icon }) => (
    <div
      className={`flex-1 border-2 border-dashed rounded-xl p-3 text-center cursor-pointer transition-colors min-w-0 ${
        isDragging === type
          ? 'border-blue-500 bg-blue-50'
          : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
      }`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(type) }}
      onDragLeave={() => setIsDragging(null)}
      onDrop={(e) => handleDrop(e, type)}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => { handleFile(e.target.files[0], type); e.target.value = '' }}
      />
      {preview ? (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">{label}</p>
          <img src={preview} alt={label} className="max-h-48 mx-auto rounded-lg" />
        </div>
      ) : (
        <div className="py-4">
          <div className="text-2xl mb-1">{icon}</div>
          <p className="text-gray-600 font-medium text-xs">{label}</p>
          <p className="text-gray-400 text-xs mt-1">Ctrl+V</p>
        </div>
      )}
    </div>
  )

  return (
    <div className="w-full" onPaste={handlePaste} tabIndex={0}>
      <div className="flex gap-3">
        <UploadBox
          type="problem"
          preview={problemPreview}
          label="원본 문제 (필수)"
          inputRef={problemInputRef}
          icon="📝"
        />
        <UploadBox
          type="solution"
          preview={solutionPreview}
          label="원본 해설 (필수)"
          inputRef={solutionInputRef}
          icon="📖"
        />
        <UploadBox
          type="variant"
          preview={variantPreview}
          label="변형문항 (선택)"
          inputRef={variantInputRef}
          icon="✏️"
        />
      </div>

      {hasVariant && (
        <p className="text-center text-sm text-green-600 mt-2 font-medium">
          변형문항이 입력됨 → 원본 해설 스타일로 변형문항 풀이를 생성합니다
        </p>
      )}

      {problemPreview && solutionPreview && (
        <div className="mt-4 flex gap-3 justify-center">
          <button
            onClick={handleSubmit}
            disabled={isLoading}
            className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? '생성 중...' : mode}
          </button>
          <button
            onClick={handleReset}
            className="px-6 py-2.5 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors"
          >
            초기화
          </button>
        </div>
      )}
    </div>
  )
}
