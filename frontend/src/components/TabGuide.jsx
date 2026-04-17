import { useState } from 'react'

const SECTIONS = [
  {
    id: 'create',
    title: '유사문항 생성',
    icon: '✦',
    color: 'bg-indigo-500',
    accent: 'border-indigo-200 dark:border-indigo-500/30',
    badge: 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300',
    desc: '원본 문제·해설 이미지를 넣으면 유사문항과 풀이를 자동으로 만들어줍니다.',
    steps: [
      {
        step: '1단계',
        title: '이미지 올리기',
        body: '원본 문제 이미지를 왼쪽 칸에, 원본 해설 이미지를 오른쪽 칸에 드래그하거나 클릭해서 올립니다. JPG, PNG 모두 됩니다.',
      },
      {
        step: '2단계',
        title: '변형 유형·난이도 선택',
        body: '숫자 변형은 숫자·조건만 바꾸고, 아이디어 변형은 문제 구조 자체를 바꿉니다. 난이도는 쉽게/비슷하게/어렵게 중 선택하세요.',
      },
      {
        step: '3단계',
        title: '생성 버튼 클릭',
        body: '버튼을 누르면 AI가 유사문항과 풀이를 만들어 줍니다. 보통 30초~1분 정도 걸립니다.',
      },
      {
        step: '4단계',
        title: '수식 코드 복사하기',
        body: '결과에서 파란 [수식] 버튼을 클릭하면 한글 수식입력기 코드가 클립보드에 복사됩니다. 한글에서 수식입력기를 열고 붙여넣기 하면 됩니다.',
      },
    ],
    tips: [
      '결과가 마음에 안 들면 아래 "수정 요청" 칸에 지시사항을 입력해 다시 요청할 수 있습니다.',
      '추가 지시사항 칸에 "4지선다 형식으로" 같은 요청을 미리 넣을 수 있습니다.',
    ],
  },
  {
    id: 'solve',
    title: '변형문항 해설',
    icon: '✎',
    color: 'bg-violet-500',
    accent: 'border-violet-200 dark:border-violet-500/30',
    badge: 'bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-300',
    desc: '이미 만들어진 변형문항에 풀이만 자동으로 작성해줍니다. 이미지 3장이 필요합니다.',
    steps: [
      {
        step: '1단계',
        title: '이미지 3장 올리기',
        body: '순서대로: ① 원본 문제 ② 원본 해설 ③ 변형문항. 변형문항은 이미 만들어진 문제 이미지를 올리면 됩니다.',
      },
      {
        step: '2단계',
        title: '해설 작성 버튼 클릭',
        body: 'AI가 원본 해설의 풀이 스타일을 참고해서 변형문항 풀이를 작성합니다. 문제 내용은 건드리지 않고 풀이만 씁니다.',
      },
      {
        step: '3단계',
        title: '수식 코드 복사',
        body: '[수식] 버튼을 클릭해 한글 수식입력기 코드를 복사합니다.',
      },
    ],
    tips: [
      '원본 문제·해설이 정확할수록 풀이 품질이 좋아집니다.',
      '변형문항이 원본과 많이 다를 때(발문 형식 변경 등) Opus 모델을 쓰면 더 정확합니다.',
    ],
  },
  {
    id: 'scan',
    title: '스캔 처리',
    icon: '⊡',
    color: 'bg-sky-500',
    accent: 'border-sky-200 dark:border-sky-500/30',
    badge: 'bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300',
    desc: '스캔한 시험지나 문제집 이미지를 올리면 문제를 자동으로 인식해 한글 수식 코드로 변환합니다.',
    steps: [
      {
        step: '1단계',
        title: '파일 올리기',
        body: '스캔 이미지(JPG/PNG) 또는 PDF를 올립니다. PDF는 페이지마다 자동으로 분리됩니다.',
      },
      {
        step: '2단계',
        title: '문제 영역 확인',
        body: 'AI가 각 문제의 위치를 빨간 박스로 표시합니다. 잘못 감지된 박스는 클릭해서 삭제하고, 빠진 문제는 드래그로 박스를 직접 그릴 수 있습니다.',
      },
      {
        step: '3단계',
        title: '처리 방식 선택',
        body: '타이핑만(수식 변환만), 타이핑+해설(변환+풀이 작성), 유사문항 생성(변환+풀이+유사문항) 중 선택합니다.',
      },
      {
        step: '4단계',
        title: '처리 시작',
        body: '처리 시작 버튼을 누르면 문제별로 순서대로 처리됩니다. 화면 오른쪽 아래에 처리 진행 상황이 표시됩니다. 각 문제가 완료될 때마다 결과가 바로 나타납니다.',
      },
      {
        step: '5단계',
        title: '결과 확인 및 한글 파일 다운로드',
        body: '모든 처리가 끝나면 "한글 파일 다운로드" 버튼이 나타납니다. 클릭하면 결과가 담긴 .hwpx 파일을 받을 수 있습니다.',
      },
    ],
    tips: [
      '스캔 품질이 좋을수록 인식 정확도가 높아집니다. 300DPI 이상을 권장합니다.',
      '처리 중에 다른 탭으로 이동해도 처리는 계속됩니다. 화면 오른쪽 아래 배지를 클릭해서 돌아오면 됩니다.',
    ],
  },
  {
    id: 'hwpx',
    title: '한글 파일',
    icon: '⬡',
    color: 'bg-orange-500',
    accent: 'border-orange-200 dark:border-orange-500/30',
    badge: 'bg-orange-50 dark:bg-orange-500/10 text-orange-700 dark:text-orange-300',
    desc: '.hwpx 한글 파일을 직접 올리면 문제를 인식해서 유사문항이나 해설을 만들어줍니다.',
    steps: [
      {
        step: '1단계',
        title: '.hwpx 파일 올리기',
        body: '한글 문서(.hwpx)를 드래그하거나 클릭해서 올립니다. 파일을 올리면 안에 들어 있는 문제 개수와 미리보기가 표시됩니다.',
      },
      {
        step: '2단계',
        title: '처리할 문제 선택',
        body: '체크박스로 유사문항을 만들 문제를 선택합니다. 전체 선택도 가능합니다.',
      },
      {
        step: '3단계',
        title: '생성 및 다운로드',
        body: '생성 버튼을 누르면 선택한 문제들을 동시에 처리합니다. 완료되면 결과가 담긴 .hwpx 파일을 다운로드 받을 수 있습니다.',
      },
    ],
    tips: [
      '한글 파일에 문제와 해설이 모두 들어 있어야 가장 좋은 결과가 나옵니다.',
      '문제가 많을수록 시간이 걸립니다. 처음엔 1~2개만 선택해서 테스트해보세요.',
    ],
  },
  {
    id: 'history',
    title: '히스토리',
    icon: '≋',
    color: 'bg-slate-500',
    accent: 'border-slate-200 dark:border-slate-500/30',
    badge: 'bg-slate-50 dark:bg-slate-500/10 text-slate-700 dark:text-slate-300',
    desc: '이전에 생성한 결과를 다시 볼 수 있습니다. 서버를 재시작해도 기록이 남아 있습니다.',
    steps: [
      {
        step: '1단계',
        title: '목록에서 찾기',
        body: '날짜·시간·작업 종류가 목록으로 표시됩니다. 원하는 항목을 클릭하면 결과 내용이 펼쳐집니다.',
      },
      {
        step: '2단계',
        title: '수식 코드 다시 복사',
        body: '결과에서 [수식] 버튼을 클릭하면 다시 복사할 수 있습니다. 항목 오른쪽 휴지통 아이콘으로 삭제도 가능합니다.',
      },
    ],
    tips: [
      '생성한 결과는 모두 자동 저장됩니다. 별도로 저장 버튼을 누를 필요가 없습니다.',
    ],
  },
  {
    id: 'prompt',
    title: '프롬프트 설정',
    icon: '⚙',
    color: 'bg-slate-500',
    accent: 'border-slate-200 dark:border-slate-500/30',
    badge: 'bg-slate-50 dark:bg-slate-500/10 text-slate-700 dark:text-slate-300',
    desc: '결과에서 반복적으로 틀리는 부분을 피드백으로 입력하면 앞으로의 결과에 반영됩니다.',
    steps: [
      {
        step: '1단계',
        title: '잘못된 부분 입력',
        body: '예) "플러스마이너스는 pm이 아니라 +- 로 써야 합니다" 처럼 구체적으로 입력합니다.',
      },
      {
        step: '2단계',
        title: '"프롬프트에 반영" 클릭',
        body: 'AI가 피드백을 규칙으로 변환해 저장합니다. 이후 생성되는 결과에 즉시 반영됩니다. 서버 재시작 없이 바로 적용됩니다.',
      },
    ],
    tips: [
      '피드백은 누적됩니다. 자주 틀리는 표현이 있으면 하나씩 등록해두면 점점 정확해집니다.',
    ],
  },
]

const COMMON_TIPS = [
  {
    icon: '📋',
    title: '수식 코드 복사',
    body: '결과 화면에서 파란색 [수식] 버튼을 클릭하면 한글 수식입력기 코드가 자동으로 복사됩니다. 한글에서 수식입력기(Ctrl+N, E)를 열고 붙여넣기(Ctrl+V) 하면 됩니다.',
  },
  {
    icon: '🎓',
    title: '학년 선택',
    body: '하단 또는 홈 화면의 학년 선택에서 학생 학년을 고르면 해당 학년 교육과정에 맞는 개념만 사용됩니다. 예를 들어 중3으로 선택하면 미분·적분 개념이 나오지 않습니다.',
  },
  {
    icon: '🤖',
    title: 'Sonnet vs Opus',
    body: 'Sonnet은 빠르고 저렴합니다. 대부분의 경우에 충분합니다. Opus는 느리고 비싸지만 복잡한 문제나 고난도 풀이에서 더 정확합니다. 처음엔 Sonnet으로 시작하세요.',
  },
  {
    icon: '📝',
    title: '지침 활용',
    body: '자주 쓰는 추가 지시사항(예: "수능 스타일로", "4지선다 형식으로")을 지침으로 저장해두면 매번 입력하지 않아도 됩니다. 상단 "지침" 버튼을 눌러 저장하고 적용하세요.',
  },
]

function Section({ section }) {
  const [open, setOpen] = useState(true)

  return (
    <div className={`rounded-2xl border ${section.accent} bg-white dark:bg-[#11131F] overflow-hidden`}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 ${section.color} rounded-xl flex items-center justify-center text-white text-base`}>
            {section.icon}
          </div>
          <div>
            <div className="text-sm font-bold text-gray-800 dark:text-[#E8EAFF]">{section.title}</div>
            <div className="text-xs text-gray-400 dark:text-[#7880AA] mt-0.5">{section.desc}</div>
          </div>
        </div>
        <span className={`text-gray-400 dark:text-[#7880AA] text-lg transition-transform ${open ? 'rotate-180' : ''}`}>
          ▾
        </span>
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-gray-100 dark:border-[#222644]">
          <div className="mt-4 space-y-3">
            {section.steps.map((s) => (
              <div key={s.step} className="flex gap-3">
                <span className={`shrink-0 mt-0.5 text-[11px] font-bold px-2 py-0.5 rounded-full ${section.badge}`}>
                  {s.step}
                </span>
                <div>
                  <div className="text-sm font-semibold text-gray-800 dark:text-[#E8EAFF]">{s.title}</div>
                  <div className="text-sm text-gray-500 dark:text-[#9BA3C7] mt-0.5 leading-relaxed">{s.body}</div>
                </div>
              </div>
            ))}
          </div>

          {section.tips && section.tips.length > 0 && (
            <div className="mt-4 p-3 bg-gray-50 dark:bg-[#191C2E] rounded-xl border border-gray-100 dark:border-[#2E3356]">
              <div className="text-[11px] font-bold text-gray-400 dark:text-[#7880AA] uppercase tracking-wide mb-2">팁</div>
              <ul className="space-y-1.5">
                {section.tips.map((tip, i) => (
                  <li key={i} className="flex gap-2 text-xs text-gray-500 dark:text-[#9BA3C7] leading-relaxed">
                    <span className="shrink-0 text-gray-300 dark:text-[#444A6E]">•</span>
                    {tip}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function TabGuide() {
  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="p-4 bg-indigo-50 dark:bg-indigo-500/5 rounded-2xl border border-indigo-200 dark:border-indigo-500/20">
        <h3 className="font-bold text-indigo-800 dark:text-indigo-300 mb-1">MathSolution 사용 설명서</h3>
        <p className="text-sm text-indigo-600 dark:text-indigo-400/70">
          각 탭을 펼쳐서 단계별 사용 방법을 확인하세요.
        </p>
      </div>

      {/* 탭별 가이드 */}
      <div className="space-y-3">
        {SECTIONS.map(section => (
          <Section key={section.id} section={section} />
        ))}
      </div>

      {/* 공통 팁 */}
      <div className="rounded-2xl border border-gray-200 dark:border-[#222644] bg-white dark:bg-[#11131F] overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-[#222644]">
          <div className="text-sm font-bold text-gray-800 dark:text-[#E8EAFF]">공통 팁</div>
          <div className="text-xs text-gray-400 dark:text-[#7880AA] mt-0.5">모든 탭에서 알아두면 좋은 것들</div>
        </div>
        <div className="p-5 grid sm:grid-cols-2 gap-4">
          {COMMON_TIPS.map((tip) => (
            <div key={tip.title} className="flex gap-3">
              <span className="text-xl shrink-0">{tip.icon}</span>
              <div>
                <div className="text-sm font-semibold text-gray-800 dark:text-[#E8EAFF]">{tip.title}</div>
                <div className="text-xs text-gray-500 dark:text-[#9BA3C7] mt-0.5 leading-relaxed">{tip.body}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
