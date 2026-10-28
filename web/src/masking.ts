/** 展示层脱敏：只在界面上打码，不改后端数据。
    实例 ID：保留前 8 位 + 3 个 * + 后 4 位，中间全打码。
    公网 IPv4：保留前两段，后两段打码，例如 47.76.*.*。
    编辑弹窗里仍显示完整值（管理员自己改配置时需要核对），不在此列。 */

export function maskInstanceId(value?: string | null): string {
  if (!value) return ''
  if (value.length <= 12) {
    return value.length <= 6 ? '******' : `${value.slice(0, 4)}***${value.slice(-2)}`
  }
  return `${value.slice(0, 8)}***${value.slice(-4)}`
}

export function maskIp(value?: string | null): string {
  if (!value) return ''
  const parts = value.split('.')
  if (parts.length === 4 && parts.every((part) => /^\d+$/.test(part))) {
    return `${parts[0]}.${parts[1]}.*.*`
  }
  if (value.includes(':')) {
    const first = value.split(':')[0]
    return first ? `${first}:*:*` : '*.*.*.*'
  }
  return '•'.repeat(Math.min(value.length, 12))
}
