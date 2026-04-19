import { useState, useEffect } from 'react'
import ImageInputMode from './ImageInputMode'
import HwpxInputMode from './HwpxInputMode'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

export default function TabCreateVariant({ grade, model, guidelines }) {
  const [mode, setMode] = useState(null)
  const [hwpConverterAvailable, setHwpConverterAvailable] = useState(false)

  useEffect(() => {
    fetch(`${API}/api/system-info`)
      .then(r => r.json())
      .then(d => setHwpConverterAvailable(!!d.hwp_converter_available))
      .catch(() => {})
  }, [])

  if (mode === 'image') {
    return (
      <div className="space-y-4">
        <button
          onClick={() => setMode(null)}
          className="text-xs text-gray-400 dark:text-[#8a8f98] hover:text-gray-600 dark:hover:text-[#f7f8f8] flex items-center gap-1"
        >
          ← 입력 방식 다시 선택
        </button>
        <ImageInputMode grade={grade} model={model} guidelines={guidelines} />
      </div>
    )
  }

  if (mode === 'hwpx') {
    return (
      <div className="space-y-4">
        <button
          onClick={() => setMode(null)}
          className="text-xs text-gray-400 dark:text-[#8a8f98] hover:text-gray-600 dark:hover:text-[#f7f8f8] flex items-center gap-1"
        >
          ← 입력 방식 다시 선택
        </button>
        <HwpxInputMode grade={grade} model={model} guidelines={guidelines} hwpConverterAvailable={hwpConverterAvailable} />
      </div>
    )
  }

  // 모드 선택 화면
  return (
    <div className="space-y-6 py-4">
      <div className="text-center">
        <h2 className="text-base font-semibold text-gray-700 dark:text-[#d0d0d5]">입력 방식을 선택하세요</h2>
        <p className="text-xs text-gray-400 dark:text-[#8a8f98] mt-1">문제와 해설을 어떻게 입력할지 고르면 됩니다</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={() => setMode('image')}
          className="group flex flex-col items-center gap-4 p-6 bg-white dark:bg-[#0f1011] rounded-2xl border-2 border-gray-200 dark:border-[rgba(255,255,255,0.06)] hover:border-indigo-400 dark:hover:border-indigo-500 hover:shadow-lg dark:hover:shadow-[0_4px_20px_rgba(108,127,255,0.12)] transition-all duration-200"
        >
          <div className="w-14 h-14 bg-indigo-500 rounded-2xl flex items-center justify-center text-2xl text-white shadow-sm group-hover:scale-110 transition-transform">
            📸
          </div>
          <div className="text-center">
            <div className="text-sm font-semibold text-gray-800 dark:text-[#f7f8f8]">이미지로 입력</div>
            <div className="text-xs text-gray-400 dark:text-[#8a8f98] mt-1">문제·해설 이미지를 직접 업로드</div>
          </div>
        </button>

        <button
          onClick={() => setMode('hwpx')}
          className="group flex flex-col items-center gap-4 p-6 bg-white dark:bg-[#0f1011] rounded-2xl border-2 border-gray-200 dark:border-[rgba(255,255,255,0.06)] hover:border-orange-400 dark:hover:border-orange-500 hover:shadow-lg dark:hover:shadow-[0_4px_20px_rgba(245,158,11,0.12)] transition-all duration-200"
        >
          <div className="w-14 h-14 bg-orange-500 rounded-2xl flex items-center justify-center text-2xl text-white shadow-sm group-hover:scale-110 transition-transform">
            📄
          </div>
          <div className="text-center">
            <div className="text-sm font-semibold text-gray-800 dark:text-[#f7f8f8]">한글 파일 입력</div>
            <div className="text-xs text-gray-400 dark:text-[#8a8f98] mt-1">
              {hwpConverterAvailable ? 'HWP / HWPX 파일에서 문제 선택' : 'HWPX 파일에서 문제 선택'}
            </div>
          </div>
        </button>
      </div>
    </div>
  )
}
