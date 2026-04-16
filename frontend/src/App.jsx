import { useState, useCallback, useEffect } from 'react'
import TabCreateVariant from './components/TabCreateVariant'
import TabSolveVariant from './components/TabSolveVariant'
import TabHwpx from './components/TabHwpx'
import TabHistory from './components/TabHistory'
import TabPromptEdit from './components/TabPromptEdit'
import TabScan from './components/TabScan'
import GuidelinesModal from './components/GuidelinesModal'

const FEATURES = [
  { id: 'create', label: '유사문항 생성', desc: '이미지 → 유사문항', icon: '✦', color: 'bg-indigo-500' },
  { id: 'solve', label: '변형문항 해설', desc: '이미지 → 해설', icon: '✎', color: 'bg-violet-500' },
  { id: 'scan', label: '스캔 처리', desc: '스캔 → HWP + 유사문항', icon: '⊡', color: 'bg-sky-500' },
  { id: 'hwpx', label: '한글 파일', desc: '.hwpx → 유사문항/해설', icon: '⬡', color: 'bg-orange-500' },
  { id: 'history', label: '히스토리', desc: '저장 · 비교', icon: '≋', color: 'bg-slate-500' },
  { id: 'prompt', label: '프롬프트 설정', desc: '피드백 반영', icon: '⚙', color: 'bg-slate-500' },
]

const GRADES = [
  { value: 'none', label: '학년 무관' },
  { value: 'mid1', label: '중1' },
  { value: 'mid2', label: '중2' },
  { value: 'mid3', label: '중3' },
  { value: 'high1', label: '고1' },
  { value: 'high2_math1', label: '고2 수I' },
  { value: 'high2_math2', label: '고2 수II' },
  { value: 'high3_prob', label: '확률과 통계' },
  { value: 'high3_calc', label: '미적분' },
  { value: 'high3_geo', label: '기하' },
]

const MODELS = [
  { value: 'sonnet', label: 'Sonnet' },
  { value: 'opus', label: 'Opus' },
]

function App() {
  const [activeFeature, setActiveFeature] = useState(null)
  const [grade, setGrade] = useState('none')
  const [model, setModel] = useState('sonnet')
  const [guidelines, setGuidelines] = useState('')
  const [guidelinesName, setGuidelinesName] = useState('')
  const [savedGuidelines, setSavedGuidelines] = useState(() => {
    try { return JSON.parse(localStorage.getItem('mathsol_guidelines') || '[]') } catch { return [] }
  })
  const [showGuidelinesModal, setShowGuidelinesModal] = useState(false)

  // 다크모드: 기본값 dark
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('ms_theme')
    return saved ? saved === 'dark' : true
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('ms_theme', dark ? 'dark' : 'light')
  }, [dark])

  const saveGuidelinesToStorage = useCallback((list) => {
    setSavedGuidelines(list)
    localStorage.setItem('mathsol_guidelines', JSON.stringify(list))
  }, [])

  const handleAddGuideline = useCallback((name, content) => {
    saveGuidelinesToStorage([...savedGuidelines, { name, content, id: Date.now() }])
  }, [savedGuidelines, saveGuidelinesToStorage])

  const handleDeleteGuideline = useCallback((id) => {
    saveGuidelinesToStorage(savedGuidelines.filter(g => g.id !== id))
  }, [savedGuidelines, saveGuidelinesToStorage])

  const handleApplyGuideline = useCallback((content) => {
    setGuidelines(content)
    setShowGuidelinesModal(false)
  }, [])

  const commonProps = { grade, model, guidelines }

  return (
    <div className="min-h-screen bg-[#F8F9FB] dark:bg-[#0A0B14] flex flex-col transition-colors">

      {/* ── 헤더 ── */}
      <header className="bg-white dark:bg-[#11131F]/90 border-b border-gray-200 dark:border-[#222644] sticky top-0 z-30 backdrop-blur-md">
        <div className="max-w-5xl mx-auto px-5 h-[52px] flex items-center justify-between">
          <button
            onClick={() => setActiveFeature(null)}
            className="flex items-center gap-2.5 hover:opacity-80 transition-opacity"
          >
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center text-white text-xs font-black shadow-[0_0_12px_rgba(108,127,255,0.35)]">
              M
            </div>
            <span className="text-sm font-bold text-gray-900 dark:text-[#E8EAFF] tracking-tight">MathSolution</span>
          </button>

          <div className="flex items-center gap-2">
            {activeFeature && (
              <button
                onClick={() => setActiveFeature(null)}
                className="text-xs text-gray-400 dark:text-[#7880AA] hover:text-gray-600 dark:hover:text-[#E8EAFF] flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-gray-200 dark:border-[#222644] transition-colors"
              >
                ← 홈
              </button>
            )}
            <button
              onClick={() => setDark(d => !d)}
              className="w-8 h-8 rounded-lg border border-gray-200 dark:border-[#222644] bg-gray-50 dark:bg-[#191C2E] text-gray-400 dark:text-[#7880AA] hover:text-gray-700 dark:hover:text-[#E8EAFF] transition-colors flex items-center justify-center text-sm"
              title="테마 전환"
            >
              {dark ? '☀' : '🌙'}
            </button>
          </div>
        </div>
      </header>

      {/* ── 메인 ── */}
      <main className="flex-1 max-w-5xl mx-auto px-5 w-full pb-24">
        {!activeFeature ? (

          /* ===== 홈 화면 ===== */
          <div className="py-12">
            <div className="text-center mb-10">
              <h1 className="text-2xl font-bold text-gray-800 dark:text-[#E8EAFF] mb-2 tracking-tight">
                수학 유사문항의 모든 것
              </h1>
              <p className="text-sm text-gray-400 dark:text-[#7880AA]">문제 이미지를 넣으면 유사문항과 풀이를 자동으로 생성합니다</p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 max-w-3xl mx-auto">
              {FEATURES.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setActiveFeature(f.id)}
                  className="group flex flex-col items-center gap-3 p-5 bg-white dark:bg-[#11131F] rounded-2xl border border-gray-200 dark:border-[#222644] hover:border-indigo-400 dark:hover:border-indigo-500 hover:shadow-lg dark:hover:shadow-[0_4px_20px_rgba(108,127,255,0.1)] transition-all duration-200"
                >
                  <div className={`w-12 h-12 ${f.color} rounded-xl flex items-center justify-center text-xl text-white shadow-sm group-hover:scale-110 transition-transform`}>
                    {f.icon}
                  </div>
                  <div className="text-center">
                    <div className="text-xs font-semibold text-gray-800 dark:text-[#E8EAFF]">{f.label}</div>
                    <div className="text-[11px] text-gray-400 dark:text-[#7880AA] mt-0.5">{f.desc}</div>
                  </div>
                </button>
              ))}
            </div>

            {/* 홈 설정 바 */}
            <div className="mt-10 max-w-xl mx-auto">
              <div className="bg-white dark:bg-[#11131F] rounded-2xl border border-gray-200 dark:border-[#222644] p-4 shadow-sm">
                <div className="flex items-center gap-3 flex-wrap justify-center">
                  <SettingsBar
                    grade={grade} setGrade={setGrade}
                    model={model} setModel={setModel}
                    guidelines={guidelines} guidelinesName={guidelinesName}
                    setGuidelines={setGuidelines} setGuidelinesName={setGuidelinesName}
                    onOpenModal={() => setShowGuidelinesModal(true)}
                  />
                </div>
              </div>
            </div>
          </div>

        ) : (

          /* ===== 기능 화면 ===== */
          <div className="py-5">
            {/* 언더라인 탭 */}
            <div className="flex gap-0 border-b border-gray-200 dark:border-[#222644] mb-6 overflow-x-auto">
              {FEATURES.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setActiveFeature(f.id)}
                  className={`px-4 py-3 text-[13px] font-medium whitespace-nowrap border-b-2 -mb-px transition-all ${
                    activeFeature === f.id
                      ? 'border-indigo-500 text-indigo-500 dark:text-indigo-400 font-semibold'
                      : 'border-transparent text-gray-400 dark:text-[#7880AA] hover:text-gray-600 dark:hover:text-[#E8EAFF]'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {activeFeature === 'create' && <TabCreateVariant {...commonProps} />}
            {activeFeature === 'solve' && <TabSolveVariant {...commonProps} />}
            {activeFeature === 'scan' && <TabScan {...commonProps} />}
            {activeFeature === 'hwpx' && <TabHwpx {...commonProps} />}
            {activeFeature === 'history' && <TabHistory />}
            {activeFeature === 'prompt' && <TabPromptEdit />}
          </div>
        )}
      </main>

      {/* ── 하단 고정 설정바 (기능 화면) ── */}
      {activeFeature && !['history', 'prompt', 'scan'].includes(activeFeature) && (
        <div className="fixed bottom-0 left-0 right-0 bg-white/90 dark:bg-[#11131F]/90 border-t border-gray-200 dark:border-[#222644] z-30 shadow-lg backdrop-blur-md">
          <div className="max-w-5xl mx-auto px-5 py-2.5 flex items-center gap-3 flex-wrap justify-center">
            <SettingsBar
              grade={grade} setGrade={setGrade}
              model={model} setModel={setModel}
              guidelines={guidelines} guidelinesName={guidelinesName}
              setGuidelines={setGuidelines} setGuidelinesName={setGuidelinesName}
              onOpenModal={() => setShowGuidelinesModal(true)}
            />
          </div>
        </div>
      )}

      {/* 지침 모달 */}
      {showGuidelinesModal && (
        <GuidelinesModal
          currentGuidelines={guidelines}
          currentName={guidelinesName}
          savedGuidelines={savedGuidelines}
          onApply={(name, content) => { setGuidelinesName(name); handleApplyGuideline(content) }}
          onSave={handleAddGuideline}
          onDelete={handleDeleteGuideline}
          onClose={() => setShowGuidelinesModal(false)}
        />
      )}
    </div>
  )
}

function SettingsBar({ grade, setGrade, model, setModel, guidelines, guidelinesName, setGuidelines, setGuidelinesName, onOpenModal }) {
  return (
    <>
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-semibold text-gray-400 dark:text-[#7880AA] uppercase tracking-wide">학년</span>
        <select
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
          className="text-[13px] border border-gray-200 dark:border-[#2E3356] rounded-lg px-2.5 py-1.5 bg-gray-50 dark:bg-[#191C2E] text-gray-700 dark:text-[#E8EAFF] focus:outline-none focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500 transition-colors"
        >
          {GRADES.map(g => <option key={g.value} value={g.value}>{g.label}</option>)}
        </select>
      </div>

      <div className="w-px h-5 bg-gray-200 dark:bg-[#2E3356]" />

      <div className="flex items-center gap-2">
        <span className="text-[11px] font-semibold text-gray-400 dark:text-[#7880AA] uppercase tracking-wide">모델</span>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="text-[13px] border border-gray-200 dark:border-[#2E3356] rounded-lg px-2.5 py-1.5 bg-gray-50 dark:bg-[#191C2E] text-gray-700 dark:text-[#E8EAFF] focus:outline-none focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500 transition-colors"
        >
          {MODELS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </div>

      <div className="w-px h-5 bg-gray-200 dark:bg-[#2E3356]" />

      <button
        onClick={onOpenModal}
        className={`flex items-center gap-1.5 text-[13px] px-3 py-1.5 rounded-lg border transition-colors ${
          guidelines
            ? 'border-indigo-400 dark:border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400'
            : 'border-gray-200 dark:border-[#2E3356] bg-gray-50 dark:bg-[#191C2E] text-gray-500 dark:text-[#7880AA] hover:bg-gray-100 dark:hover:bg-[#212540]'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        지침{guidelines ? ' ✓' : ''}
      </button>

      {guidelines && (
        <>
          <span className="text-[11px] text-gray-400 dark:text-[#7880AA] truncate max-w-[160px]">
            {guidelinesName || guidelines.slice(0, 25)}
          </span>
          <button
            onClick={() => { setGuidelines(''); setGuidelinesName('') }}
            className="text-[11px] text-red-400 hover:text-red-500 transition-colors"
          >
            해제
          </button>
        </>
      )}
    </>
  )
}

export default App
