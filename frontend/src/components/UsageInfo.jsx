export default function UsageInfo({ usage }) {
  if (!usage) return null

  return (
    <div className="flex items-center gap-4 text-xs text-gray-400 mt-2 px-1">
      <span>모델: {usage.model.includes('opus') ? 'Opus' : 'Sonnet'}</span>
      <span>입력: {usage.input_tokens.toLocaleString()}t</span>
      <span>출력: {usage.output_tokens.toLocaleString()}t</span>
      <span>합계: {usage.total_tokens.toLocaleString()}t</span>
      <span className="font-medium text-gray-500">
        비용: ${usage.cost_usd} (약 {usage.cost_krw.toLocaleString()}원)
      </span>
    </div>
  )
}
