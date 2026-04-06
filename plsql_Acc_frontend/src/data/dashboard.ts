import type {
  ActivityItem,
  ContextTab,
  FilterChip,
  HeroData,
  KpiMetric,
  NavItem,
  PipelineItem,
  TaskItem,
  TeamLoadItem,
  TopStripData,
  TransactionItem,
} from "@/types/dashboard"

export const topStripData: TopStripData = {
  environment: "Production Mirror",
  syncLabel: "Synced on March 11, 2026 at 04:10 PM IST",
  links: ["Audit Trail", "Release Notes", "Support"],
}

export const primaryNavItems: NavItem[] = [
  { label: "Overview", active: true },
  { label: "Collections" },
  { label: "Payables", badge: "4" },
  { label: "Reconciliation" },
  { label: "Reports" },
]

export const contextTabs: ContextTab[] = [
  { label: "Control Panel", active: true },
  { label: "Approvals", count: 8 },
  { label: "Workflows", count: 12 },
  { label: "Risk Review", count: 3 },
]

export const filterChips: FilterChip[] = [
  { label: "All Entities", selected: true },
  { label: "North America" },
  { label: "EMEA" },
  { label: "APAC" },
]

export const heroData: HeroData = {
  eyebrow: "Finance Operations Hub",
  title: "Unified accounting cockpit for faster monthly close",
  description:
    "Track approvals, monitor risk, and keep every posting stream audit-ready with a tighter operational view across teams.",
  highlights: [
    { label: "Current Period", value: "March 2026" },
    { label: "Open Exceptions", value: "17" },
    { label: "Auto-Match Rate", value: "94.8%" },
  ],
}

export const kpiMetrics: KpiMetric[] = [
  {
    title: "Collected Today",
    value: "$2.84M",
    delta: "+12.4%",
    direction: "up",
    caption: "Compared to yesterday",
    icon: "wallet",
  },
  {
    title: "Invoices Processed",
    value: "1,248",
    delta: "+8.1%",
    direction: "up",
    caption: "Daily throughput trend",
    icon: "receipt",
  },
  {
    title: "Compliance Score",
    value: "98.2%",
    delta: "+0.7%",
    direction: "up",
    caption: "Policy adherence",
    icon: "shield",
  },
  {
    title: "Avg. Approval Cycle",
    value: "6.4h",
    delta: "-9.2%",
    direction: "down",
    caption: "Lower is better",
    icon: "clock",
  },
]

export const pipelineItems: PipelineItem[] = [
  {
    name: "Vendor accrual closeout",
    owner: "Aditi Sharma",
    progress: 82,
    due: "Mar 12",
    status: "On Track",
  },
  {
    name: "Intercompany balancing",
    owner: "Miguel Ortiz",
    progress: 58,
    due: "Mar 13",
    status: "At Risk",
  },
  {
    name: "Tax journal validation",
    owner: "Rhea George",
    progress: 74,
    due: "Mar 14",
    status: "On Track",
  },
  {
    name: "Expense policy variance review",
    owner: "Noah Bennett",
    progress: 39,
    due: "Mar 15",
    status: "Needs Review",
  },
]

export const teamLoadItems: TeamLoadItem[] = [
  { name: "L. Khan", stream: "AP", utilization: 76, openItems: 13 },
  { name: "R. Gupta", stream: "Treasury", utilization: 64, openItems: 9 },
  { name: "M. Collins", stream: "AR", utilization: 88, openItems: 16 },
  { name: "P. Singh", stream: "Compliance", utilization: 52, openItems: 6 },
]

export const transactionItems: TransactionItem[] = [
  {
    id: "TX-18472",
    vendor: "Bluefin Logistics",
    category: "Freight",
    amount: "$48,200",
    dueDate: "Mar 12, 2026",
    status: "Approved",
  },
  {
    id: "TX-18468",
    vendor: "Northline Media",
    category: "Marketing",
    amount: "$16,800",
    dueDate: "Mar 12, 2026",
    status: "Pending",
  },
  {
    id: "TX-18457",
    vendor: "Ventrix Cloud",
    category: "Software",
    amount: "$93,450",
    dueDate: "Mar 13, 2026",
    status: "Escalated",
  },
  {
    id: "TX-18449",
    vendor: "Orchid Facilities",
    category: "Operations",
    amount: "$25,110",
    dueDate: "Mar 13, 2026",
    status: "Approved",
  },
  {
    id: "TX-18442",
    vendor: "Peakline Consulting",
    category: "Advisory",
    amount: "$37,900",
    dueDate: "Mar 14, 2026",
    status: "Pending",
  },
]

export const activityItems: ActivityItem[] = [
  {
    title: "Policy breach flagged",
    message: "Travel spend exceeded approval limit in entity E-104.",
    timestamp: "9 mins ago",
    tone: "warning",
  },
  {
    title: "Journal batch posted",
    message: "Batch JRN-4421 has been posted to the general ledger.",
    timestamp: "22 mins ago",
    tone: "success",
  },
  {
    title: "Rate card updated",
    message: "New vendor discount matrix applied for Q2 procurement.",
    timestamp: "1 hour ago",
    tone: "info",
  },
]

export const taskItems: TaskItem[] = [
  {
    title: "Approve disputed freight invoice",
    owner: "Treasury Lead",
    due: "Today, 06:30 PM",
    priority: "High",
  },
  {
    title: "Resolve missing PO references",
    owner: "AP Operations",
    due: "Mar 12, 11:00 AM",
    priority: "Medium",
  },
  {
    title: "Finalize compliance evidence pack",
    owner: "Risk Team",
    due: "Mar 13, 03:00 PM",
    priority: "Low",
  },
]
