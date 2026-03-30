import { useRef } from 'react'

export default function ImageUploadBox({ preview, label, icon, isDragging, onFile, onDragState }) {
  const inputRef = useRef(null)

  return (
    <div
      className={`flex-1 border-2 border-dashed rounded-xl p-3 text-center cursor-pointer transition-colors min-w-0 ${
        isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
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
}
