import type {
  AssessmentProcedure,
  DiscoveryObject,
  JavaSpec,
  SourceOption,
  StrategyOption,
  TargetOption,
  WorkflowStep,
} from "@/types/converter"

export const workflowSteps: WorkflowStep[] = [
  {
    id: 1,
    title: "Connect",
    subtitle: "Source & Target",
    helper: "Configure PL/SQL source and Spring Boot target options.",
  },
  {
    id: 2,
    title: "Discovery",
    subtitle: "Select Objects",
    helper: "Pick packages, procedures, and dependencies for conversion.",
  },
  {
    id: 3,
    title: "Strategy",
    subtitle: "Conversion Rules",
    helper: "Choose Spring project specs and run conversion.",
  },
  {
    id: 4,
    title: "Summary",
    subtitle: "Report & Output",
    helper: "Review project source, business logic strategy, DB details, and output paths.",
  },
]

export const sourceOptions: SourceOption[] = [
  { label: "Database Type", value: "Oracle 19c" },
  { label: "Schema", value: "FINANCE_CORE" },
  { label: "Connection Mode", value: "Read-only service account" },
]

export const targetOptions: TargetOption[] = [
  { label: "Java Version", value: "Java 21 LTS" },
  { label: "Framework", value: "Spring Boot 3.3" },
  { label: "Build Tool", value: "Maven" },
]

export const discoveryObjects: DiscoveryObject[] = [
  { name: "PKG_ACCOUNTING_CORE", type: "Package", selected: true },
  { name: "SP_VALIDATE_LEDGER", type: "Procedure", selected: true },
  { name: "SP_POST_JOURNAL", type: "Procedure", selected: true },
  { name: "FN_GET_FX_RATE", type: "Function", selected: false },
  { name: "TRG_AUDIT_ENTRIES", type: "Trigger", selected: false },
  { name: "ACCT_BALANCE", type: "Table", selected: true },
]

export const strategyOptions: StrategyOption[] = [
  {
    title: "Domain-first conversion",
    description: "Generate aggregate-centric service and repository layers.",
    recommendation: true,
  },
  {
    title: "Procedure wrapper mode",
    description: "Create one-to-one service wrappers for each stored procedure.",
  },
  {
    title: "Hybrid mode",
    description: "Use wrappers first, then progressively refactor to domain services.",
  },
]

export const assessmentProcedures: AssessmentProcedure[] = [
  { name: "SP_VALIDATE_LEDGER", complexity: "Medium", dependencies: 5 },
  { name: "SP_POST_JOURNAL", complexity: "High", dependencies: 9 },
  { name: "SP_RECONCILE_PERIOD", complexity: "High", dependencies: 7 },
  { name: "SP_CLOSE_MONTH", complexity: "Medium", dependencies: 6 },
]

export const javaSpecs: JavaSpec[] = [
  { name: "Packaging", value: "Layered (controller, service, repository)" },
  { name: "Error Handling", value: "Global @ControllerAdvice + typed exceptions" },
  { name: "Persistence", value: "Spring Data JPA + native query fallback" },
  { name: "API Style", value: "REST + OpenAPI annotations" },
]
