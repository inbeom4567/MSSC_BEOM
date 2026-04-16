import { useRef } from 'react'

export default function ImageUploadBox({ preview, label, icon, isDragging, onFile, onDragState }) {
  const inputRef = useRef(null)

  return (
    <div
      className={`flex-1 border-2 border-dashed rounded-xl p-3 text-center cursor-pointer transition-colors min-w-0 ${
        isDragging
          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10'
          : 'border-gray-300 dark:border-[#2E3356] hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-gray-50 dark:hover:bg-indigo-500/5'
      }`}
      onDragOver={(e) => { e.preventDefault(); onDragState(true) }}
      onDragLeave={() => onDragState(false)}
      onDrop={(e) => { e.preventDefault(); onDragState(false); onFile(e.dataTransfer.files[0]) }}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => { onFile(e.target.files[0]); e.target.value = '' }}
      />
      {preview ? (
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-[#7880AA] mb-2">{label}</p>
          <img src={preview} alt={label} className="max-h-48 mx-auto rounded-lg" />
        </div>
      ) : (
        <div className="py-4">
          <div className="text-2xl mb-1 opacity-60">{icon}</div>
          <p className="text-gray-600 dark:text-[#7880AA] font-medium text-xs">{label}</p>
          <p className="text-gray-400 dark:text-[#444A6E] text-xs mt-1">클릭 또는 Ctrl+V</p>
        </div>
      )}
    </div>
  )
}
