import { Cable, CheckCircle2, Compass, FileSearch2, Rocket, ShieldCheck } from "lucide-react"

import type { WorkflowStep } from "@/types/converter"

interface ConversionStepperProps {
  steps: WorkflowStep[]
  activeStep: number
  onStepClick: (stepId: number) => void
}

const iconMap = {
  1: Cable,
  2: FileSearch2,
  3: Compass,
  4: ShieldCheck,
  5: Rocket,
} as const

export function ConversionStepper({ steps, activeStep, onStepClick }: ConversionStepperProps) {
  return (
    <nav className="rounded-2xl border border-slate-200/80 bg-white/90 px-3 py-2 shadow-lg shadow-slate-200/40 backdrop-blur">
      <ul className="flex flex-wrap items-stretch gap-2">
        {steps.map((step) => {
          const Icon = iconMap[step.id as keyof typeof iconMap]
          const isActive = step.id === activeStep
          const isDone = step.id < activeStep

          return (
            <li key={step.id} className="min-w-[180px] flex-1">
              <button
                onClick={() => onStepClick(step.id)}
                className={`w-full cursor-pointer rounded-xl border px-3 py-3 text-left transition-all duration-200 ${
                  isActive
                    ? "border-cyan-300 bg-cyan-50"
                    : isDone
                      ? "border-emerald-200 bg-emerald-50"
                      : "border-transparent bg-slate-50 hover:border-slate-200 hover:bg-slate-100"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-white text-slate-700 shadow-sm">
                    <Icon className="h-4 w-4" />
                  </div>
                  {isDone ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : null}
                </div>
                <p className="mt-2 text-sm font-semibold text-slate-900">{step.title}</p>
                <p className="text-xs text-slate-500">{step.subtitle}</p>
                {/* {isActive ? (
                  <Badge variant="info" className="mt-2 normal-case tracking-normal">
                    Current step
                  </Badge>
                ) : null} */}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
