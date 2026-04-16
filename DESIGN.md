# MathSolution Design System

> 수학 유사문항 생성기 — 고등학교 수학 교사를 위한 도구.  
> React + Tailwind CSS v4. 기본 테마: 다크 모드.

---

## 1. 브랜드 아이덴티티

**이름**: MathSolution  
**로고 마크**: `M` — 7×7 rounded-lg, indigo-to-violet 그라디언트, 흰색 볼드 텍스트  
**성격**: 정확하고 조용한 도구. 화려함보다 신뢰감. 수능 교재처럼 군더더기 없는 스타일.

---

## 2. 컬러 팔레트

### 다크 모드 (기본)

| 역할 | 토큰 | Hex |
|------|------|-----|
| 페이지 배경 | `bg-page` | `#0A0B14` |
| 카드/표면 (기본) | `bg-surface` | `#11131F` |
| 카드/표면 (중간) | `bg-surface-2` | `#191C2E` |
| 테두리 (강) | `border-strong` | `#222644` |
| 테두리 (약) | `border-subtle` | `#2E3356` |
| 텍스트 — 주 | `text-primary` | `#E8EAFF` |
| 텍스트 — 보조 | `text-secondary` | `#C8CADF` |
| 텍스트 — 흐림 | `text-muted` | `#7880AA` |
| 텍스트 — 비활성 | `text-disabled` | `#444A6E` |
| 포커스 링 | — | `rgba(108,127,255,0.30)` |
| 로고 글로우 | — | `rgba(108,127,255,0.35)` |

### 라이트 모드

| 역할 | Tailwind |
|------|---------|
| 페이지 배경 | `bg-[#F8F9FB]` |
| 카드/표면 | `bg-white` |
| 테두리 | `border-gray-200` |
| 텍스트 — 주 | `text-gray-900` |
| 텍스트 — 보조 | `text-gray-700` |
| 텍스트 — 흐림 | `text-gray-400` |

### 액센트

| 역할 | 값 |
|------|-----|
| 주 액센트 | `indigo-500` (#6366F1) |
| 보조 액센트 | `violet-500` (#8B5CF6) |
| 그라디언트 (버튼/로고) | `from-indigo-500 to-violet-500` |
| 탭 활성 색 | `indigo-500` / `dark:indigo-400` |
| 포커스 테두리 | `indigo-500` |

### 시맨틱 컬러

| 상태 | 라이트 | 다크 |
|------|--------|------|
| 에러 배경 | `bg-red-50` | `bg-red-900/10` |
| 에러 테두리 | `border-red-300` | `border-red-800` |
| 에러 텍스트 | `text-red-600` | `text-red-400` |
| 성공 | `text-green-600` | `text-green-400` |
| 경고 | `text-yellow-600` | `text-yellow-400` |

---

## 3. 타이포그래피

**폰트**: Pretendard (폴백: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`)

| 역할 | 크기 | 굵기 | 용도 |
|------|------|------|------|
| 페이지 제목 | `text-2xl` (24px) | `font-bold` | 홈 h1 |
| 섹션 제목 | `text-lg` / `text-base` | `font-semibold` | 카드 헤딩 |
| 탭 레이블 | `text-[13px]` | `font-medium` / `font-semibold` (활성) | 탭 바 |
| 본문 | `text-sm` (14px) | `font-normal` | 설명, 입력값 |
| 캡션 | `text-xs` (12px) | `font-normal` | 서브텍스트 |
| 마이크로 | `text-[11px]` | `font-semibold` | 레이블, 배지 |

**자간**: `tracking-tight` — 제목류에 적용.

---

## 4. 간격 & 레이아웃

| 항목 | 값 |
|------|-----|
| 최대 너비 | `max-w-5xl` (1024px) |
| 페이지 패딩 | `px-5` |
| 헤더 높이 | `52px` |
| 카드 모서리 | `rounded-2xl` (feature 카드), `rounded-xl` (아이콘), `rounded-lg` (입력/버튼) |
| 카드 내부 패딩 | `p-5` (기능 카드), `p-4` (설정 바) |
| 그리드 gap | `gap-3` |
| 섹션 간격 | `mb-6` (탭 아래), `mb-10` (홈 카드 위) |
| 하단 고정바 높이 | `py-2.5` |
| 하단 콘텐츠 여백 | `pb-24` (하단바 겹침 방지) |

---

## 5. 컴포넌트

### 5.1 헤더

```
sticky top-0 z-30 backdrop-blur-md
bg-white dark:bg-[#11131F]/90
border-b border-gray-200 dark:border-[#222644]
h-[52px]
```

- 좌: 로고 마크(7×7) + 앱 이름
- 우: `← 홈` 버튼(기능 화면에서만) + 테마 전환 버튼

### 5.2 기능 카드 (홈)

```
flex flex-col items-center gap-3 p-5
bg-white dark:bg-[#11131F] rounded-2xl
border border-gray-200 dark:border-[#222644]
hover:border-indigo-400 dark:hover:border-indigo-500
hover:shadow-lg dark:hover:shadow-[0_4px_20px_rgba(108,127,255,0.1)]
transition-all duration-200
```

- 아이콘 박스: `w-12 h-12 rounded-xl`, 각 탭별 고유 색상
  - 유사문항 생성: `bg-indigo-500`
  - 변형문항 해설: `bg-violet-500`
  - 스캔 처리: `bg-sky-500`
  - 한글 파일: `bg-orange-500`
  - 히스토리/설정: `bg-slate-500`
- 호버 시 아이콘 `scale-110`

### 5.3 탭 바 (기능 화면)

```
border-b border-gray-200 dark:border-[#222644]
```

각 탭:
```
px-4 py-3 text-[13px] font-medium border-b-2 -mb-px transition-all
```

- 활성: `border-indigo-500 text-indigo-500 dark:text-indigo-400 font-semibold`
- 비활성: `border-transparent text-gray-400 dark:text-[#7880AA]`
- 호버: `hover:text-gray-600 dark:hover:text-[#E8EAFF]`

### 5.4 하단 고정 설정 바

```
fixed bottom-0 left-0 right-0 z-30
bg-white/90 dark:bg-[#11131F]/90
border-t border-gray-200 dark:border-[#222644]
backdrop-blur-md shadow-lg
```

히스토리, 프롬프트 설정, 스캔 탭에서는 숨김.

### 5.5 입력 요소 (Select, Input)

```
text-[13px] border border-gray-200 dark:border-[#2E3356] rounded-lg
px-2.5 py-1.5
bg-gray-50 dark:bg-[#191C2E]
text-gray-700 dark:text-[#E8EAFF]
focus:outline-none focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500
transition-colors
```

### 5.6 기본 버튼

**기본 (텍스트/아이콘)**:
```
border border-gray-200 dark:border-[#2E3356]
bg-gray-50 dark:bg-[#191C2E]
text-gray-500 dark:text-[#7880AA]
hover:bg-gray-100 dark:hover:bg-[#212540]
rounded-lg px-3 py-1.5 text-[13px] transition-colors
```

**강조 (그라디언트)**:
```
bg-gradient-to-r from-indigo-500 to-violet-500
text-white font-medium rounded-lg
shadow-[0_0_12px_rgba(108,127,255,0.25)]
hover:shadow-[0_0_18px_rgba(108,127,255,0.4)]
transition-all
```

**에러 액션**:
```
bg-red-100 dark:bg-red-900/30
text-red-700 dark:text-red-300
hover:bg-red-200 dark:hover:bg-red-900/50
rounded-md px-3 py-1 text-xs transition-colors
```

**활성 상태 (지침 적용됨)**:
```
border-indigo-400 dark:border-indigo-500
bg-indigo-50 dark:bg-indigo-500/10
text-indigo-600 dark:text-indigo-400
```

### 5.7 카드 / 패널

```
bg-white dark:bg-[#11131F] rounded-2xl
border border-gray-200 dark:border-[#222644]
shadow-sm p-4
```

중첩 표면:
```
bg-gray-50 dark:bg-[#191C2E] rounded-xl
border border-gray-100 dark:border-[#2E3356]
```

### 5.8 그래프 이미지 (GraphImage)

```
my-4 relative group
```

버튼 오버레이: 항상 표시 (hover-only 금지)
```
absolute top-2 right-2 flex gap-1
```

버튼:
```
px-2 py-1 bg-gray-700 text-gray-200 rounded text-xs hover:bg-gray-600
```

에러 상태:
```
my-4 flex flex-col items-center justify-center gap-2
rounded-lg border border-dashed
border-red-300 dark:border-red-800
bg-red-50 dark:bg-red-900/10
p-6 text-center
```

### 5.9 스크롤바 (다크 모드)

```css
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #11131F; }
::-webkit-scrollbar-thumb { background: #2E3356; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3E4470; }
```

### 5.10 구분선

세로: `w-px h-5 bg-gray-200 dark:bg-[#2E3356]`  
가로: `border-b border-gray-200 dark:border-[#222644]`

---

## 6. 모션

| 적용처 | 값 |
|--------|-----|
| 페이지 테마 전환 | `transition-colors` |
| 카드 hover | `transition-all duration-200` |
| 아이콘 hover scale | `transition-transform` |
| 버튼 hover | `transition-colors` |
| 입력 focus | `transition-colors` |

애니메이션은 최소로. 기능 전환에는 fade 없음 — 즉각 전환.

---

## 7. 수학 그래프 스타일

이 앱의 핵심 출력물 — 교과서/수능 스타일 준수.

- **배경**: 흰색
- **축**: 검정, `linewidth=1.5`, 화살표 끝
- **함수 선**: 검정, `linewidth=2`
- **보조선**: 회색, 점선 (`linestyle='--'`, `alpha=0.5`)
- **포인트**: 속이 찬 원 `(zorder=5)`
- **레이블**: 10~11pt, LaTeX 렌더링
- **원점**: 반드시 알파벳 대문자 **O** (숫자 0 금지)
- **여백**: `tight_layout(pad=0.8)`
- **출력**: PNG, DPI 150, 워터마크 없음

---

## 8. 접근성

- 색상만으로 상태를 전달하지 않음 — 아이콘 또는 텍스트 병행
- 포커스 링: `focus:ring-2 focus:ring-indigo-400/30 focus:border-indigo-500`
- 버튼에 `title` 속성으로 툴팁 제공 (테마 전환 등)
- 터치 지원: 버튼은 항상 표시 (hover-only 패턴 사용 금지)

---

## 9. 파일 구조 참조

```
frontend/
  src/
    index.css          ← 폰트, 다크모드 variant, 스크롤바, body 배경
    App.jsx            ← 헤더, 탭, 설정 바, 테마 토글
    components/
      GraphImage.jsx   ← 그래프 표시, 복사/저장 버튼
      SolutionDisplay.jsx ← 수식 버튼 렌더링
      ImageUploadBox.jsx  ← 드래그앤드롭 업로드
      TabCreateVariant.jsx
      TabSolveVariant.jsx
      TabHwpx.jsx
      TabScan.jsx
      TabHistory.jsx
      TabPromptEdit.jsx
      GuidelinesModal.jsx
      HwpCodeBlock.jsx    ← 한글 수식 코드 블록
```
