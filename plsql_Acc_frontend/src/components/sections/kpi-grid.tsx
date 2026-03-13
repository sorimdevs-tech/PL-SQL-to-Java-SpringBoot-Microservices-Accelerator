import {
  Clock3,
  ReceiptText,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { KpiMetric } from "@/types/dashboard"

interface KpiGridProps {
  metrics: KpiMetric[]
}

const iconMap = {
  wallet: Wallet,
  receipt: ReceiptText,
  shield: ShieldCheck,
  clock: Clock3,
}

export function KpiGrid({ metrics }: KpiGridProps) {
  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric, index) => {
        const Icon = iconMap[metric.icon]
        const TrendIcon = metric.direction === "up" ? TrendingUp : TrendingDown
        const trendColor =
          metric.direction === "up"
            ? "text-emerald-600 bg-emerald-50 border-emerald-100"
            : "text-sky-700 bg-sky-50 border-sky-100"

        return (
          <Card key={metric.title} className={`animate-rise delay-${Math.min(index + 1, 4)}`}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardDescription>{metric.title}</CardDescription>
                <div className="rounded-lg border border-slate-200 bg-white p-2 text-slate-700">
                  <Icon className="h-4 w-4" />
                </div>
              </div>
              <CardTitle className="text-2xl">{metric.value}</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold ${trendColor}`}
              >
                <TrendIcon className="h-3.5 w-3.5" />
                {metric.delta}
              </p>
              <p className="mt-2 text-sm text-slate-500">{metric.caption}</p>
            </CardContent>
          </Card>
        )
      })}
    </section>
  )
}
