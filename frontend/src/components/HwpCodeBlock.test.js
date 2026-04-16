import { describe, test, expect } from 'vitest'
import { hwpToLatex } from './HwpCodeBlock'

describe('hwpToLatex — 수식 변환', () => {
  // 관계 기호
  test('ge → \\geq', () => {
    expect(hwpToLatex('x ge 0')).toBe('x \\geq 0')
  })
  test('le → \\leq', () => {
    expect(hwpToLatex('x le 0')).toBe('x \\leq 0')
  })
  test('ne → \\neq', () => {
    expect(hwpToLatex('x ne 0')).toBe('x \\neq 0')
  })
  test('pm → \\pm', () => {
    expect(hwpToLatex('a pm b')).toBe('a \\pm b')
  })

  // 연산자
  test('cdot → \\cdot', () => {
    expect(hwpToLatex('a cdot b')).toBe('a \\cdot b')
  })
  test('times → \\times', () => {
    expect(hwpToLatex('a times b')).toBe('a \\times b')
  })

  // 함수
  test('sqrt → \\sqrt', () => {
    expect(hwpToLatex('sqrt')).toBe('\\sqrt')
  })
  test('sum → \\sum', () => {
    expect(hwpToLatex('sum')).toBe('\\sum')
  })
  test('int → \\int', () => {
    expect(hwpToLatex('int')).toBe('\\int')
  })
  test('lim → \\lim', () => {
    expect(hwpToLatex('lim')).toBe('\\lim')
  })
  test('log → \\log', () => {
    expect(hwpToLatex('log')).toBe('\\log')
  })
  test('sin → \\sin', () => {
    expect(hwpToLatex('sin')).toBe('\\sin')
  })
  test('cos → \\cos', () => {
    expect(hwpToLatex('cos')).toBe('\\cos')
  })
  test('infty → \\infty', () => {
    expect(hwpToLatex('infty')).toBe('\\infty')
  })

  // 그리스 문자
  test('alpha → \\alpha', () => {
    expect(hwpToLatex('alpha')).toBe('\\alpha')
  })
  test('beta → \\beta', () => {
    expect(hwpToLatex('beta')).toBe('\\beta')
  })
  test('pi → \\pi', () => {
    expect(hwpToLatex('pi')).toBe('\\pi')
  })
  test('theta → \\theta', () => {
    expect(hwpToLatex('theta')).toBe('\\theta')
  })
  test('sigma → \\sigma', () => {
    expect(hwpToLatex('sigma')).toBe('\\sigma')
  })
  test('omega → \\omega', () => {
    expect(hwpToLatex('omega')).toBe('\\omega')
  })

  // 대괄호
  test('left( → \\left(', () => {
    expect(hwpToLatex('left (')).toBe('\\left(')
  })
  test('right) → \\right)', () => {
    expect(hwpToLatex('right )')).toBe('\\right)')
  })

  // 복합 수식
  test('복합: sin x ge 0', () => {
    expect(hwpToLatex('sin x ge 0')).toBe('\\sin x \\geq 0')
  })
  test('빈 문자열', () => {
    expect(hwpToLatex('')).toBe('')
  })
  test('LaTeX 이미 들어있는 경우 — 겹쳐서 깨지지 않아야 함', () => {
    const result = hwpToLatex('alpha + beta')
    expect(result).toContain('\\alpha')
    expect(result).toContain('\\beta')
  })
})
