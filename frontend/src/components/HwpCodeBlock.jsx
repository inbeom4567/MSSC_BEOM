import { useMemo } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'

// HWP 수식 코드 → LaTeX 변환 (공유 유틸)
export function hwpToLatex(hwp) {
  let s = (hwp || '').trim()

  // 백틱 연산자 처리: `^` → ^, `_` → _
  s = s.replace(/`\^`/g, '^')
  s = s.replace(/`_`/g, '_')
  s = s.replace(/`([^`\s]+)`/g, '$1')

  // HWP 괄호 → LaTeX
  s = s.replace(/\bleft\s*\(/g, '\\left(')
  s = s.replace(/\bright\s*\)/g, '\\right)')
  s = s.replace(/\bleft\s*\[/g, '\\left[')
  s = s.replace(/\bright\s*\]/g, '\\right]')
  s = s.replace(/\bleft\s*\{/g, '\\left\\{')
  s = s.replace(/\bright\s*\}/g, '\\right\\}')
  s = s.replace(/\bleft\s*\|/g, '\\left|')
  s = s.replace(/\bright\s*\|/g, '\\right|')

  // 관계 기호
  s = s.replace(/\bge\b/g, '\\geq')
  s = s.replace(/\ble\b/g, '\\leq')
  s = s.replace(/\bne\b/g, '\\neq')
  s = s.replace(/\bapprox\b/g, '\\approx')
  s = s.replace(/\bsim\b/g, '\\sim')
  s = s.replace(/\bpm\b/g, '\\pm')
  s = s.replace(/\bmp\b/g, '\\mp')

  // 연산자
  s = s.replace(/\bcdot\b/g, '\\cdot')
  s = s.replace(/\btimes\b/g, '\\times')
  s = s.replace(/\bdiv\b/g, '\\div')

  // 함수/기호
  s = s.replace(/\bsqrt\b/g, '\\sqrt')
  s = s.replace(/\bfrac\b/g, '\\frac')
  s = s.replace(/\bsum\b/g, '\\sum')
  s = s.replace(/\bprod\b/g, '\\prod')
  s = s.replace(/\bint\b/g, '\\int')
  s = s.replace(/\blim\b/g, '\\lim')
  s = s.replace(/\binfty\b/g, '\\infty')
  s = s.replace(/\blog\b/g, '\\log')
  s = s.replace(/\bln\b/g, '\\ln')
  s = s.replace(/\bsin\b/g, '\\sin')
  s = s.replace(/\bcos\b/g, '\\cos')
  s = s.replace(/\btan\b/g, '\\tan')
  s = s.replace(/\bmax\b/g, '\\max')
  s = s.replace(/\bmin\b/g, '\\min')
  s = s.replace(/\bover\b/g, '\\over')
  s = s.replace(/\bldots\b/g, '\\ldots')
  s = s.replace(/\bcdots\b/g, '\\cdots')
  s = s.replace(/\bvdots\b/g, '\\vdots')

  // 그리스 문자 (소문자)
  const greeks = ['alpha','beta','gamma','delta','epsilon','zeta','eta','theta',
    'iota','kappa','lambda','mu','nu','xi','pi','rho','sigma','tau','upsilon',
    'phi','chi','psi','omega']
  const GREEKS = ['Gamma','Delta','Theta','Lambda','Xi','Pi','Sigma','Upsilon','Phi','Psi','Omega']
  ;[...greeks, ...GREEKS].forEach(g => {
    s = s.replace(new RegExp(`\\b${g}\\b`, 'g'), `\\${g}`)
  })

  return s
}

export default function HwpCodeBlock({ code, inline = false }) {
  const latexHtml = useMemo(() => {
    try {
      const tex = hwpToLatex(code)
      return katex.renderToString(tex, {
        throwOnError: false,
        displayMode: !inline,
        output: 'html',
      })
    } catch {
      return null
    }
  }, [code, inline])

  if (inline) {
    if (latexHtml) {
      return (
        <span
          className="inline-flex items-center bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200/60 dark:border-indigo-500/20 rounded-[5px] px-1.5 py-px mx-px align-middle"
          dangerouslySetInnerHTML={{ __html: latexHtml }}
        />
      )
    }
    // LaTeX 변환 실패 시 원본 코드 표시
    return (
      <span className="bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded text-xs border border-indigo-200/60 dark:border-indigo-500/20 font-mono align-middle">
        {code}
      </span>
    )
  }

  // 블록 모드
  return (
    <div className="my-3 px-4 py-3 bg-gray-50 dark:bg-[#191C2E] rounded-lg border border-gray-200 dark:border-[#2E3356] overflow-x-auto">
      {latexHtml ? (
        <div dangerouslySetInnerHTML={{ __html: latexHtml }} />
      ) : (
        <pre className="text-sm text-gray-600 dark:text-gray-300 font-mono">{code}</pre>
      )}
    </div>
  )
}
