export interface TopStripData {
  environment: string
  syncLabel: string
  links: string[]
}

export interface NavItem {
  label: string
  active?: boolean
  badge?: string
}

export interface ContextTab {
  label: string
  count?: number
  active?: boolean
}

export interface FilterChip {
  label: string
  selected?: boolean
}

export interface HeroHighlight {
  label: string
  value: string
}

export interface HeroData {
  eyebrow: string
  title: string
  description: string
  highlights: HeroHighlight[]
}

export type KpiIcon = "wallet" | "receipt" | "shield" | "clock"

export interface KpiMetric {
  title: string
  value: string
  delta: string
  direction: "up" | "down"
  caption: string
  icon: KpiIcon
}

export type PipelineStatus = "On Track" | "At Risk" | "Needs Review"

export interface PipelineItem {
  name: string
  owner: string
  progress: number
  due: string
  status: PipelineStatus
}

export interface TeamLoadItem {
  name: string
  stream: string
  utilization: number
  openItems: number
}

export type TransactionStatus = "Approved" | "Pending" | "Escalated"

export interface TransactionItem {
  id: string
  vendor: string
  category: string
  amount: string
  dueDate: string
  status: TransactionStatus
}

export type ActivityTone = "info" | "success" | "warning"

export interface ActivityItem {
  title: string
  message: string
  timestamp: string
  tone: ActivityTone
}

export interface TaskItem {
  title: string
  owner: string
  due: string
  priority: "High" | "Medium" | "Low"
}
