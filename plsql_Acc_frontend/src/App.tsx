import { useState } from "react"
import { BrainCircuit } from "lucide-react"

import { ConversionStepper } from "@/components/workflow/conversion-stepper"
import { StepPanels } from "@/components/workflow/step-panels"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { workflowSteps } from "@/data/converter-workflow"

function App() {
  const [activeStep, setActiveStep] = useState(1)

  const goPrevious = () => setActiveStep((current) => Math.max(1, current - 1))
  const goNext = () => setActiveStep((current) => Math.min(workflowSteps.length, current + 1))

  return (
    <div className="relative min-h-screen overflow-x-clip text-slate-900">
      <div className="pointer-events-none absolute -left-24 top-20 h-72 w-72 rounded-full bg-cyan-300/30 blur-3xl" />
      <div className="pointer-events-none absolute right-0 top-0 h-72 w-72 rounded-full bg-sky-300/20 blur-3xl" />
      <div className="pointer-events-none absolute inset-0 bg-grid-pattern opacity-40" />

      <div className="relative z-10 mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 pb-10 pt-6 md:px-6 lg:px-8">
        <header className="rounded-2xl border border-slate-200/80 bg-white/85 p-5 shadow-lg shadow-slate-200/40 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900 text-white shadow-md shadow-slate-900/20">
                <BrainCircuit className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xl font-bold text-slate-900">PL/SQL to Java Converter</p>
                <p className="text-sm text-slate-600">
                  Structured conversion workflow with guided next-next step execution.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant="info" className="normal-case tracking-normal">
                Wizard Mode
              </Badge>
              <Button variant="outline" size="sm">
                Docs
              </Button>
              {/* <Button size="sm">
                Run latest profile
                <ArrowRight className="h-4 w-4" />
              </Button> */}
            </div>
          </div>
        </header>

        <ConversionStepper steps={workflowSteps} activeStep={activeStep} onStepClick={setActiveStep} />
        <main>
          <StepPanels activeStep={activeStep} onPrevious={goPrevious} onNext={goNext} />
        </main>
      </div>
    </div>
  )
}

export default App
