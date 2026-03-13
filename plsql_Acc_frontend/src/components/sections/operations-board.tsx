import { ArrowUpRight, Users2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { PipelineItem, TeamLoadItem } from "@/types/dashboard"

interface OperationsBoardProps {
  pipelineItems: PipelineItem[]
  teamLoadItems: TeamLoadItem[]
}

function pipelineStatusVariant(status: PipelineItem["status"]) {
  switch (status) {
    case "On Track":
      return "success"
    case "At Risk":
      return "warning"
    default:
      return "danger"
  }
}

export function OperationsBoard({ pipelineItems, teamLoadItems }: OperationsBoardProps) {
  return (
    <section className="grid gap-6 xl:grid-cols-12">
      <Card className="xl:col-span-8 animate-rise delay-1">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Workflow Progress</CardTitle>
              <CardDescription>Track each close activity by owner and due date</CardDescription>
            </div>
            <a href="#" className="inline-flex items-center text-sm font-medium text-emerald-700 hover:text-emerald-800">
              Open board
              <ArrowUpRight className="ml-1 h-4 w-4" />
            </a>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {pipelineItems.map((item) => (
            <div
              key={item.name}
              className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-4 transition-all hover:-translate-y-0.5 hover:bg-white hover:shadow-md"
            >
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                  <p className="text-xs text-slate-500">Owner: {item.owner}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={pipelineStatusVariant(item.status)}>{item.status}</Badge>
                  <span className="text-xs font-medium text-slate-500">Due {item.due}</span>
                </div>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500"
                  style={{ width: `${item.progress}%` }}
                />
              </div>
              <p className="mt-2 text-xs font-medium text-slate-600">{item.progress}% complete</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="xl:col-span-4 animate-rise delay-2">
        <CardHeader>
          <CardTitle className="inline-flex items-center gap-2">
            <Users2 className="h-4 w-4 text-slate-500" />
            Team Capacity
          </CardTitle>
          <CardDescription>Load balancing across operational streams</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {teamLoadItems.map((member) => (
            <div key={member.name} className="space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-800">{member.name}</p>
                  <p className="text-xs text-slate-500">{member.stream}</p>
                </div>
                <p className="text-xs font-semibold text-slate-600">{member.openItems} open</p>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-slate-700"
                  style={{ width: `${member.utilization}%` }}
                />
              </div>
              <p className="text-xs text-slate-500">{member.utilization}% utilization</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </section>
  )
}
