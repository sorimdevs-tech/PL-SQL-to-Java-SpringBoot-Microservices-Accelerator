import { LifeBuoy, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { TopStripData } from "@/types/dashboard"

interface TopStripProps {
  data: TopStripData
}

export function TopStrip({ data }: TopStripProps) {
  return (
    <div className="border-b border-slate-200/80 bg-white/70 backdrop-blur-lg">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2 text-xs md:px-6 lg:px-8">
        <div className="flex items-center gap-2 text-slate-600">
          <Badge variant="info" className="normal-case tracking-normal">
            <ShieldCheck className="mr-1 h-3 w-3" />
            {data.environment}
          </Badge>
          <span>{data.syncLabel}</span>
        </div>

        <div className="flex items-center gap-3 text-slate-500">
          {data.links.map((item) => (
            <a
              key={item}
              href="#"
              className="transition-colors hover:text-slate-800"
              aria-label={item}
            >
              {item}
            </a>
          ))}
          <a
            href="#"
            className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-2 py-1 text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
          >
            <LifeBuoy className="h-3.5 w-3.5" />
            Chat
          </a>
        </div>
      </div>
    </div>
  )
}
