import { Download, Search, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { ContextTab, FilterChip } from "@/types/dashboard"

interface ContextNavbarProps {
  tabs: ContextTab[]
  filters: FilterChip[]
}

export function ContextNavbar({ tabs, filters }: ContextNavbarProps) {
  return (
    <div className="border-b border-slate-200/80 bg-white/75 backdrop-blur-lg">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 md:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {tabs.map((tab) => (
              <a
                key={tab.label}
                href="#"
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors ${
                  tab.active
                    ? "bg-emerald-100 text-emerald-700"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {tab.label}
                {tab.count ? (
                  <span className="rounded-full bg-white/80 px-2 py-0.5 text-xs font-semibold text-slate-600">
                    {tab.count}
                  </span>
                ) : null}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4" />
              Export
            </Button>
            <Button variant="secondary" size="sm">
              <Sparkles className="h-4 w-4" />
              Automate Close
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full max-w-xl">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input placeholder="Search invoice, vendor, journal..." className="pl-9" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {filters.map((filter) => (
              <button
                key={filter.label}
                className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
                  filter.selected
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
