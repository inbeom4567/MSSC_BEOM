export default function UsageInfo({ usage }) {
  if (!usage) return null

  return (
    <div className="flex items-center gap-4 text-[11px] text-gray-400 dark:text-[#444A6E] mt-1 px-1 flex-wrap">
      <span>모델: {usage.model.includes('opus') ? 'Opus' : 'Sonnet'}</span>
      <span>입력: {usage.input_tokens.toLocaleString()}t</span>
      <span>출력: {usage.output_tokens.toLocaleString()}t</span>
      <span>합계: {usage.total_tokens.toLocaleString()}t</span>
      <span className="text-gray-500 dark:text-[#7880AA]">
        ${usage.cost_usd} (약 {usage.cost_krw.toLocaleString()}원)
      </span>
    </div>
  )
}
