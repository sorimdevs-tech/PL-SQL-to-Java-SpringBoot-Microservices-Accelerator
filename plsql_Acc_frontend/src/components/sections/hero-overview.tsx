import { ArrowRight, CalendarClock, WandSparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import type { HeroData } from "@/types/dashboard"

interface HeroOverviewProps {
  data: HeroData
}

export function HeroOverview({ data }: HeroOverviewProps) {
  return (
    <Card className="relative overflow-hidden border-none bg-gradient-to-br from-slate-900 via-slate-800 to-emerald-900 text-white shadow-2xl shadow-slate-900/30 animate-rise">
      <div className="absolute -right-12 -top-12 h-44 w-44 rounded-full bg-emerald-400/25 blur-3xl" />
      <div className="absolute bottom-0 left-8 h-28 w-28 rounded-full bg-cyan-300/20 blur-2xl" />

      <div className="relative z-10 grid gap-6 p-6 lg:grid-cols-12 lg:items-end">
        <div className="space-y-4 lg:col-span-8">
          <p className="inline-flex items-center rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100">
            {data.eyebrow}
          </p>
          <h1 className="max-w-2xl text-2xl font-bold leading-tight md:text-4xl">
            {data.title}
          </h1>
          <p className="max-w-2xl text-sm text-slate-200 md:text-base">{data.description}</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary">
              <WandSparkles className="h-4 w-4" />
              Start Smart Run
            </Button>
            <Button variant="outline" className="border-white/30 bg-white/10 text-white hover:bg-white/20">
              <CalendarClock className="h-4 w-4" />
              Review Schedule
            </Button>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3 lg:col-span-4 lg:grid-cols-1">
          {data.highlights.map((item, index) => (
            <div
              key={item.label}
              className={`rounded-xl border border-white/15 bg-white/10 p-3 backdrop-blur-sm animate-rise delay-${
                index + 1
              }`}
            >
              <p className="text-xs uppercase tracking-[0.14em] text-slate-300">{item.label}</p>
              <p className="mt-1 flex items-center justify-between text-lg font-semibold">
                {item.value}
                <ArrowRight className="h-4 w-4 text-slate-300" />
              </p>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
