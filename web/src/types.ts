export type SiteType = 'china' | 'international'

/** 服务器被哪个自动化流程托管；null 表示闲散机器，可随时手动开关机 */
export type Managed = {
  kind: 'keepalive' | 'group'
  name: string
  active: boolean
  group_id?: number
  keepalive_id?: number
}

/** 费用快照：本月账单 + 账户余额，来自 BSS（慢数据，后台定时刷新） */
export type Billing = {
  /** 本月税前消费；null = 还没查到（刚添加 / 缺 BSS 权限） */
  monthly_cost: number | null
  /** 账户可用额度；null = 还没查到 */
  balance: number | null
  currency: string
  /** 账单所属账期 YYYY-MM */
  cycle: string
  /** true = 这份数字是上个月的，跨月后还没刷新 */
  stale: boolean
  updated_at: number
  error: string
}

/** DNS 绑定的目标：一台服务器（含单机保活）或一个换班组 */
export type DnsTarget = {
  kind: 'server' | 'group'
  id: number
  label: string
  status: string
  running: boolean
  ip: string
  /** 换班组专用：此刻当班那台叫什么 */
  duty?: string
}

/** 一条域名记录 + 它绑给了谁 + 上次同步结果 */
export type DnsRecord = {
  record: string
  target: DnsTarget | null
  last_ip: string
  last_status: string
  last_at: number
  /** 目标现在在跑的话，应该解析到的 IP；没跑就是空串 */
  desired_ip: string
  state: 'unbound' | 'idle' | 'pending' | 'synced' | 'error'
}

export type DnsState = {
  enabled: boolean
  provider: string
  configured: boolean
  ttl: string
  proxied: boolean
  records: DnsRecord[]
}

export type Server = {
  id: number
  label: string
  access_key_masked: string
  region_id: string
  site: SiteType
  instance_id: string
  quota_gb: number
  threshold_gb: number
  remark: string
  traffic_used: number | null
  traffic_percent: number | null
  /** TX 补丁：CDT 接口流量（GB），None = 本轮未成功查到 */
  cdt_gb?: number | null
  /** TX 补丁：合并值来自哪一方：cdt / tx / max */
  traffic_source?: string | null
  /** TX 补丁：机器上报 TX（GB），None = 从未上报 */
  tx_gb?: number | null
  /** TX 补丁：TX 是否在 180 秒新鲜窗口内 */
  tx_fresh?: boolean
  /** TX 补丁：面板收到 TX 的时间戳（秒），0 = 从未上报 */
  tx_received_at?: number
  /** TX 补丁：距上次 TX 上报的秒数，None = 从未上报 */
  tx_age_seconds?: number | null
  /** TX 补丁：TX 所属月份 YYYY-MM */
  tx_month?: string
  instance_status: string
  stopped_mode: string
  public_ip: string
  traffic_checked_at: number
  status_checked_at: number
  secret_configured: boolean
  managed?: Managed | null
  billing: Billing
  /** 绑定的 DNS 域名；空串 = 没占任何记录 */
  dns_record?: string
}

export type Keepalive = {
  id: number
  server_id: number
  enabled: boolean
  created_at: number
  label: string
  instance_status: string
  stopped_mode: string
  public_ip: string
  traffic_used: number | null
  quota_gb: number
  threshold_gb: number
  instance_id: string
  region_id: string
  site?: SiteType
  status_checked_at: number
  dns_record?: string
}

export type ShiftMember = {
  id: number
  server_id: number
  position: number
  hours: number
  enabled: boolean
  is_duty: boolean
  /** 班次名称，如「白班」「夜班」 */
  slot_name: string
  /** 固定起止时刻 HH:MM（时刻表模式）；空串 = 走老 hours 累加 */
  start_time: string
  end_time: string
  server: Server | null
}

export type ShiftGroup = {
  id: number
  name: string
  enabled: boolean
  failover_enabled: boolean
  ddns_record: string
  anchor_at: number
  cycle_hours: number
  members: ShiftMember[]
  duty_server_id: number
  shift_started_at: number
  next_switch_at: number
  phase: string
  phase_label: string
  note: string
  updated_at: number
  current_index: number
}

export type EventItem = {
  id: number
  ts: number
  level: string
  kind: string
  group_id: number
  server_id: number
  title: string
  detail: string
  /** running 进行中 / done 完成 / error 失败 */
  status: string
  /** 完成过程日志 [{ts, text}]：几点几分干了什么 */
  progress: { ts: number; text: string }[]
  /** 完成 / 失败时间戳，0 = 还没结束 */
  finished_at: number
}

export type Overview = {
  now: string
  now_ts: number
  timezone: string
  version: string
  brand: string
  repo: string
  servers: Server[]
  keepalives: Keepalive[]
  groups: ShiftGroup[]
  dns: DnsState
  notifications: {
    channels: string[]
    telegram: boolean
    email: boolean
    webhook: boolean
  }
  events: EventItem[]
}

export type Settings = {
  admin_username: string
  timezone: string
  traffic_threshold_pct: string
  reconcile_interval: string
  billing_enabled: boolean
  billing_interval: string
  daily_report_enabled: boolean
  daily_report_time: string
  notify_on_shift: boolean
  notify_on_failover: boolean
  notify_on_recovery: boolean
  notify_on_breaker: boolean
  notify_on_limit_stop: boolean
  notify_on_error: boolean
  notify_on_keepalive: boolean
  ddns: {
    enabled: boolean
    provider: string
    cf_auth_mode: string
    cf_token_configured: boolean
    cf_email: string
    cf_key_configured: boolean
    zone_id: string
    record: string
    records: string[]
    ttl: string
    proxied: boolean
    last_ip: string
    last_status: string
  }
  telegram: {
    enabled: boolean
    token_configured: boolean
    chat_id: string
    proxy: string
  }
  email: {
    enabled: boolean
    host: string
    port: string
    security: string
    username: string
    password_configured: boolean
    to: string
  }
  webhook: {
    enabled: boolean
    url: string
    method: string
    headers_configured: boolean
    body: string
  }
  channels: string[]
  sdk_ready: boolean
  dry_run: boolean
  repo?: string
  version?: string
}

export type InitStatus = {
  initialized: boolean
  brand: string
  version: string
  repo: string
}

export function emptyServer(): Server {
  return {
    id: 0,
    label: '',
    access_key_masked: '',
    region_id: 'cn-hongkong',
    site: 'china',
    instance_id: '',
    quota_gb: 200,
    threshold_gb: 188,
    remark: '',
    traffic_used: null,
    traffic_percent: null,
    instance_status: 'Unknown',
    stopped_mode: '',
    public_ip: '',
    traffic_checked_at: 0,
    status_checked_at: 0,
    secret_configured: false,
    billing: {
      monthly_cost: null,
      balance: null,
      currency: 'CNY',
      cycle: '',
      stale: false,
      updated_at: 0,
      error: '',
    },
  }
}
