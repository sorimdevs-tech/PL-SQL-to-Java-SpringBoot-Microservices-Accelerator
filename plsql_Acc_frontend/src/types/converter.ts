export interface WorkflowStep {
  id: number
  title: string
  subtitle: string
  helper: string
}

export interface SourceOption {
  label: string
  value: string
}

export interface TargetOption {
  label: string
  value: string
}

export interface DiscoveryObject {
  name: string
  type: "Package" | "Procedure" | "Function" | "Trigger" | "Table"
  selected?: boolean
}

export interface StrategyOption {
  title: string
  description: string
  recommendation?: boolean
}

export interface AssessmentProcedure {
  name: string
  complexity: "Low" | "Medium" | "High"
  dependencies: number
}

export interface JavaSpec {
  name: string
  value: string
}
