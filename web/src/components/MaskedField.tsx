import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

/** 可逆打码：默认只显示打码版，点击展开完整值，再点一次收回。
    不是单向隐藏——不进编辑弹窗也能在原地核对完整值，截图时默认仍是打码的。 */
export default function MaskedField({
  full,
  masked,
  fallback,
}: {
  full?: string | null
  masked: string
  fallback: string
}) {
  const [revealed, setRevealed] = useState(false)
  if (!full) return <>{fallback}</>
  return (
    <span
      role="button"
      tabIndex={0}
      title={revealed ? '点击隐藏' : '点击显示完整值'}
      onClick={() => setRevealed((value) => !value)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          setRevealed((value) => !value)
        }
      }}
      style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}
    >
      {revealed ? full : masked}
      {revealed ? <EyeOff size={11} /> : <Eye size={11} />}
    </span>
  )
}
