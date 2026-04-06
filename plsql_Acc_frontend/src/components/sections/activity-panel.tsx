import { AlertTriangle, BellRing, CheckCircle2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { ActivityItem, TaskItem } from "@/types/dashboard"

interface ActivityPanelProps {
  activities: ActivityItem[]
  tasks: TaskItem[]
}

function toneIcon(tone: ActivityItem["tone"]) {
  switch (tone) {
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-emerald-600" />
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-amber-600" />
    default:
      return <BellRing className="h-4 w-4 text-sky-600" />
  }
}

function priorityVariant(priority: TaskItem["priority"]) {
  switch (priority) {
    case "High":
      return "danger"
    case "Medium":
      return "warning"
    default:
      return "info"
  }
}

export function ActivityPanel({ activities, tasks }: ActivityPanelProps) {
  return (
    <div className="space-y-6">
      <Card className="animate-rise delay-2">
        <CardHeader>
          <CardTitle>Live Alerts</CardTitle>
          <CardDescription>Latest system and policy notifications</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {activities.map((activity) => (
            <article
              key={activity.title}
              className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3"
            >
              <div className="mb-2 flex items-center gap-2">
                {toneIcon(activity.tone)}
                <p className="text-sm font-semibold text-slate-900">{activity.title}</p>
              </div>
              <p className="text-sm text-slate-600">{activity.message}</p>
              <p className="mt-2 text-xs text-slate-500">{activity.timestamp}</p>
            </article>
          ))}
        </CardContent>
      </Card>

      <Card className="animate-rise delay-3">
        <CardHeader>
          <CardTitle>Upcoming Tasks</CardTitle>
          <CardDescription>Priority items your team should close next</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {tasks.map((task) => (
            <div key={task.title} className="rounded-xl border border-slate-200/80 p-3">
              <div className="mb-2 flex items-start justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{task.title}</p>
                <Badge variant={priorityVariant(task.priority)}>{task.priority}</Badge>
              </div>
              <p className="text-xs text-slate-500">Owner: {task.owner}</p>
              <p className="mt-1 text-xs font-medium text-slate-600">Due: {task.due}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
