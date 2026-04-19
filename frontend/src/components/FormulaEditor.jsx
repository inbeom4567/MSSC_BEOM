import { useState, useRef, useCallback } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'

// ── HWP 수식 → LaTeX 변환 ──────────────────────────────────────────
export function hwpToLatex(hwp) {
  let result = hwp
  // 분수: {a} over {b} → \dfrac{a}{b}  (재귀 처리를 위해 반복)
  for (let i = 0; i < 5; i++) {
    result = result.replace(/\{([^{}]*)\}\s+over\s+\{([^{}]*)\}/g, (_, n, d) => `\\dfrac{${n}}{${d}}`)
  }
  return result
    // 루트: sqrt {x} → \sqrt{x}
    .replace(/sqrt\s*\{([^}]*)\}/g, (_, x) => `\\sqrt{${x}}`)
    // 괄호
    .replace(/left\s*\(\s*(.*?)\s*right\s*\)/gs, (_, inner) => `\\left(${inner}\\right)`)
    .replace(/left\s*\[\s*(.*?)\s*right\s*\]/gs, (_, inner) => `\\left[${inner}\\right]`)
    .replace(/left\s*\\\{\s*(.*?)\s*right\s*\\\}/gs, (_, inner) => `\\left\\{${inner}\\right\\}`)
    // 연산자
    .replace(/\bTIMES\b/g, '\\times')
    .replace(/\bDIVIDE\b/g, '\\div')
    .replace(/\bNEQ\b/g, '\\neq')
    .replace(/\bLEQ\b/g, '\\leq')
    .replace(/\bGEQ\b/g, '\\geq')
    .replace(/\bPM\b/g, '\\pm')
    .replace(/\bCDOT\b/g, '\\cdot')
    .replace(/\bINT\b/g, '\\int')
    .replace(/\bSUM\b/g, '\\sum')
    .replace(/\bPROD\b/g, '\\prod')
    .replace(/\bLIM\b/g, '\\lim')
    .replace(/\bINFINITY\b/g, '\\infty')
    // 그리스
    .replace(/\bPI\b/g, '\\pi')
    .replace(/\bALPHA\b/g, '\\alpha')
    .replace(/\bBETA\b/g, '\\beta')
    .replace(/\bTHETA\b/g, '\\theta')
    .replace(/\bDELTA\b/g, '\\delta')
    .replace(/\bSIGMA\b/g, '\\sigma')
    .replace(/\bOMEGA\b/g, '\\omega')
    // 삼각함수
    .replace(/\bsin\b/g, '\\sin')
    .replace(/\bcos\b/g, '\\cos')
    .replace(/\btan\b/g, '\\tan')
    .replace(/\blog\b/g, '\\log')
    .replace(/\bln\b/g, '\\ln')
}

// 텍스트 전체를 파트 배열로 파싱 ([ ] 안이 수식)
export function renderMathText(text) {
  const parts = text.split(/(\[[^\]]+\])/g)
  return parts.map((part, i) => {
    if (part.startsWith('[') && part.endsWith(']') && part.length > 2) {
      const inner = part.slice(1, -1)
      try {
        const html = katex.renderToString(hwpToLatex(inner), { throwOnError: false, displayMode: false })
        return { type: 'math', html, key: i }
      } catch {
        return { type: 'text', text: part, key: i }
      }
    }
    return { type: 'text', text: part, key: i }
  })
}

// ── 팔레트 데이터 ──────────────────────────────────────────────────
const PALETTE = {
  기본: [
    { label: 'a/b', insert: '{} over {}', cursorOffset: 1 },
    { label: '√', insert: 'sqrt {}', cursorOffset: 6 },
    { label: 'xⁿ', insert: '^{}', cursorOffset: 2 },
    { label: 'xₙ', insert: '_{}', cursorOffset: 2 },
    { label: '( )', insert: 'left (  right )', cursorOffset: 7 },
    { label: '[ ]', insert: 'left [  right ]', cursorOffset: 7 },
    { label: '{ }', insert: 'left \\{  right \\}', cursorOffset: 8 },
    { label: '×', insert: 'TIMES', cursorOffset: 0 },
    { label: '÷', insert: 'DIVIDE', cursorOffset: 0 },
    { label: '±', insert: 'PM', cursorOffset: 0 },
    { label: '·', insert: 'CDOT', cursorOffset: 0 },
    { label: '≠', insert: 'NEQ', cursorOffset: 0 },
    { label: '≤', insert: 'LEQ', cursorOffset: 0 },
    { label: '≥', insert: 'GEQ', cursorOffset: 0 },
    { label: '∞', insert: 'INFINITY', cursorOffset: 0 },
  ],
  그리스: [
    { label: 'π', insert: 'PI', cursorOffset: 0 },
    { label: 'α', insert: 'ALPHA', cursorOffset: 0 },
    { label: 'β', insert: 'BETA', cursorOffset: 0 },
    { label: 'θ', insert: 'THETA', cursorOffset: 0 },
    { label: 'δ', insert: 'DELTA', cursorOffset: 0 },
    { label: 'σ', insert: 'SIGMA', cursorOffset: 0 },
    { label: 'ω', insert: 'OMEGA', cursorOffset: 0 },
  ],
  함수: [
    { label: 'sin', insert: 'sin', cursorOffset: 0 },
    { label: 'cos', insert: 'cos', cursorOffset: 0 },
    { label: 'tan', insert: 'tan', cursorOffset: 0 },
    { label: 'log', insert: 'log', cursorOffset: 0 },
    { label: 'ln', insert: 'ln', cursorOffset: 0 },
    { label: '∫', insert: 'INT', cursorOffset: 0 },
    { label: 'Σ', insert: 'SUM', cursorOffset: 0 },
    { label: 'Π', insert: 'PROD', cursorOffset: 0 },
    { label: 'lim', insert: 'LIM', cursorOffset: 0 },
  ],
}

const BOX_INSERTS = [
  { label: '조건박스', text: '\n===조건박스===\n\n===조건박스끝===\n', cursorOffset: 12 },
  { label: '보기박스(2단)', text: '\n===보기박스1===\n\n===보기박스끝===\n', cursorOffset: 13 },
  { label: '보기박스(1단)', text: '\n===보기박스2===\n\n===보기박스끝===\n', cursorOffset: 13 },
  { label: '보기박스(좁은)', text: '\n===보기박스3===\n\n===보기박스끝===\n', cursorOffset: 13 },
  { label: '선지(짧은)', text: '\n① \t② \t③ \n④ \t⑤ \n', cursorOffset: 0 },
  { label: '선지(긴)', text: '\n① \n② \n③ \n④ \n⑤ \n', cursorOffset: 0 },
]

// ── 메인 컴포넌트 ──────────────────────────────────────────────────
/**
 * FormulaEditor
 * props:
 *   value: string — 현재 편집 텍스트
 *   onChange: (newValue: string) => void
 *   onSave: () => void
 *   onCancel: () => void
 */
export default function FormulaEditor({ value, onChange, onSave, onCancel }) {
  const [activeCategory, setActiveCategory] = useState('기본')
  const textareaRef = useRef(null)

  const insertAtCursor = useCallback((insertText, cursorOffset) => {
    const ta = textareaRef.current
    if (!ta) return
    const start = ta.selectionStart
    const end = ta.selectionEnd
    const newVal = value.slice(0, start) + insertText + value.slice(end)
    onChange(newVal)
    const newCursor = cursorOffset > 0 ? start + cursorOffset : start + insertText.length
    requestAnimationFrame(() => {
      ta.focus()
      ta.setSelectionRange(newCursor, newCursor)
    })
  }, [value, onChange])

  const previewParts = renderMathText(value)

  return (
    <div className="rounded-xl border border-gray-200 dark:border-[#353844] overflow-hidden bg-white dark:bg-[#22252E]">
      {/* 팔레트 카테고리 탭 */}
      <div className="flex items-center gap-1 px-3 pt-3 flex-wrap border-b border-gray-100 dark:border-[#2A2D38]">
        {Object.keys(PALETTE).map(cat => (
          <button key={cat} onClick={() => setActiveCategory(cat)}
            className={`px-3 py-1.5 text-xs font-semibold border-b-2 transition-colors ${
              activeCategory === cat
                ? 'border-violet-500 text-violet-600 dark:text-violet-400'
                : 'border-transparent text-gray-500 dark:text-[#5A5E70] hover:text-gray-700 dark:hover:text-gray-300'
            }`}>
            {cat}
          </button>
        ))}
      </div>

      {/* 팔레트 버튼들 */}
      <div className="px-3 py-2 bg-gray-50 dark:bg-[#2A2D38] border-b border-gray-200 dark:border-[#353844] flex flex-wrap gap-1">
        {PALETTE[activeCategory].map((btn, i) => (
          <button key={i}
            onClick={() => insertAtCursor(btn.insert, btn.cursorOffset)}
            className="px-2.5 py-1 rounded border border-gray-200 dark:border-[#353844] bg-white dark:bg-[#22252E] text-gray-700 dark:text-[#E2E4F0] text-sm hover:border-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 font-serif">
            {btn.label}
          </button>
        ))}
      </div>

      {/* 구조 삽입 버튼들 */}
      <div className="px-3 py-2 bg-gray-50 dark:bg-[#2A2D38] border-b border-gray-200 dark:border-[#353844] flex flex-wrap gap-1 items-center">
        <span className="text-xs text-gray-400 dark:text-[#5A5E70] mr-1">구조:</span>
        {BOX_INSERTS.map((btn, i) => (
          <button key={i}
            onClick={() => insertAtCursor(btn.text, btn.cursorOffset ?? 0)}
            className="px-2.5 py-1 rounded border border-dashed border-gray-300 dark:border-[#454854] text-gray-500 dark:text-[#6A6E80] text-xs hover:border-violet-400 hover:text-violet-600 dark:hover:text-violet-400">
            {btn.label}
          </button>
        ))}
      </div>

      {/* 텍스트 에디터 */}
      <div className="px-3 pt-2 pb-1">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full min-h-[120px] bg-gray-50 dark:bg-[#1A1D24] border border-gray-200 dark:border-[#353844] rounded-lg text-sm text-gray-800 dark:text-[#E2E4F0] font-mono p-2.5 outline-none resize-y focus:border-violet-400 dark:focus:border-violet-500"
          placeholder="텍스트를 입력하세요. 수식은 [수식코드] 형태로 입력합니다. 예: [{a} over {b}]"
        />
      </div>

      {/* 미리보기 */}
      <div className="mx-3 mb-2 p-3 bg-white rounded-lg border border-gray-200 text-sm text-gray-900 leading-loose min-h-[60px]">
        <div className="text-xs text-gray-400 mb-1">미리보기</div>
        <div>
          {previewParts.map(part =>
            part.type === 'math'
              ? <span key={part.key} dangerouslySetInnerHTML={{ __html: part.html }} />
              : <span key={part.key} style={{ whiteSpace: 'pre-wrap' }}>{part.text}</span>
          )}
        </div>
      </div>

      {/* 저장/취소 */}
      <div className="flex gap-2 px-3 pb-3">
        <button onClick={onCancel}
          className="flex-1 py-2 rounded-lg border border-gray-200 dark:border-[#353844] text-sm text-gray-500 dark:text-[#5A5E70] hover:bg-gray-50 dark:hover:bg-[#2A2D38]">
          취소
        </button>
        <button onClick={onSave}
          className="flex-1 py-2 rounded-lg text-sm font-semibold text-white bg-gradient-to-r from-violet-600 to-purple-700 hover:from-violet-500 hover:to-purple-600">
          저장
        </button>
      </div>
    </div>
  )
}
