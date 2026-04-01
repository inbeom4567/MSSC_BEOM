import { useState } from 'react'
import TabCreateVariant from './components/TabCreateVariant'
import TabSolveVariant from './components/TabSolveVariant'
import TabHwpx from './components/TabHwpx'
import TabHistory from './components/TabHistory'
import TabPromptEdit from './components/TabPromptEdit'

const TABS = [
  { id: 'create', label: '유사문항 생성', desc: '이미지 → 유사문항' },
  { id: 'solve', label: '변형문항 해설', desc: '이미지 → 해설' },
  { id: 'hwpx', label: '한글 파일', desc: '.hwpx → 유사문항/해설' },
  { id: 'history', label: '히스토리', desc: '저장 · 비교' },
  { id: 'prompt', label: '프롬프트', desc: '피드백 반영' },
]

function App() {
  const [activeTab, setActiveTab] = useState('create')

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <header className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-800">수학 유사문항 생성기</h1>
        </header>

        <div className="flex border-b border-gray-200 mb-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-3 text-center transition-colors border-b-2 ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600 font-bold'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <div className="text-sm">{tab.label}</div>
              <div className="text-xs text-gray-400 mt-0.5">{tab.desc}</div>
            </button>
          ))}
        </div>

        {activeTab === 'create' && <TabCreateVariant />}
        {activeTab === 'solve' && <TabSolveVariant />}
        {activeTab === 'hwpx' && <TabHwpx />}
        {activeTab === 'history' && <TabHistory />}
        {activeTab === 'prompt' && <TabPromptEdit />}
      </div>
    </div>
  )
}

export default App
