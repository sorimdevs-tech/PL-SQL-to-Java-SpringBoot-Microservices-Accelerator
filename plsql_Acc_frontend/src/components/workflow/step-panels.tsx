import { useEffect, useRef, useState, type ReactNode } from "react"
import {
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  FileCode2,
  Folder,
  GitBranch,
  LoaderCircle,
  RefreshCcw,
} from "lucide-react"

import { ConversionJobPanel, type ConversionSnapshot } from "@/components/workflow/conversion-job-panel"
import { OracleDiscovery } from "@/components/workflow/oracle-discovery"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { strategyOptions, workflowSteps } from "@/data/converter-workflow"
import { getJobDownloadUrl } from "@/lib/jobs-api"
import { testOracleConnection } from "@/lib/oracle-api"
import {
  analyzeGitSqlSource,
  analyzeUploadedSqlFile,
  getDependencySuggestions,
  getGitRepoTree,
  uploadSqlDiscoveryFile,
} from "@/lib/sql-discovery-api"
import { pickOutputDirectory } from "@/lib/jobs-api"
import type { OracleConnectionPayload } from "@/types/oracle-api"
import type {
  SqlBulkOperation,
  SqlBusinessRule,
  SqlCollectionVariable,
  SqlCursorPattern,
  SqlDataFlow,
  SqlDiscoveryAnalyzeResponse,
  SqlDiscoveryProcedure,
  SqlDiscoveryObject,
  SqlErrorHandling,
  SqlRetryLogic,
  SqlDiscoverySchema,
  SqlSchemaRelationship,
  SqlSchemaTable,
  SqlTransactionSummary,
} from "@/types/sql-discovery-api"

interface StepPanelsProps {
  activeStep: number
  onPrevious: () => void
  onNext: () => void
  onConversionFocusChange?: (focused: boolean) => void
  onStepAccessChange?: (maxStep: number) => void
}

type SourceMethod = "git" | "oracle" | "sqlfile"
type BuildTool = "mvn" | "gradle"
type SpringConfigFormat = "properties" | "yaml"
type PackagingType = "jar" | "war"

const DEFAULT_SPRING_DEPENDENCIES = [
  { id: "web", name: "Spring Web", description: "Build REST APIs with Spring MVC." },
  { id: "data-jpa", name: "Spring Data JPA", description: "Repository support and ORM integration." },
  { id: "validation", name: "Validation", description: "Jakarta Bean Validation annotations." },
  { id: "actuator", name: "Actuator", description: "Health checks and metrics endpoints." },
  { id: "lombok", name: "Lombok", description: "Boilerplate reduction for model and DTO classes." },
  { id: "oracle-driver", name: "Oracle Driver", description: "Oracle JDBC runtime driver support." },
]

type DependencyInsight = {
  id: string
  name: string
  reason: string
}

type SuggestedDependency = {
  name: string
  reason: string
  coordinate?: string
}

interface ConnectPanelProps {
  sourceMethod: SourceMethod
  setSourceMethod: (method: SourceMethod) => void
  gitRepoUrl: string
  setGitRepoUrl: (value: string) => void
  dbHost: string
  setDbHost: (value: string) => void
  dbPort: string
  setDbPort: (value: string) => void
  dbServiceName: string
  setDbServiceName: (value: string) => void
  dbUsername: string
  setDbUsername: (value: string) => void
  dbPassword: string
  setDbPassword: (value: string) => void
  dbConfigPath: string
  setDbConfigPath: (value: string) => void
  sourceFile: File | null
  setSourceFile: (file: File | null) => void
}

function ConnectPanel(props: ConnectPanelProps) {
  const [isTestingConnection, setIsTestingConnection] = useState(false)
  const [connectionInfo, setConnectionInfo] = useState<unknown | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  async function handleTestConnection() {
    const payload: OracleConnectionPayload = {
      host: props.dbHost.trim(),
      port: Number(props.dbPort),
      service_name: props.dbServiceName.trim(),
      username: props.dbUsername.trim(),
      password: props.dbPassword,
    }

    const hasValidPayload =
      !!payload.host &&
      !!payload.service_name &&
      !!payload.username &&
      !!payload.password &&
      Number.isFinite(payload.port)

    if (!hasValidPayload) {
      setConnectionError("Fill valid host, port, service name, username, and password first.")
      return
    }

    try {
      setIsTestingConnection(true)
      const response = await testOracleConnection(payload)
      setConnectionInfo(response)
      setConnectionError(null)
    } catch (requestError) {
      setConnectionError(requestError instanceof Error ? requestError.message : "Failed to test Oracle connection.")
    } finally {
      setIsTestingConnection(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Source Options</CardTitle>
        <CardDescription>Choose one extraction method for stored procedures</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-3">
          <button
            onClick={() => props.setSourceMethod("git")}
            className={`rounded-xl border p-3 text-left transition-all ${
              props.sourceMethod === "git"
                ? "border-cyan-300 bg-cyan-50"
                : "border-slate-200 bg-white hover:border-slate-300"
            }`}
          >
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <GitBranch className="h-4 w-4" />
              Git repo URL
            </p>
            <p className="mt-1 text-xs text-slate-500">Fetch stored procedures from repository path</p>
          </button>

          <button
            onClick={() => props.setSourceMethod("oracle")}
            className={`rounded-xl border p-3 text-left transition-all ${
              props.sourceMethod === "oracle"
                ? "border-cyan-300 bg-cyan-50"
                : "border-slate-200 bg-white hover:border-slate-300"
            }`}
          >
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Database className="h-4 w-4" />
              Extract from local Oracle DB
            </p>
            <p className="mt-1 text-xs text-slate-500">Use Oracle credentials for connection and browsing</p>
          </button>

          <button
            onClick={() => props.setSourceMethod("sqlfile")}
            className={`rounded-xl border p-3 text-left transition-all ${
              props.sourceMethod === "sqlfile"
                ? "border-cyan-300 bg-cyan-50"
                : "border-slate-200 bg-white hover:border-slate-300"
            }`}
          >
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <FileCode2 className="h-4 w-4" />
              Local SQL file path
            </p>
            <p className="mt-1 text-xs text-slate-500">Provide path to `.sql` file containing procedures</p>
          </button>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-4">
          {props.sourceMethod === "git" ? (
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Git repository URL</p>
              <Input
                placeholder="https://github.com/org/plsql-procedures.git"
                value={props.gitRepoUrl}
                onChange={(event) => props.setGitRepoUrl(event.target.value)}
              />
            </div>
          ) : null}

          {props.sourceMethod === "oracle" ? (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">DB Host</p>
                  <Input
                    placeholder="localhost"
                    value={props.dbHost}
                    onChange={(event) => props.setDbHost(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">DB Port</p>
                  <Input
                    placeholder="1521"
                    value={props.dbPort}
                    onChange={(event) => props.setDbPort(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Service Name</p>
                  <Input
                    placeholder="XEPDB1"
                    value={props.dbServiceName}
                    onChange={(event) => props.setDbServiceName(event.target.value)}
                  />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">DB Username</p>
                  <Input
                    placeholder="system"
                    value={props.dbUsername}
                    onChange={(event) => props.setDbUsername(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">DB Password</p>
                  <Input
                    type="password"
                    placeholder="Enter password"
                    value={props.dbPassword}
                    onChange={(event) => props.setDbPassword(event.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">Config Path</p>
                <Input
                  placeholder="config.json"
                  value={props.dbConfigPath}
                  onChange={(event) => props.setDbConfigPath(event.target.value)}
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" onClick={handleTestConnection} disabled={isTestingConnection}>
                  {isTestingConnection ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
                  Test Connection
                </Button>
              </div>

              {connectionError ? <p className="text-sm font-medium text-rose-600">{connectionError}</p> : null}

              {connectionInfo ? (
                <div className="rounded-xl border border-cyan-200 bg-cyan-50 p-3">
                  <p className="text-xs uppercase tracking-wide text-cyan-700">Connection Result</p>
                  <pre className="mt-2 overflow-auto text-xs text-cyan-900">{JSON.stringify(connectionInfo, null, 2)}</pre>
                </div>
              ) : null}
            </div>
          ) : null}

          {props.sourceMethod === "sqlfile" ? (
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Local SQL File</p>
              <Input
                type="file"
                accept=".sql,.pls,.pkb,.pks,.fnc,.prc"
                onChange={(event) => props.setSourceFile(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-slate-500">{props.sourceFile ? props.sourceFile.name : "No file selected"}</p>
              <p className="text-xs text-slate-500">
                Recommended: include schema DDL (tables, constraints, sequences) alongside procedures. You can upload
                multiple files or bundle them into a single `.sql` script for the most accurate entities.
              </p>
            </div>
          ) : null}
        </div>

        {/* <p className="text-xs text-slate-500">
          Spring project specifications are configured in <strong>Strategy - Step 2</strong>.
        </p> */}
      </CardContent>
    </Card>
  )
}

interface GlobalSchemaPanelProps {
  schema: SqlDiscoverySchema
  selectedTable: string | null
  onSelectTable: (tableName: string) => void
}

function GlobalSchemaPanel(props: GlobalSchemaPanelProps) {
  const globalTables = props.schema.tables ?? []
  const selectedSchemaTable = globalTables.find((table) => table.name === props.selectedTable) ?? null

  return (
    <Card>
      <CardHeader>
        <CardTitle>File-Level Global Schema Model</CardTitle>
        <CardDescription>
          Global pass across the full SQL file: all tables, foreign-key relationships, sequences, and sequence-to-table
          mappings.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-[220px_1fr_260px]">
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <p className="text-xs uppercase tracking-wide text-slate-500">Tables ({globalTables.length})</p>
          <div className="mt-2 space-y-1">
            {globalTables.map((table) => (
              <button
                key={table.name}
                onClick={() => props.onSelectTable(table.name)}
                className={`flex w-full min-w-0 items-center gap-2 rounded-lg px-2 py-1 text-left text-sm transition ${
                  props.selectedTable === table.name ? "bg-cyan-50 text-cyan-900" : "text-slate-700 hover:bg-slate-50"
                }`}
              >
                <span className="flex-1 truncate">{table.name}</span>
                <span className="w-8 shrink-0 text-right text-xs text-slate-400">{table.columns.length}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white">
            <div className="absolute inset-0 bg-grid-pattern opacity-30" />
            <div className="relative h-full min-h-[320px] overflow-auto p-6">
              {(() => {
                const relationships: SqlSchemaRelationship[] = props.schema.relationships ?? []
                const cardWidth = 220
                const cardHeight = 152
                const gapX = 80
                const gapY = 90
                const columns = 2
                const rows = Math.ceil(globalTables.length / columns)
                const width = columns * cardWidth + (columns - 1) * gapX + 40
                const height = rows * cardHeight + (rows - 1) * gapY + 40
                const positions = new Map<string, { x: number; y: number }>()

                globalTables.forEach((table, index) => {
                  const col = index % columns
                  const row = Math.floor(index / columns)
                  positions.set(table.name, {
                    x: 20 + col * (cardWidth + gapX),
                    y: 20 + row * (cardHeight + gapY),
                  })
                })

                return (
                  <div className="relative" style={{ width, height }}>
                    <svg className="absolute inset-0 h-full w-full">
                      <defs>
                        <marker
                          id="arrow"
                          viewBox="0 0 10 10"
                          refX="9"
                          refY="5"
                          markerWidth="6"
                          markerHeight="6"
                          orient="auto-start-reverse"
                        >
                          <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
                        </marker>
                      </defs>
                      {relationships.map((rel, idx) => {
                        const from = positions.get(rel.source_table)
                        const to = positions.get(rel.target_table)
                        if (!from || !to) {
                          return null
                        }
                        const startX = from.x + cardWidth
                        const startY = from.y + cardHeight / 2
                        const endX = to.x
                        const endY = to.y + cardHeight / 2
                        const midX = (startX + endX) / 2
                        return (
                          <path
                            key={`${rel.source_table}-${rel.target_table}-${idx}`}
                            d={`M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`}
                            stroke="#94a3b8"
                            strokeWidth="1.5"
                            fill="none"
                            markerEnd="url(#arrow)"
                          />
                        )
                      })}
                    </svg>

                    {globalTables.map((table) => {
                      const pos = positions.get(table.name)
                      if (!pos) {
                        return null
                      }
                      return (
                        <div
                          key={table.name}
                          className="absolute overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
                          style={{ width: cardWidth, height: cardHeight, left: pos.x, top: pos.y }}
                        >
                          <div className="rounded-t-xl border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700">
                            {table.name}
                          </div>
                          <div className="flex h-[108px] flex-col overflow-auto px-3 py-2 text-xs text-slate-600">
                            {table.columns.length > 0 ? (
                              <ul className="space-y-1">
                                {table.columns.slice(0, 5).map((col) => (
                                  <li key={`${table.name}-${col.name}`}>
                                    {col.name} <span className="text-slate-400">({col.type})</span>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-slate-400">No columns detected</p>
                            )}
                            {table.columns.length > 5 ? (
                              <p className="mt-1 text-[11px] text-slate-400">+{table.columns.length - 5} more</p>
                            ) : null}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )
              })()}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Sequences</p>
            {(props.schema.sequences ?? []).length > 0 ? (
              <div className="mt-2 space-y-2 text-sm text-slate-700">
                {(props.schema.sequences ?? []).map((sequence) => (
                  <div key={sequence.name} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="font-semibold">{sequence.name}</p>
                    <p className="text-xs text-slate-500">
                      {(props.schema.sequence_mapping ?? [])
                        .filter((mapping) => mapping.sequence_name === sequence.name)
                        .map((mapping) => mapping.mapped_table)
                        .join(", ") || "No table mapping detected"}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-400">No sequences detected</p>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <p className="text-xs uppercase tracking-wide text-slate-500">Table Properties</p>
          <div className="mt-3 space-y-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-800">
              {props.selectedTable ?? "Select a table"}
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Columns</p>
              <div className="mt-2 space-y-1 text-sm text-slate-700">
                {(selectedSchemaTable?.columns ?? []).map((col) => (
                  <p key={`${selectedSchemaTable?.name}-${col.name}`}>
                    {col.name} <span className="text-slate-400">({col.type})</span>
                  </p>
                ))}
                {props.selectedTable && (selectedSchemaTable?.columns.length ?? 0) === 0 ? (
                  <p className="text-sm text-slate-400">No columns detected</p>
                ) : null}
              </div>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Primary Keys</p>
              <div className="mt-2 space-y-1 text-sm text-slate-700">
                {(selectedSchemaTable?.primary_keys ?? []).length > 0 ? (
                  (selectedSchemaTable?.primary_keys ?? []).map((key) => <p key={key}>{key}</p>)
                ) : (
                  <p className="text-sm text-slate-400">No primary keys detected</p>
                )}
              </div>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Foreign Keys</p>
              <div className="mt-2 space-y-1 text-sm text-slate-700">
                {(selectedSchemaTable?.foreign_keys ?? []).length > 0 ? (
                  (selectedSchemaTable?.foreign_keys ?? []).map((rel, index) => (
                    <p key={`${rel.source_column}-${rel.target_table}-${index}`}>
                      {selectedSchemaTable?.name}.{rel.source_column} {"->"} {rel.target_table}.{rel.target_column}
                    </p>
                  ))
                ) : (
                  <p className="text-sm text-slate-400">No foreign keys detected</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

interface ProcedureBehaviorPanelProps {
  activeProcedure: SqlDiscoveryProcedure | null
  activeAnalysis: SqlDiscoveryAnalyzeResponse | SqlDiscoveryObject | null
}

interface CollapsibleInsightSectionProps {
  title: string
  description: string
  count?: number | string
  children: ReactNode
}

function CollapsibleInsightSection(props: CollapsibleInsightSectionProps) {
  return (
    <details className="group rounded-xl border border-slate-200 bg-white">
      <summary className="flex cursor-pointer list-none items-start justify-between gap-3 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-slate-800">{props.title}</p>
          <p className="mt-1 text-xs text-slate-500">{props.description}</p>
        </div>
        <div className="flex items-center gap-2">
          {props.count !== undefined ? (
            <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-500">
              {props.count}
            </span>
          ) : null}
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200 group-open:rotate-90" />
        </div>
      </summary>
      <div className="border-t border-slate-200 px-4 py-3">{props.children}</div>
    </details>
  )
}

function ProcedureBehaviorPanel(props: ProcedureBehaviorPanelProps) {
  if (!props.activeProcedure && !props.activeAnalysis?.procedureName) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Procedure-Level Behavior Model</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-500">No procedures detected in the analyzed SQL source.</p>
        </CardContent>
      </Card>
    )
  }

  const procedureRecord = props.activeProcedure as Record<string, unknown> | null
  const analysisRecord = props.activeAnalysis as Record<string, unknown> | null

  function readField<T>(snakeKey: string, camelKey: string, fallback: T): T {
    const procedureValue = procedureRecord?.[snakeKey]
    if (procedureValue !== undefined && procedureValue !== null) {
      return procedureValue as T
    }

    const camelValue = analysisRecord?.[camelKey]
    if (camelValue !== undefined && camelValue !== null) {
      return camelValue as T
    }

    const snakeValue = analysisRecord?.[snakeKey]
    if (snakeValue !== undefined && snakeValue !== null) {
      return snakeValue as T
    }

    return fallback
  }

  const parametersIn = props.activeProcedure?.input_parameters ?? props.activeAnalysis?.parameters?.in ?? []
  const parametersOut = props.activeProcedure?.output_parameters ?? props.activeAnalysis?.parameters?.out ?? []
  const tablesUsed = props.activeProcedure?.tables_used ?? props.activeAnalysis?.tablesUsed ?? []
  const operationsByTable = props.activeProcedure?.operations ?? props.activeAnalysis?.operationsByTable ?? {}
  const variables = props.activeProcedure?.variables ?? props.activeAnalysis?.localVariables ?? []
  const dataFlow = props.activeProcedure?.data_flow ?? props.activeAnalysis?.dataFlow ?? []
  const businessRules = props.activeProcedure?.business_rules ?? props.activeAnalysis?.businessRules ?? []
  const dependencies = props.activeProcedure?.dependencies ?? props.activeAnalysis?.dependencies ?? []
  const complexity = props.activeProcedure?.complexity ?? props.activeAnalysis?.complexity
  const exceptions = props.activeProcedure?.exceptions ?? props.activeAnalysis?.exceptions ?? []
  const sequenceUsage =
    props.activeProcedure?.dependency_graph?.sequences_used ??
    props.activeAnalysis?.dependencyGraph?.sequencesUsed ??
    ((analysisRecord?.dependency_graph as { sequences_used?: string[] } | undefined)?.sequences_used ?? [])
  const bulkOperations = readField<SqlBulkOperation[]>("bulk_operations", "bulkOperations", [])
  const cursor = readField<SqlCursorPattern | null>("cursor", "cursor", null)
  const transaction = readField<SqlTransactionSummary | null>("transaction", "transaction", null)
  const retryLogic = readField<SqlRetryLogic | null>("retry_logic", "retryLogic", null)
  const collections = readField<SqlCollectionVariable[]>("collections", "collections", [])
  const errorHandling = readField<SqlErrorHandling | null>("error_handling", "errorHandling", null)
  const performancePatterns = readField<string[]>("performance_patterns", "performancePatterns", [])

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Procedure-Level Behavior Model</CardTitle>
          <CardDescription>
            Per-procedure pass: parameters, local variables, CRUD operations, data flow, business rules, and cleaned
            dependencies.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-slate-500">Procedure Name</p>
            <p className="text-sm font-semibold text-slate-800">
              {props.activeProcedure?.name || props.activeAnalysis?.procedureName || "N/A"}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-slate-500">Object Type</p>
            <p className="text-sm font-semibold text-slate-800">
              {props.activeProcedure?.object_type || props.activeAnalysis?.objectType || "N/A"}
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Parameters</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">IN</p>
              {parametersIn.length > 0 ? (
                parametersIn.map((param) => (
                  <p key={`in-${param.name}`} className="text-slate-700">
                    {param.name} ({param.type})
                  </p>
                ))
              ) : (
                <p className="text-slate-500">No input parameters detected</p>
              )}
            </div>
            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">OUT</p>
              {parametersOut.length > 0 ? (
                parametersOut.map((param) => (
                  <p key={`out-${param.name}`} className="text-slate-700">
                    {param.name} ({param.type})
                  </p>
                ))
              ) : (
                <p className="text-slate-500">No output parameters detected</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tables Used</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {tablesUsed.length > 0 ? (
              <ul className="space-y-1 text-slate-700">
                {tablesUsed.map((tableName) => (
                  <li key={tableName}>{tableName}</li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">No tables detected</p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>CRUD Operations By Table</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {Object.entries(operationsByTable).length > 0 ? (
              <div className="space-y-2 text-slate-700">
                {Object.entries(operationsByTable).map(([tableName, operations]) => (
                  <div key={tableName} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="font-semibold">{tableName}</p>
                    <p>{operations.join(", ")}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500">No CRUD operations detected</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Local Variables</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {variables.length > 0 ? (
              <ul className="space-y-1 text-slate-700">
                {variables.map((variable) => (
                  <li key={variable.name}>
                    {variable.name} ({variable.type})
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">No variables detected</p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Data Flow</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {dataFlow.length > 0 ? (
              <div className="space-y-2 text-slate-700">
                {dataFlow.map((flow: SqlDataFlow, index: number) => (
                  <div key={`${flow.variable}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    {flow.variable} {"<-"} {flow.source}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500">No SELECT INTO data flow detected</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Business Rules</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {businessRules.length > 0 ? (
              <div className="space-y-2 text-slate-700">
                {businessRules.map((rule: SqlBusinessRule, index: number) => (
                  <div key={`${rule.condition}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="font-semibold">IF {rule.condition}</p>
                    <p>THEN {rule.true_action || "N/A"}</p>
                    {rule.false_action ? <p>ELSE {rule.false_action}</p> : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500">No conditional business logic detected</p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Dependencies</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Tables And Sequences</p>
              {dependencies.length > 0 ? (
                <ul className="space-y-1 text-slate-700">
                  {dependencies.map((dependency) => (
                    <li key={dependency}>{dependency}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-500">No dependencies detected</p>
              )}
            </div>
            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Sequence Usage</p>
              {sequenceUsage.length > 0 ? (
                <ul className="space-y-1 text-slate-700">
                  {sequenceUsage.map((sequenceName: string) => (
                    <li key={sequenceName}>{sequenceName}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-500">No sequence usage detected</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Complexity And Exceptions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="grid gap-2 md:grid-cols-2">
              <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                LOC: {complexity?.linesOfCode ?? 0}
              </p>
              <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                Queries: {complexity?.numberOfQueries ?? 0}
              </p>
              <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                Conditions: {complexity?.numberOfConditions ?? 0}
              </p>
              <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                Loops: {complexity?.numberOfLoops ?? 0}
              </p>
            </div>
            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Exceptions</p>
              {exceptions.length > 0 ? (
                <ul className="space-y-1 text-slate-700">
                  {exceptions.map((exceptionName: string) => (
                    <li key={exceptionName}>{exceptionName}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-500">No exceptions detected</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Advanced Execution Patterns</CardTitle>
          <CardDescription>
            Batch processing, cursor behavior, transaction semantics, retry flow, collections, and performance hints.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 lg:grid-cols-2">
          <CollapsibleInsightSection
            title="Bulk Operations"
            description="Batch reads and writes such as BULK COLLECT and FORALL."
            count={bulkOperations.length}
          >
            {bulkOperations.length > 0 ? (
              <div className="space-y-2 text-sm text-slate-700">
                {bulkOperations.map((operation, index) => {
                  const saveExceptions =
                    operation.save_exceptions ??
                    ((operation as SqlBulkOperation & { saveExceptions?: boolean }).saveExceptions ?? false)

                  return (
                    <div key={`${operation.type}-${operation.table ?? operation.target ?? index}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                      <p>
                        <span className="font-semibold">Type:</span> {operation.type}
                      </p>
                      <p>
                        <span className="font-semibold">Table:</span> {operation.table ?? operation.source ?? "N/A"}
                      </p>
                      <p>
                        <span className="font-semibold">Save Exceptions:</span> {saveExceptions ? "Yes" : "No"}
                      </p>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No bulk operations detected.</p>
            )}
          </CollapsibleInsightSection>

          <CollapsibleInsightSection
            title="Cursor"
            description="Explicit cursor locking and concurrency behavior."
            count={cursor ? 1 : 0}
          >
            {cursor ? (
              <div className="space-y-2 text-sm text-slate-700">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <p>
                    <span className="font-semibold">Type:</span> {cursor.type ?? "N/A"}
                  </p>
                  <p>
                    <span className="font-semibold">Locking:</span> {cursor.locking ?? "N/A"}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">No cursor behavior detected.</p>
            )}
          </CollapsibleInsightSection>

          <CollapsibleInsightSection
            title="Transaction"
            description="Transaction requirements, control flow features, and risk signals."
            count={transaction?.features?.length ?? (transaction ? 1 : 0)}
          >
            {transaction ? (
              <div className="space-y-2 text-sm text-slate-700">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <p>
                    <span className="font-semibold">Type:</span> {transaction.type ?? "N/A"}
                  </p>
                  <p>
                    <span className="font-semibold">Risk:</span> {transaction.risk ?? "N/A"}
                  </p>
                  <div className="mt-2">
                    <p className="font-semibold">Features</p>
                    {transaction.features && transaction.features.length > 0 ? (
                      <ul className="mt-1 space-y-1">
                        {transaction.features.map((feature) => (
                          <li key={feature}>{feature}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-slate-500">No transaction features detected.</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">No transaction behavior detected.</p>
            )}
          </CollapsibleInsightSection>

          <CollapsibleInsightSection
            title="Retry Logic"
            description="Retry behavior such as GOTO-based retry blocks or bounded attempts."
            count={retryLogic ? 1 : 0}
          >
            {retryLogic ? (
              <div className="space-y-2 text-sm text-slate-700">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <p>
                    <span className="font-semibold">Enabled:</span> {retryLogic.enabled ? "Yes" : "No"}
                  </p>
                  <p>
                    <span className="font-semibold">Max Attempts:</span>{" "}
                    {retryLogic.max_attempts ??
                      ((retryLogic as SqlRetryLogic & { maxAttempts?: number | null }).maxAttempts ?? "N/A")}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">No retry logic detected.</p>
            )}
          </CollapsibleInsightSection>

          <CollapsibleInsightSection
            title="Collections"
            description="Collection variables and their mapped source tables."
            count={collections.length}
          >
            {collections.length > 0 ? (
              <div className="space-y-2 text-sm text-slate-700">
                {collections.map((collection, index) => (
                  <div key={`${collection.name}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <p>
                      <span className="font-semibold">Name:</span> {collection.name}
                    </p>
                    <p>
                      <span className="font-semibold">Type:</span> {collection.type}
                    </p>
                    <p>
                      <span className="font-semibold">Source Table:</span>{" "}
                      {collection.source_table ??
                        ((collection as SqlCollectionVariable & { sourceTable?: string }).sourceTable ?? "N/A")}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No collection variables detected.</p>
            )}
          </CollapsibleInsightSection>

          <CollapsibleInsightSection
            title="Error Handling"
            description="Bulk or procedural error handling patterns surfaced by the analyzer."
            count={errorHandling ? 1 : 0}
          >
            {errorHandling ? (
              <div className="space-y-2 text-sm text-slate-700">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <p>
                    <span className="font-semibold">Type:</span> {errorHandling.type}
                  </p>
                  <p>
                    <span className="font-semibold">Mechanism:</span> {errorHandling.mechanism ?? "N/A"}
                  </p>
                  <p>
                    <span className="font-semibold">Behavior:</span> {errorHandling.behavior ?? "N/A"}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">No error handling pattern detected.</p>
            )}
          </CollapsibleInsightSection>

          <CollapsibleInsightSection
            title="Performance"
            description="Execution patterns that indicate throughput or context-switch reduction."
            count={performancePatterns.length}
          >
            {performancePatterns.length > 0 ? (
              <div className="space-y-2 text-sm text-slate-700">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <ul className="space-y-1">
                    {performancePatterns.map((pattern) => (
                      <li key={pattern}>{pattern}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">No performance patterns detected.</p>
            )}
          </CollapsibleInsightSection>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Conversion Preview</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-5">
          {[
            { label: "Entities", values: props.activeAnalysis?.conversionPreview?.entities ?? [] },
            { label: "Repositories", values: props.activeAnalysis?.conversionPreview?.repositories ?? [] },
            { label: "Services", values: props.activeAnalysis?.conversionPreview?.services ?? [] },
            { label: "Controllers", values: props.activeAnalysis?.conversionPreview?.controllers ?? [] },
            { label: "DTOs", values: props.activeAnalysis?.conversionPreview?.dtos ?? [] },
          ].map((item) => (
            <div key={item.label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">{item.label}</p>
              {item.values.length > 0 ? (
                <p className="text-slate-700">{item.values.join(", ")}</p>
              ) : (
                <p className="text-slate-500">No {item.label.toLowerCase()} detected</p>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </>
  )
}

interface DiscoveryPanelProps {
  sourceMethod: SourceMethod
  gitRepoUrl: string
  sourceFile: File | null
  dbHost: string
  dbPort: string
  dbServiceName: string
  dbUsername: string
  dbPassword: string
  availableDatabases: string[]
  setAvailableDatabases: (databases: string[]) => void
  selectedDatabases: string[]
  setSelectedDatabases: (databases: string[]) => void
  availableSchemas: string[]
  setAvailableSchemas: (schemas: string[]) => void
  selectedSchemas: string[]
  setSelectedSchemas: (schemas: string[]) => void
  availableObjects: string[]
  setAvailableObjects: (objects: string[]) => void
  selectedObjects: string[]
  setSelectedObjects: (objects: string[]) => void
  availableProcedures: string[]
  setAvailableProcedures: (procedures: string[]) => void
  selectedProcedures: string[]
  setSelectedProcedures: (procedures: string[]) => void
  setAnalyzedDependencies: (deps: DependencyInsight[]) => void
  setSuggestedDependencies: (deps: SuggestedDependency[]) => void
  onDiscoveryLoadingChange?: (value: boolean) => void
}

function SqlSourceDiscovery(props: {
  sourceMethod: SourceMethod
  gitRepoUrl: string
  sourceFile: File | null
  setAvailableObjects: (objects: string[]) => void
  setSelectedObjects: (objects: string[]) => void
  setAvailableProcedures: (procedures: string[]) => void
  setSelectedProcedures: (procedures: string[]) => void
  setAnalyzedDependencies: (deps: DependencyInsight[]) => void
  setSuggestedDependencies: (deps: SuggestedDependency[]) => void
  onLoadingChange?: (value: boolean) => void
}) {
  const [analysis, setAnalysis] = useState<SqlDiscoveryAnalyzeResponse | null>(null)
  const [selectedObjectKey, setSelectedObjectKey] = useState<string | null>(null)
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [gitStep, setGitStep] = useState<1 | 2>(1)
  const [gitPath, setGitPath] = useState("")
  const [gitEntries, setGitEntries] = useState<{ name: string; path: string; type: "dir" | "file" }[]>([])
  const [gitTreeError, setGitTreeError] = useState<string | null>(null)
  const [isLoadingTree, setIsLoadingTree] = useState(false)
  const requestIdRef = useRef(0)

  useEffect(() => {
    props.onLoadingChange?.(isLoading && (props.sourceMethod !== "git" || gitStep === 2))
  }, [gitStep, isLoading, props.onLoadingChange, props.sourceMethod])

  function deriveDependencies(value: SqlDiscoveryAnalyzeResponse): DependencyInsight[] {
    const dependencies: DependencyInsight[] = []
    const operations = (value.operations ?? []).map((op) => op.toUpperCase())
    const tables = value.tablesUsed ?? []
    const inParams = value.parameters?.in ?? []
    const outParams = value.parameters?.out ?? []

    if (tables.length > 0) {
      dependencies.push({
        id: "data-jpa",
        name: "Spring Data JPA",
        reason: "Tables detected in SQL statements; JPA repositories will be generated.",
      })
      dependencies.push({
        id: "oracle-driver",
        name: "Oracle Driver",
        reason: "SQL tables detected; JDBC driver is required for runtime access.",
      })
    }

    if (operations.length > 0) {
      dependencies.push({
        id: "web",
        name: "Spring Web",
        reason: "Operations detected; REST endpoints will be exposed for generated services.",
      })
    }

    if (inParams.length > 0 || outParams.length > 0) {
      dependencies.push({
        id: "validation",
        name: "Validation",
        reason: "Procedure parameters detected; request validation will be added.",
      })
    }

    if (value.exceptions && value.exceptions.length > 0) {
      dependencies.push({
        id: "actuator",
        name: "Actuator",
        reason: "Exception handling detected; health/monitoring endpoints recommended.",
      })
    }

    return dependencies
  }

  useEffect(() => {
    if (props.sourceMethod !== "sqlfile") {
      return
    }
    if (!props.sourceFile) {
      setAnalysis(null)
      props.setAnalyzedDependencies([])
      props.setSuggestedDependencies([])
      props.setAvailableObjects([])
      props.setSelectedObjects([])
      props.setAvailableProcedures([])
      props.setSelectedProcedures([])
      setError("Select a local SQL file in Connect step to preview tables.")
      return
    }

    let isCancelled = false
    const requestId = ++requestIdRef.current
    const selectedFile = props.sourceFile

    async function analyzeFile() {
      if (!selectedFile) {
        return
      }
      try {
        setIsLoading(true)
        const uploadResponse = await uploadSqlDiscoveryFile(selectedFile)
        if (requestIdRef.current !== requestId) {
          return
        }
        const analyzed = await analyzeUploadedSqlFile(uploadResponse.file_id)
        if (requestIdRef.current !== requestId) {
          return
        }

        props.setAnalyzedDependencies(deriveDependencies(analyzed))
        try {
          const suggestionResponse = await getDependencySuggestions({
            procedure_name: analyzed.procedureName,
            object_type: analyzed.objectType,
            tables_used: analyzed.tablesUsed,
            operations: analyzed.operations,
            parameters_in: analyzed.parameters?.in,
            parameters_out: analyzed.parameters?.out,
            local_variables: analyzed.localVariables,
            exceptions: analyzed.exceptions,
          })
          if (requestIdRef.current === requestId) {
            props.setSuggestedDependencies(suggestionResponse.suggestions ?? [])
          }
        } catch {
          if (requestIdRef.current === requestId) {
            props.setSuggestedDependencies([])
          }
        }
        const objectNames = (analyzed.objects ?? []).map(
          (item) => `${item.procedureName} (${item.objectType})`,
        )
        const procedureNames = (analyzed.objects ?? [])
          .filter((item) => item.objectType.toUpperCase() === "PROCEDURE")
          .map((item) => item.procedureName)

        if (!isCancelled) {
          setAnalysis(analyzed)
          const defaultObject =
            (analyzed.objects ?? []).find((item) => item.objectType.toUpperCase() === "PROCEDURE") ??
            (analyzed.objects ?? [])[0] ??
            analyzed
          setSelectedObjectKey(`${defaultObject.objectType}::${defaultObject.procedureName}`)
          props.setAvailableObjects(objectNames)
          props.setSelectedObjects(objectNames)
          props.setAvailableProcedures(procedureNames)
          props.setSelectedProcedures(procedureNames)
          setError(null)
        }
      } catch (requestError) {
        if (!isCancelled) {
          setAnalysis(null)
          props.setAnalyzedDependencies([])
          props.setSuggestedDependencies([])
          setError(requestError instanceof Error ? requestError.message : "Failed to analyze SQL file.")
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false)
        }
      }
    }

    void analyzeFile()

    return () => {
      isCancelled = true
    }
  }, [
    props.setAvailableObjects,
    props.setAvailableProcedures,
    props.setSelectedObjects,
    props.setSelectedProcedures,
    props.sourceFile,
    props.sourceMethod,
  ])

  const selectedObject: SqlDiscoveryObject | null =
    analysis?.objects?.find(
      (item) => `${item.objectType}::${item.procedureName}` === selectedObjectKey,
    ) ?? null
  const activeAnalysis: SqlDiscoveryAnalyzeResponse | SqlDiscoveryObject | null =
    selectedObject ?? analysis
  const globalSchema: SqlDiscoverySchema | null = analysis?.discovery?.schema ?? null
  const globalTables: SqlSchemaTable[] = globalSchema?.tables ?? []
  const activeProcedure: SqlDiscoveryProcedure | null =
    analysis?.discovery?.procedures?.find(
      (item) => `${item.object_type}::${item.name}` === selectedObjectKey,
    ) ??
    analysis?.discovery?.procedures?.[0] ??
    null

  useEffect(() => {
    const tables: SqlSchemaTable[] = globalTables
    if (!tables.length) {
      setSelectedTable(null)
      return
    }
    if (!selectedTable || !tables.some((table: SqlSchemaTable) => table.name === selectedTable)) {
      setSelectedTable(tables[0].name)
    }
  }, [globalTables, selectedTable])

  useEffect(() => {
    if (props.sourceMethod !== "git") {
      return
    }
    setAnalysis(null)
    setGitStep(1)
    setGitPath("")
    setGitEntries([])
    setGitTreeError(null)
    props.setAvailableObjects([])
    props.setSelectedObjects([])
    props.setAvailableProcedures([])
    props.setSelectedProcedures([])
    if (!props.gitRepoUrl.trim()) {
      setError("Provide a Git repository URL in Connect step to discover SQL tables.")
      props.setAnalyzedDependencies([])
      props.setSuggestedDependencies([])
      return
    }

    let isCancelled = false

    async function analyzeGitRepo() {
      try {
        const requestId = ++requestIdRef.current
        setIsLoading(true)
        const analyzed = await analyzeGitSqlSource(props.gitRepoUrl.trim())
        if (requestIdRef.current !== requestId) {
          return
        }
        props.setAnalyzedDependencies(deriveDependencies(analyzed))
        try {
          const suggestionResponse = await getDependencySuggestions({
            procedure_name: analyzed.procedureName,
            object_type: analyzed.objectType,
            tables_used: analyzed.tablesUsed,
            operations: analyzed.operations,
            parameters_in: analyzed.parameters?.in,
            parameters_out: analyzed.parameters?.out,
            local_variables: analyzed.localVariables,
            exceptions: analyzed.exceptions,
          })
          if (requestIdRef.current === requestId) {
            props.setSuggestedDependencies(suggestionResponse.suggestions ?? [])
          }
        } catch {
          if (requestIdRef.current === requestId) {
            props.setSuggestedDependencies([])
          }
        }
        const objectNames = (analyzed.objects ?? []).map(
          (item) => `${item.procedureName} (${item.objectType})`,
        )
        const procedureNames = (analyzed.objects ?? [])
          .filter((item) => item.objectType.toUpperCase() === "PROCEDURE")
          .map((item) => item.procedureName)
        if (!isCancelled) {
          setAnalysis(analyzed)
          const defaultObject =
            (analyzed.objects ?? []).find((item) => item.objectType.toUpperCase() === "PROCEDURE") ??
            (analyzed.objects ?? [])[0] ??
            analyzed
          setSelectedObjectKey(`${defaultObject.objectType}::${defaultObject.procedureName}`)
          props.setAvailableObjects(objectNames)
          props.setSelectedObjects(objectNames)
          props.setAvailableProcedures(procedureNames)
          props.setSelectedProcedures(procedureNames)
          setError(null)
        }
      } catch (requestError) {
        if (!isCancelled) {
          setAnalysis(null)
          props.setAnalyzedDependencies([])
          props.setSuggestedDependencies([])
          setError(requestError instanceof Error ? requestError.message : "Failed to analyze Git repository.")
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false)
        }
      }
    }

    void analyzeGitRepo()

    return () => {
      isCancelled = true
    }
  }, [
    props.gitRepoUrl,
    props.setAvailableObjects,
    props.setAvailableProcedures,
    props.setSelectedObjects,
    props.setSelectedProcedures,
    props.sourceMethod,
  ])

  useEffect(() => {
    if (props.sourceMethod !== "git") {
      return
    }
    if (!props.gitRepoUrl.trim()) {
      return
    }
    let isCancelled = false
    async function loadTree() {
      try {
        setIsLoadingTree(true)
        const response = await getGitRepoTree(props.gitRepoUrl.trim(), undefined, gitPath || undefined)
        if (isCancelled) {
          return
        }
        setGitEntries(response.entries)
        setGitTreeError(null)
      } catch (requestError) {
        if (!isCancelled) {
          setGitTreeError(requestError instanceof Error ? requestError.message : "Failed to load repository tree.")
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingTree(false)
        }
      }
    }
    void loadTree()
    return () => {
      isCancelled = true
    }
  }, [gitPath, props.gitRepoUrl, props.sourceMethod])

  return (
    <div className="space-y-4">
      {props.sourceMethod === "git" ? (
        <Card>
          <CardContent className="flex items-center justify-between gap-3 p-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Discovery Steps</p>
              <p className="text-sm font-semibold text-slate-900">Step {gitStep} of 2</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setGitStep(1)}
                className={`inline-flex h-9 w-9 items-center justify-center rounded-full border transition ${
                  gitStep === 1 ? "border-cyan-400 bg-cyan-50 text-cyan-700" : "border-slate-200 text-slate-600"
                }`}
                aria-label="Project structure"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setGitStep(2)}
                className={`inline-flex h-9 w-9 items-center justify-center rounded-full border transition ${
                  gitStep === 2 ? "border-cyan-400 bg-cyan-50 text-cyan-700" : "border-slate-200 text-slate-600"
                }`}
                aria-label="Schema explorer"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {props.sourceMethod === "git" && gitStep === 1 ? (
        <Card>
          <CardHeader>
            <CardTitle>Project Folder Structure</CardTitle>
            <CardDescription>Browse repository folders and files before discovery.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs uppercase tracking-wide text-slate-500">Path</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setGitPath(gitPath.split("/").slice(0, -1).join("/"))}
                disabled={!gitPath}
              >
                Up
              </Button>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-xs text-slate-500">{gitPath || "/"}</p>
              {gitTreeError ? <p className="mt-2 text-sm text-rose-600">{gitTreeError}</p> : null}
              {isLoadingTree ? (
                <p className="mt-3 inline-flex items-center gap-2 text-sm text-slate-600">
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                  Loading folders...
                </p>
              ) : (
                <div className="mt-3 space-y-1">
                  {gitEntries.map((entry) =>
                    entry.name !== ".git" ? (
                      <button
                        key={entry.path}
                        onClick={() => {
                          if (entry.type === "dir") {
                            setGitPath(entry.path)
                          }
                        }}
                        className="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left text-sm text-slate-700 transition hover:bg-slate-50"
                      >
                        {entry.type === "dir" ? (
                          <Folder className="h-4 w-4 text-cyan-600" />
                        ) : (
                          <FileCode2 className="h-4 w-4 text-slate-400" />
                        )}
                        <span>{entry.name}</span>
                      </button>
                    ) : null,
                  )}
                  {gitEntries.length === 0 ? <p className="text-sm text-slate-500">No files found.</p> : null}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {isLoading && (props.sourceMethod !== "git" || gitStep === 2) ? (
        <Card>
          <CardContent className="p-4">
            <p className="inline-flex items-center gap-2 text-sm text-slate-600">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              Analyzing SQL file...
            </p>
          </CardContent>
        </Card>
      ) : null}

      {error && (props.sourceMethod !== "git" || gitStep === 2) ? (
        <Card>
          <CardContent className="p-4">
            <p className="text-sm font-medium text-rose-700">{error}</p>
          </CardContent>
        </Card>
      ) : null}

      {analysis && (props.sourceMethod !== "git" || gitStep === 2) ? (
        <>
          {(analysis?.objects ?? []).length > 1 ? (
            <Card>
              <CardHeader>
                <CardTitle>Active Object</CardTitle>
                <CardDescription>Select which procedure/function drives the schema view.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center gap-3">
                  <label className="text-xs uppercase tracking-wide text-slate-500">Object</label>
                  <select
                    className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 shadow-sm"
                    value={selectedObjectKey ?? ""}
                    onChange={(event) => setSelectedObjectKey(event.target.value)}
                  >
                    {(analysis?.objects ?? []).map((item) => {
                      const key = `${item.objectType}::${item.procedureName}`
                      return (
                        <option key={key} value={key}>
                          {item.procedureName} ({item.objectType})
                        </option>
                      )
                    })}
                  </select>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {globalSchema ? (
            <GlobalSchemaPanel
              schema={globalSchema}
              selectedTable={selectedTable}
              onSelectTable={(tableName) => setSelectedTable(tableName)}
            />
          ) : null}

          <ProcedureBehaviorPanel activeProcedure={activeProcedure} activeAnalysis={activeAnalysis} />

          <Card>
            <CardHeader>
              <CardTitle>Objects</CardTitle>
            </CardHeader>
            <CardContent>
              {(analysis?.objects ?? []).length > 0 ? (
                <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="px-3 py-2 text-left font-semibold">Procedure</th>
                        <th className="px-3 py-2 text-left font-semibold">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(analysis?.objects ?? []).map((item) => (
                        <tr key={`${item.objectType}-${item.procedureName}`} className="border-t border-slate-100">
                          <td className="px-3 py-2 font-medium text-slate-800">{item.procedureName}</td>
                          <td className="px-3 py-2 text-slate-700">{item.objectType}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-slate-500">No objects detected</p>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  )
}

function DiscoveryPanel(props: DiscoveryPanelProps) {
  if (props.sourceMethod === "git" || props.sourceMethod === "sqlfile") {
    return (
      <SqlSourceDiscovery
        sourceMethod={props.sourceMethod}
        gitRepoUrl={props.gitRepoUrl}
        sourceFile={props.sourceFile}
        setAvailableObjects={props.setAvailableObjects}
        setSelectedObjects={props.setSelectedObjects}
        setAvailableProcedures={props.setAvailableProcedures}
        setSelectedProcedures={props.setSelectedProcedures}
        setAnalyzedDependencies={props.setAnalyzedDependencies}
        setSuggestedDependencies={props.setSuggestedDependencies}
        onLoadingChange={props.onDiscoveryLoadingChange}
      />
    )
  }

  if (props.sourceMethod !== "oracle") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Discovery</CardTitle>
          <CardDescription>Oracle browsing is available only for Oracle source mode</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-600">
            Switch to <strong>Extract from local Oracle DB</strong> in Connect step to browse databases, schemas,
            and available PL/SQL objects.
          </p>
          <br />
          <p className="text-sm text-slate-600">
            For Git and Local File source methods, the discovery step should be skipped since the scope is determined by repository path or selected file.
          </p>
        </CardContent>
      </Card>
    )
  }

    return (
      <OracleDiscovery
      host={props.dbHost}
      port={props.dbPort}
      serviceName={props.dbServiceName}
      username={props.dbUsername}
      password={props.dbPassword}
      availableDatabases={props.availableDatabases}
      setAvailableDatabases={props.setAvailableDatabases}
      selectedDatabases={props.selectedDatabases}
      setSelectedDatabases={props.setSelectedDatabases}
      availableSchemas={props.availableSchemas}
      setAvailableSchemas={props.setAvailableSchemas}
      selectedSchemas={props.selectedSchemas}
      setSelectedSchemas={props.setSelectedSchemas}
      availableObjects={props.availableObjects}
      setAvailableObjects={props.setAvailableObjects}
      selectedObjects={props.selectedObjects}
      setSelectedObjects={props.setSelectedObjects}
      availableProcedures={props.availableProcedures}
      setAvailableProcedures={props.setAvailableProcedures}
        selectedProcedures={props.selectedProcedures}
        setSelectedProcedures={props.setSelectedProcedures}
        setAnalyzedDependencies={props.setAnalyzedDependencies}
        setSuggestedDependencies={props.setSuggestedDependencies}
      />
    )
  }

interface StrategyPanelProps {
  springBootVersion: string
  setSpringBootVersion: (value: string) => void
  javaVersion: string
  setJavaVersion: (value: string) => void
  buildTool: BuildTool
  setBuildTool: (tool: BuildTool) => void
  packaging: PackagingType
  setPackaging: (value: PackagingType) => void
  springConfigFormat: SpringConfigFormat
  setSpringConfigFormat: (format: SpringConfigFormat) => void
  projectGroup: string
  setProjectGroup: (value: string) => void
  projectArtifact: string
  setProjectArtifact: (value: string) => void
  projectDisplayName: string
  setProjectDisplayName: (value: string) => void
  projectDescription: string
  setProjectDescription: (value: string) => void
  projectPackageName: string
  setProjectPackageName: (value: string) => void
  outputDirectory: string
  setOutputDirectory: (value: string) => void
  analyzedDependencies: DependencyInsight[]
  suggestedDependencies: SuggestedDependency[]
  selectedOptionalDependencies: string[]
  setSelectedOptionalDependencies: (deps: string[]) => void
}

function StrategyPanel(props: StrategyPanelProps) {
  const [language, setLanguage] = useState<"java" | "kotlin" | "groovy">("java")
  const [gradleFlavor, setGradleFlavor] = useState<"groovy" | "kotlin">("groovy")
  const [isPickingDir, setIsPickingDir] = useState(false)
  const [pickDirError, setPickDirError] = useState<string | null>(null)

  function resolveSuggestedId(name: string): string | null {
    const normalized = name.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()
    if (!normalized) {
      return null
    }
    if (normalized.includes("lombok")) return "lombok"
    if (normalized.includes("security")) return "spring-boot-starter-security"
    if (normalized.includes("cache")) return "spring-boot-starter-cache"
    if (normalized.includes("batch")) return "spring-boot-starter-batch"
    if (normalized.includes("mail")) return "spring-boot-starter-mail"
    if (normalized.includes("webflux")) return "spring-boot-starter-webflux"
    if (normalized.includes("redis")) return "spring-boot-starter-data-redis"
    if (normalized.includes("mongo")) return "spring-boot-starter-data-mongodb"
    if (normalized.includes("amqp") || normalized.includes("rabbit")) return "spring-boot-starter-amqp"
    if (normalized.includes("quartz") || normalized.includes("scheduler")) return "spring-boot-starter-quartz"
    if (normalized.includes("actuator")) return "spring-boot-starter-actuator"
    if (normalized.includes("validation")) return "spring-boot-starter-validation"
    if (normalized.includes("data jpa") || normalized.includes("jpa")) return "spring-boot-starter-data-jpa"
    if (normalized.includes("web")) return "spring-boot-starter-web"
    return null
  }

  const optionalSet = new Set(props.selectedOptionalDependencies)
  const labelById = new Map(
    props.suggestedDependencies
      .map((dep) => {
        const resolved = dep.coordinate ?? resolveSuggestedId(dep.name)
        return resolved ? ([resolved, dep.name] as const) : null
      })
      .filter((item): item is readonly [string, string] => item !== null),
  )

  function addOptionalDependency(id: string) {
    if (optionalSet.has(id)) {
      return
    }
    props.setSelectedOptionalDependencies([...props.selectedOptionalDependencies, id])
  }

  function removeOptionalDependency(id: string) {
    props.setSelectedOptionalDependencies(props.selectedOptionalDependencies.filter((dep) => dep !== id))
  }

  async function handlePickDirectory() {
    try {
      setIsPickingDir(true)
      setPickDirError(null)
      const selected = await pickOutputDirectory()
      if (selected) {
        props.setOutputDirectory(selected)
      }
    } catch (error) {
      setPickDirError(error instanceof Error ? error.message : "Failed to open folder picker.")
    } finally {
      setIsPickingDir(false)
    }
  }

  return (
    <Card className="rounded-md border border-slate-200 bg-white shadow-none">
      <CardContent className="grid gap-6 px-6 pb-6 pt-6 lg:grid-cols-[1.2fr_1fr]">
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-3">
              <p className="text-sm font-semibold text-slate-900">Project</p>
              <div className="space-y-2 text-sm text-slate-800">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="build-tool"
                    checked={props.buildTool === "gradle" && gradleFlavor === "groovy"}
                    onChange={() => {
                      setGradleFlavor("groovy")
                      props.setBuildTool("gradle")
                    }}
                    className="h-4 w-4 accent-green-500"
                  />
                  Gradle - Groovy
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="build-tool"
                    checked={props.buildTool === "gradle" && gradleFlavor === "kotlin"}
                    onChange={() => {
                      setGradleFlavor("kotlin")
                      props.setBuildTool("gradle")
                    }}
                    className="h-4 w-4 accent-green-500"
                  />
                  Gradle - Kotlin
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="build-tool"
                    checked={props.buildTool === "mvn"}
                    onChange={() => props.setBuildTool("mvn")}
                    className="h-4 w-4 accent-green-500"
                  />
                  Maven
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-sm font-semibold text-slate-900">Language</p>
              <div className="space-y-2 text-sm text-slate-800">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="language"
                    checked={language === "java"}
                    onChange={() => setLanguage("java")}
                    className="h-4 w-4 accent-green-500"
                  />
                  Java
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="language"
                    checked={language === "kotlin"}
                    onChange={() => setLanguage("kotlin")}
                    className="h-4 w-4 accent-green-500"
                  />
                  Kotlin
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="language"
                    checked={language === "groovy"}
                    onChange={() => setLanguage("groovy")}
                    className="h-4 w-4 accent-green-500"
                  />
                  Groovy
                </label>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-semibold text-slate-900">Spring Boot</p>
            <div className="grid gap-2 text-sm text-slate-800 md:grid-cols-3">
              {[
                { value: "4.1.0-SNAPSHOT", label: "4.1.0 (SNAPSHOT)" },
                { value: "4.1.0-M2", label: "4.1.0 (M2)" },
                { value: "4.0.4-SNAPSHOT", label: "4.0.4 (SNAPSHOT)" },
                { value: "4.0.3", label: "4.0.3" },
                { value: "3.5.12-SNAPSHOT", label: "3.5.12 (SNAPSHOT)" },
                { value: "3.5.11", label: "3.5.11" },
              ].map((option) => (
                <label key={option.value} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="spring-boot"
                    checked={props.springBootVersion === option.value}
                    onChange={() => props.setSpringBootVersion(option.value)}
                    className="h-4 w-4 accent-green-500"
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-semibold text-slate-900">Project Metadata</p>
            <div className="grid gap-4">
              {[
                { label: "Group", value: props.projectGroup, onChange: props.setProjectGroup },
                { label: "Artifact", value: props.projectArtifact, onChange: props.setProjectArtifact },
                { label: "Name", value: props.projectDisplayName, onChange: props.setProjectDisplayName },
                { label: "Description", value: props.projectDescription, onChange: props.setProjectDescription },
                { label: "Package name", value: props.projectPackageName, onChange: props.setProjectPackageName },
              ].map((field) => (
                <div key={field.label} className="grid items-center gap-3 md:grid-cols-[140px_1fr]">
                  <p className="text-sm text-slate-700">{field.label}</p>
                  <input
                    value={field.value}
                    onChange={(event) => field.onChange(event.target.value)}
                    className="h-9 w-full border-b border-slate-400 bg-transparent text-sm text-slate-900 outline-none focus:border-green-500"
                  />
                </div>
              ))}
              <div className="grid items-center gap-3 md:grid-cols-[140px_1fr]">
                <p className="text-sm text-slate-700">Output directory</p>
                <div className="flex items-center gap-3">
                  <input
                    value={props.outputDirectory}
                    onChange={(event) => props.setOutputDirectory(event.target.value)}
                    placeholder="C:\\projects\\output\\converted-app"
                    className="h-9 w-full border-b border-slate-400 bg-transparent text-sm text-slate-900 outline-none focus:border-green-500"
                  />
                  <button
                    type="button"
                    onClick={handlePickDirectory}
                    disabled={isPickingDir}
                    className="inline-flex h-9 items-center justify-center rounded-full border border-slate-200 px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isPickingDir ? "Picking..." : "Choose"}
                  </button>
                </div>
                {pickDirError ? <p className="text-xs text-rose-600">{pickDirError}</p> : null}
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <p className="text-sm font-semibold text-slate-900">Packaging</p>
              <div className="flex items-center gap-6 text-sm text-slate-800">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="packaging"
                    checked={props.packaging === "jar"}
                    onChange={() => props.setPackaging("jar")}
                    className="h-4 w-4 accent-green-500"
                  />
                  Jar
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="packaging"
                    checked={props.packaging === "war"}
                    onChange={() => props.setPackaging("war")}
                    className="h-4 w-4 accent-green-500"
                  />
                  War
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-semibold text-slate-900">Configuration</p>
              <div className="flex items-center gap-6 text-sm text-slate-800">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="config"
                    checked={props.springConfigFormat === "properties"}
                    onChange={() => props.setSpringConfigFormat("properties")}
                    className="h-4 w-4 accent-green-500"
                  />
                  Properties
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="config"
                    checked={props.springConfigFormat === "yaml"}
                    onChange={() => props.setSpringConfigFormat("yaml")}
                    className="h-4 w-4 accent-green-500"
                  />
                  YAML
                </label>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-900">Java</p>
            <div className="flex flex-wrap items-center gap-6 text-sm text-slate-800">
              {["25", "21", "17"].map((version) => (
                <label key={version} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="java-version"
                    checked={props.javaVersion === version}
                    onChange={() => props.setJavaVersion(version)}
                    className="h-4 w-4 accent-green-500"
                  />
                  {version}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-md border border-slate-200/80 bg-white p-4">
          <div className="flex items-center justify-between border-b border-slate-200/70 pb-3">
            <p className="text-sm font-semibold text-slate-900">Dependencies</p>
            <button
              type="button"
              className="rounded border border-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-900"
            >
              Add dependencies... <span className="ml-2 text-[11px] font-semibold">CTRL + B</span>
            </button>
          </div>
          {props.analyzedDependencies.length > 0 ? (
            <div className="mt-4 space-y-3 text-sm text-slate-700">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Required</p>
              {props.analyzedDependencies.map((dependency) => (
                <div key={dependency.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <p className="font-semibold text-slate-900">{dependency.name}</p>
                  <p className="text-xs text-slate-500">{dependency.reason}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-500">No dependencies inferred yet.</p>
          )}
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Suggested (LLM)</p>
            {props.suggestedDependencies.length > 0 ? (
              props.suggestedDependencies.map((dependency) => {
                const resolvedId = dependency.coordinate ?? resolveSuggestedId(dependency.name)
                const isAdded = resolvedId ? optionalSet.has(resolvedId) : false
                return (
                  <div key={dependency.name} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">{dependency.name}</p>
                        <p className="text-xs text-slate-500">{dependency.reason}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => resolvedId && addOptionalDependency(resolvedId)}
                        disabled={!resolvedId || isAdded}
                        className={`rounded px-3 py-1 text-xs font-semibold ${
                          isAdded
                            ? "bg-slate-100 text-slate-500"
                            : resolvedId
                              ? "bg-cyan-600 text-white"
                              : "bg-slate-200 text-slate-400"
                        }`}
                      >
                        {isAdded ? "Added" : resolvedId ? "Add" : "Unavailable"}
                      </button>
                    </div>
                  </div>
                )
              })
            ) : (
              <p className="text-xs text-slate-500">
                No LLM suggestions available yet. Run discovery with the backend online and an LLM configured to see recommendations.
              </p>
            )}
          </div>
          {props.selectedOptionalDependencies.length > 0 ? (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Included (Optional)</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {props.selectedOptionalDependencies.map((dep) => (
                  <button
                    key={dep}
                    type="button"
                    onClick={() => removeOptionalDependency(dep)}
                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700"
                  >
                    {labelById.get(dep) ?? dep}
                    <span className="text-slate-400">×</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          <p className="mt-6 text-xs text-slate-400">
            {DEFAULT_SPRING_DEPENDENCIES.length} baseline dependencies remain available for generation.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

interface SummaryPanelProps {
  projectName: string
  sourceMethod: SourceMethod
  gitRepoUrl: string
  sourceFileName: string
  dbHost: string
  dbPort: string
  dbServiceName: string
  selectedDatabases: string[]
  selectedSchemas: string[]
  selectedObjects: string[]
  selectedProcedures: string[]
  selectedStrategy: string
  javaVersion: string
  buildTool: BuildTool
  springConfigFormat: SpringConfigFormat
  conversionSnapshot: ConversionSnapshot | null
  backendLogs: string[]
  backendLogsStatus: string | null
}

function SummaryPanel(props: SummaryPanelProps) {
  function formatDuration(ms: number | null | undefined): string {
    if (!Number.isFinite(ms) || ms === null || ms === undefined) {
      return "Not available"
    }
    const totalSeconds = Math.floor(ms / 1000)
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60
    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`
    }
    if (minutes > 0) {
      return `${minutes}m ${seconds}s`
    }
    return `${seconds}s`
  }

  const [filesOpen, setFilesOpen] = useState(false)
  const filesBodyRef = useRef<HTMLDivElement | null>(null)
  const [filesBodyHeight, setFilesBodyHeight] = useState("0px")
  const hasDownload = props.conversionSnapshot?.jobId && props.conversionSnapshot?.status === "completed"
  const sourceLabel =
    props.sourceMethod === "oracle"
      ? `Oracle DB (${props.dbServiceName})`
      : props.sourceMethod === "git"
        ? `Git repository (${props.gitRepoUrl || "Not provided"})`
        : `Local file (${props.sourceFileName || "Not selected"})`
  const isOracleSource = props.sourceMethod === "oracle"
  const sourceDetailsTitle = isOracleSource ? "DB & Output Details" : "Source & Output Details"
  const sourceDetailsDescription = isOracleSource
    ? "Database context and generated project paths"
    : "Source context and generated project paths"
  const sourceTypeLabel =
    props.sourceMethod === "git"
      ? "Git repository"
      : props.sourceMethod === "sqlfile"
        ? "Local SQL file"
        : "Oracle database"
  const sourceLocationLabel =
    props.sourceMethod === "git"
      ? props.gitRepoUrl || "Not provided"
      : props.sourceMethod === "sqlfile"
        ? props.sourceFileName || "Not selected"
        : `${props.dbHost}:${props.dbPort}/${props.dbServiceName}`
  const normalizedProcedures = props.selectedProcedures.map((name) => name.toLowerCase())
  const dominantDomains = []
  if (normalizedProcedures.some((name) => name.includes("validate") || name.includes("check"))) {
    dominantDomains.push("Validation")
  }
  if (normalizedProcedures.some((name) => name.includes("post") || name.includes("journal"))) {
    dominantDomains.push("Posting")
  }
  if (normalizedProcedures.some((name) => name.includes("reconcile") || name.includes("match"))) {
    dominantDomains.push("Reconciliation")
  }
  if (normalizedProcedures.some((name) => name.includes("close") || name.includes("period"))) {
    dominantDomains.push("Period Close")
  }
  if (dominantDomains.length === 0 && props.selectedProcedures.length > 0) {
    dominantDomains.push("General PL/SQL Logic")
  }
  const defaultDependencyNames = DEFAULT_SPRING_DEPENDENCIES.map((dependency) => dependency.name)
  const backendSummary = props.conversionSnapshot?.backendSummaryData as
    | {
        plsql_files?: number
        procedures?: number
        functions?: number
        triggers?: number
        packages?: number
        tables_detected?: number
        java_files_generated?: number
        entities_generated?: number
        repositories_generated?: number
        services_generated?: number
        controllers_generated?: number
        unit_tests_generated?: number
        integration_tests_generated?: number
        validation_results?: number
        validation_passed?: boolean
      }
    | undefined
  const resolvedSummary = backendSummary
    ? `This conversion used ${backendSummary.plsql_files ?? 0} PL/SQL file(s) from ${sourceLabel} and produced ${
        backendSummary.java_files_generated ?? 0
      } Java source file(s). The parsed scope included ${backendSummary.procedures ?? 0} procedures, ${
        backendSummary.functions ?? 0
      } functions, ${backendSummary.triggers ?? 0} triggers, and ${backendSummary.packages ?? 0} packages, with ${
        backendSummary.tables_detected ?? 0
      } table(s) detected.

Generated outputs include ${backendSummary.entities_generated ?? 0} entities, ${
        backendSummary.repositories_generated ?? 0
      } repositories, ${backendSummary.services_generated ?? 0} services, and ${
        backendSummary.controllers_generated ?? 0
      } controllers. Tests generated: ${backendSummary.unit_tests_generated ?? 0} unit and ${
        backendSummary.integration_tests_generated ?? 0
      } integration tests. Validation ${
        backendSummary.validation_passed ? "passed" : "did not pass"
      } with ${backendSummary.validation_results ?? 0} result(s).

Target runtime is Java ${props.javaVersion} using ${props.buildTool}, configuration in ${
        props.springConfigFormat === "properties" ? "application.properties" : "application.yml"
      }, baseline dependencies: ${defaultDependencyNames.join(", ")}. Output directory: ${
        props.conversionSnapshot?.outputDirectory ?? "not available"
      }.`
    : "Run a conversion to generate a real summary from the backend."

  useEffect(() => {
    if (!filesBodyRef.current) {
      return
    }
    if (filesOpen) {
      setFilesBodyHeight(`${filesBodyRef.current.scrollHeight}px`)
    } else {
      setFilesBodyHeight("0px")
    }
  }, [filesOpen, props.conversionSnapshot?.generatedFiles?.length])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>Project Narrative Summary</CardTitle>
            {hasDownload ? (
              <a
                href={getJobDownloadUrl(props.conversionSnapshot?.jobId ?? "")}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-emerald-500 px-4 text-sm font-semibold text-white! shadow-md shadow-emerald-500/30 transition-all duration-200 hover:-translate-y-0.5 hover:bg-emerald-600"
              >
                <Download className="h-4 w-4 text-white" />
                Download ZIP
              </a>
            ) : null}
          </div>
          <CardDescription>
            {backendSummary ? "From backend conversion summary" : "Waiting for conversion summary"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-line text-sm leading-6 text-slate-700">{resolvedSummary}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Business Logic Summary</CardTitle>
          <CardDescription>Functional interpretation of selected PL/SQL scope</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl text-center border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Selected Logic Units</p>
            <p className="text-sm font-semibold text-slate-900">{props.selectedProcedures.length} procedures</p>
          </div>
          <div className="rounded-xl text-center border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Primary Logic Domains</p>
            <p className="text-sm font-semibold text-slate-900">
              {dominantDomains.length > 0 ? dominantDomains.join(", ") : "Not inferred yet"}
            </p>
          </div>
          <div className="rounded-xl border text-center border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Conversion Time</p>
            <p className="text-sm font-semibold text-slate-900">{formatDuration(props.conversionSnapshot?.conversionDurationMs)}</p>
          </div>
          <div className="rounded-xl text-center border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Target Runtime</p>
            <p className="text-sm font-semibold text-slate-900">
              Java {props.javaVersion} with {props.buildTool}
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Project Summary</CardTitle>
          <CardDescription>How this conversion project is configured</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Project Name</p>
            <p className="text-sm font-semibold text-slate-900">{props.projectName}</p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Project Source</p>
            <p className="text-sm font-semibold text-slate-900">{sourceLabel}</p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Conversion Time</p>
            <p className="text-sm font-semibold text-slate-900">
              {formatDuration(props.conversionSnapshot?.conversionDurationMs)}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Business Logic Strategy</p>
            <p className="text-sm font-semibold text-slate-900">{props.selectedStrategy}</p>
            <p className="mt-1 text-xs text-slate-600">
              {props.selectedProcedures.length} stored procedures selected across {props.selectedSchemas.length} schema(s).
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{sourceDetailsTitle}</CardTitle>
          <CardDescription>{sourceDetailsDescription}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isOracleSource ? (
            <>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">DB Connection</p>
                <p className="text-sm font-semibold text-slate-800">
                  {props.dbHost}:{props.dbPort}/{props.dbServiceName}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Databases in Scope</p>
                <p className="text-sm font-semibold text-slate-800">
                  {props.selectedDatabases.length > 0 ? props.selectedDatabases.join(", ") : "No database selected"}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Schemas in Scope</p>
                <p className="text-sm font-semibold text-slate-800">
                  {props.selectedSchemas.length > 0 ? props.selectedSchemas.join(", ") : "No schema selected"}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Objects in Scope</p>
                <p className="text-sm font-semibold text-slate-800">
                  {props.selectedObjects.length > 0 ? `${props.selectedObjects.length} selected` : "No objects selected"}
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Source Type</p>
                <p className="text-sm font-semibold text-slate-800">{sourceTypeLabel}</p>
              </div>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Source Location</p>
                <p className="text-sm font-semibold text-slate-800">{sourceLocationLabel}</p>
              </div>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Objects in Scope</p>
                <p className="text-sm font-semibold text-slate-800">
                  {props.selectedObjects.length > 0 ? `${props.selectedObjects.length} selected` : "No objects selected"}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Procedures in Scope</p>
                <p className="text-sm font-semibold text-slate-800">
                  {props.selectedProcedures.length > 0
                    ? `${props.selectedProcedures.length} selected`
                    : "No procedures selected"}
                </p>
              </div>
            </>
          )}
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Java Version</p>
            <p className="text-sm font-semibold text-slate-800">{props.javaVersion}</p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Build Tool</p>
            <p className="text-sm font-semibold text-slate-800">{props.buildTool}</p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Spring Config</p>
            <p className="text-sm font-semibold text-slate-800">
              {props.springConfigFormat === "properties" ? "application.properties" : "application.yml"}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Dependencies</p>
            <p className="text-sm font-semibold break-words text-slate-800">
              {defaultDependencyNames.join(", ")}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Output Directory</p>
            <p className="text-sm font-semibold break-words text-slate-800">
              {props.conversionSnapshot?.outputDirectory ?? "Run conversion to get output path"}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Generated File Paths</p>
            {props.conversionSnapshot?.generatedFiles?.length ? (
              <ul className="mt-1 space-y-1 text-xs text-slate-700">
                {props.conversionSnapshot.generatedFiles.slice(0, 8).map((path) => (
                  <li key={path}>{path}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm font-semibold text-slate-800">No generated files yet</p>
            )}
          </div>
        </CardContent>
      </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Generated Files</CardTitle>
          <CardDescription>Full list of files created by the conversion</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <button
            type="button"
            onClick={() => setFilesOpen((current) => !current)}
            aria-expanded={filesOpen}
            className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm font-semibold text-slate-800 transition hover:border-slate-300"
          >
            <span>
              {props.conversionSnapshot?.generatedFiles?.length
                ? `${props.conversionSnapshot.generatedFiles.length} files generated`
                : "No generated files yet"}
            </span>
            <span className={`text-xs uppercase tracking-wide text-slate-500 transition ${filesOpen ? "rotate-180" : ""}`}>
              ▾
            </span>
          </button>
          <div
            className="overflow-hidden transition-[max-height,opacity] duration-300 ease-out"
            style={{ maxHeight: filesBodyHeight, opacity: filesOpen ? 1 : 0 }}
          >
            <div ref={filesBodyRef} className="pt-2">
              {props.conversionSnapshot?.generatedFiles?.length ? (
                <ul className="space-y-2 text-sm text-slate-700">
                  {props.conversionSnapshot.generatedFiles.map((path) => (
                    <li key={path} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                      {path}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm font-semibold text-slate-800">No generated files yet</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Backend Logs</CardTitle>
          <CardDescription>Live logs captured during conversion</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-xl border border-slate-800 bg-slate-950/95 p-3">
            <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap text-xs text-emerald-200">
              {props.backendLogs.length > 0
                ? props.backendLogs.join("\n")
                : props.backendLogsStatus === "missing"
                  ? "Job not found. Start a new conversion to stream logs."
                  : "No backend logs yet."}
            </pre>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

interface PanelBodyProps {
  activeStep: number
  hideSpringConfig: boolean
  onConversionStart: () => void
  sourceMethod: SourceMethod
  dbHost: string
  dbPort: string
  dbServiceName: string
  dbUsername: string
  dbPassword: string
  dbConfigPath: string
  availableDatabases: string[]
  setAvailableDatabases: (databases: string[]) => void
  selectedDatabases: string[]
  setSelectedDatabases: (databases: string[]) => void
  availableSchemas: string[]
  setAvailableSchemas: (schemas: string[]) => void
  selectedSchemas: string[]
  setSelectedSchemas: (schemas: string[]) => void
  availableObjects: string[]
  setAvailableObjects: (objects: string[]) => void
  selectedObjects: string[]
  setSelectedObjects: (objects: string[]) => void
  availableProcedures: string[]
  setAvailableProcedures: (procedures: string[]) => void
  selectedProcedures: string[]
  setSelectedProcedures: (procedures: string[]) => void
  setAnalyzedDependencies: (deps: DependencyInsight[]) => void
  setSuggestedDependencies: (deps: SuggestedDependency[]) => void
  onDiscoveryLoadingChange?: (value: boolean) => void
  selectedStrategy: string
  springBootVersion: string
  setSpringBootVersion: (value: string) => void
  javaVersion: string
  setJavaVersion: (value: string) => void
  buildTool: BuildTool
  setBuildTool: (tool: BuildTool) => void
  packaging: PackagingType
  setPackaging: (value: PackagingType) => void
  springConfigFormat: SpringConfigFormat
  setSpringConfigFormat: (format: SpringConfigFormat) => void
  projectGroup: string
  setProjectGroup: (value: string) => void
  projectArtifact: string
  setProjectArtifact: (value: string) => void
  projectDisplayName: string
  setProjectDisplayName: (value: string) => void
  projectDescription: string
  setProjectDescription: (value: string) => void
  projectPackageName: string
  setProjectPackageName: (value: string) => void
  outputDirectory: string
  setOutputDirectory: (value: string) => void
  analyzedDependencies: DependencyInsight[]
  suggestedDependencies: SuggestedDependency[]
  selectedOptionalDependencies: string[]
  setSelectedOptionalDependencies: (deps: string[]) => void
  gitRepoUrl: string
  projectName: string
  conversionSnapshot: ConversionSnapshot | null
  onSnapshotChange: (snapshot: ConversionSnapshot | null) => void
  backendLogs: string[]
  backendLogsStatus: string | null
  onBackendLogsChange: (lines: string[], status?: string | null) => void
  setGitRepoUrl: (value: string) => void
  setSourceMethod: (method: SourceMethod) => void
  setDbHost: (value: string) => void
  setDbPort: (value: string) => void
  setDbServiceName: (value: string) => void
  setDbUsername: (value: string) => void
  setDbPassword: (value: string) => void
  setDbConfigPath: (value: string) => void
  sourceFile: File | null
  setSourceFile: (file: File | null) => void
}

function PanelBody(props: PanelBodyProps) {
  switch (props.activeStep) {
    case 1:
      return (
        <ConnectPanel
          sourceMethod={props.sourceMethod}
          setSourceMethod={props.setSourceMethod}
          gitRepoUrl={props.gitRepoUrl}
          setGitRepoUrl={props.setGitRepoUrl}
          dbHost={props.dbHost}
          setDbHost={props.setDbHost}
          dbPort={props.dbPort}
          setDbPort={props.setDbPort}
          dbServiceName={props.dbServiceName}
          setDbServiceName={props.setDbServiceName}
          dbUsername={props.dbUsername}
          setDbUsername={props.setDbUsername}
          dbPassword={props.dbPassword}
          setDbPassword={props.setDbPassword}
          dbConfigPath={props.dbConfigPath}
          setDbConfigPath={props.setDbConfigPath}
          sourceFile={props.sourceFile}
          setSourceFile={props.setSourceFile}
        />
      )
    case 2:
      return (
        <DiscoveryPanel
          sourceMethod={props.sourceMethod}
          gitRepoUrl={props.gitRepoUrl}
          sourceFile={props.sourceFile}
          dbHost={props.dbHost}
          dbPort={props.dbPort}
          dbServiceName={props.dbServiceName}
          dbUsername={props.dbUsername}
          dbPassword={props.dbPassword}
          availableDatabases={props.availableDatabases}
          setAvailableDatabases={props.setAvailableDatabases}
          selectedDatabases={props.selectedDatabases}
          setSelectedDatabases={props.setSelectedDatabases}
          availableSchemas={props.availableSchemas}
          setAvailableSchemas={props.setAvailableSchemas}
          selectedSchemas={props.selectedSchemas}
          setSelectedSchemas={props.setSelectedSchemas}
          availableObjects={props.availableObjects}
          setAvailableObjects={props.setAvailableObjects}
          selectedObjects={props.selectedObjects}
          setSelectedObjects={props.setSelectedObjects}
          availableProcedures={props.availableProcedures}
          setAvailableProcedures={props.setAvailableProcedures}
          selectedProcedures={props.selectedProcedures}
          setSelectedProcedures={props.setSelectedProcedures}
          setAnalyzedDependencies={props.setAnalyzedDependencies}
          setSuggestedDependencies={props.setSuggestedDependencies}
          onDiscoveryLoadingChange={props.onDiscoveryLoadingChange}
        />
      )
    case 3:
      return (
        <div className="space-y-4">
          {props.hideSpringConfig ? null : (
            <StrategyPanel
              springBootVersion={props.springBootVersion}
              setSpringBootVersion={props.setSpringBootVersion}
              javaVersion={props.javaVersion}
              setJavaVersion={props.setJavaVersion}
              buildTool={props.buildTool}
              setBuildTool={props.setBuildTool}
              packaging={props.packaging}
              setPackaging={props.setPackaging}
              springConfigFormat={props.springConfigFormat}
              setSpringConfigFormat={props.setSpringConfigFormat}
              projectGroup={props.projectGroup}
              setProjectGroup={props.setProjectGroup}
              projectArtifact={props.projectArtifact}
              setProjectArtifact={props.setProjectArtifact}
              projectDisplayName={props.projectDisplayName}
              setProjectDisplayName={props.setProjectDisplayName}
              projectDescription={props.projectDescription}
              setProjectDescription={props.setProjectDescription}
              projectPackageName={props.projectPackageName}
              setProjectPackageName={props.setProjectPackageName}
              outputDirectory={props.outputDirectory}
              setOutputDirectory={props.setOutputDirectory}
              analyzedDependencies={props.analyzedDependencies}
              suggestedDependencies={props.suggestedDependencies}
              selectedOptionalDependencies={props.selectedOptionalDependencies}
              setSelectedOptionalDependencies={props.setSelectedOptionalDependencies}
            />
          )}
          <ConversionJobPanel
            sourceMethod={props.sourceMethod}
            projectName={props.projectName}
            gitRepoUrl={props.gitRepoUrl}
            sourceFile={props.sourceFile}
            dbHost={props.dbHost}
            dbPort={props.dbPort}
            dbServiceName={props.dbServiceName}
            dbUsername={props.dbUsername}
            dbPassword={props.dbPassword}
            dbConfigPath={props.dbConfigPath}
            springBootVersion={props.springBootVersion}
            javaVersion={props.javaVersion}
            buildTool={props.buildTool}
            packaging={props.packaging}
            springConfigFormat={props.springConfigFormat}
            projectGroup={props.projectGroup}
            projectArtifact={props.projectArtifact}
            projectDisplayName={props.projectDisplayName}
            projectDescription={props.projectDescription}
            projectPackageName={props.projectPackageName}
            outputDirectory={props.outputDirectory}
            optionalDependencies={props.selectedOptionalDependencies}
            onConversionStart={props.onConversionStart}
            onSnapshotChange={props.onSnapshotChange}
            onBackendLogsChange={props.onBackendLogsChange}
          />
        </div>
      )
    case 4:
      return (
        <SummaryPanel
          projectName={props.projectName}
          sourceMethod={props.sourceMethod}
          gitRepoUrl={props.gitRepoUrl}
          sourceFileName={props.sourceFile?.name ?? ""}
          dbHost={props.dbHost}
          dbPort={props.dbPort}
          dbServiceName={props.dbServiceName}
          selectedDatabases={props.selectedDatabases}
          selectedSchemas={props.selectedSchemas}
          selectedObjects={props.selectedObjects}
          selectedProcedures={props.selectedProcedures}
          selectedStrategy={props.selectedStrategy}
          javaVersion={props.javaVersion}
          buildTool={props.buildTool}
          springConfigFormat={props.springConfigFormat}
          conversionSnapshot={props.conversionSnapshot}
          backendLogs={props.backendLogs}
          backendLogsStatus={props.backendLogsStatus}
        />
      )
    default:
      return null
  }
}

export function StepPanels({
  activeStep,
  onPrevious,
  onNext,
  onConversionFocusChange,
  onStepAccessChange,
}: StepPanelsProps) {
  const [isDiscoveryLoading, setIsDiscoveryLoading] = useState(false)
  const [sourceMethod, setSourceMethod] = useState<SourceMethod>("oracle")
  const [gitRepoUrl, setGitRepoUrl] = useState("")
  const [dbHost, setDbHost] = useState("localhost")
  const [dbPort, setDbPort] = useState("1521")
  const [dbServiceName, setDbServiceName] = useState("XEPDB1")
  const [dbUsername, setDbUsername] = useState("")
  const [dbPassword, setDbPassword] = useState("")
  const [dbConfigPath, setDbConfigPath] = useState("config.json")
  const [sourceFile, setSourceFile] = useState<File | null>(null)
  const [availableDatabases, setAvailableDatabases] = useState<string[]>([])
  const [selectedDatabases, setSelectedDatabases] = useState<string[]>([])
  const [availableSchemas, setAvailableSchemas] = useState<string[]>([])
  const [selectedSchemas, setSelectedSchemas] = useState<string[]>([])
  const [availableObjects, setAvailableObjects] = useState<string[]>([])
  const [selectedObjects, setSelectedObjects] = useState<string[]>([])
  const [availableProcedures, setAvailableProcedures] = useState<string[]>([])
  const [selectedProcedures, setSelectedProcedures] = useState<string[]>([])
  const [selectedStrategy] = useState(
    strategyOptions.find((option) => option.recommendation)?.title ?? strategyOptions[0]?.title ?? "Strategy",
  )
  const [springBootVersion, setSpringBootVersion] = useState("4.0.3")
  const [javaVersion, setJavaVersion] = useState("17")
  const [buildTool, setBuildTool] = useState<BuildTool>("gradle")
  const [packaging, setPackaging] = useState<PackagingType>("jar")
  const [springConfigFormat, setSpringConfigFormat] = useState<SpringConfigFormat>("properties")
  const [projectGroup, setProjectGroup] = useState("com.example")
  const [projectArtifact, setProjectArtifact] = useState("demo")
  const [projectDisplayName, setProjectDisplayName] = useState("demo")
  const [projectDescription, setProjectDescription] = useState("Demo project for Spring Boot")
  const [projectPackageName, setProjectPackageName] = useState("com.example.demo")
  const [outputDirectory, setOutputDirectory] = useState("")
  const [analyzedDependencies, setAnalyzedDependencies] = useState<DependencyInsight[]>([])
  const [suggestedDependencies, setSuggestedDependencies] = useState<SuggestedDependency[]>([])
  const [selectedOptionalDependencies, setSelectedOptionalDependencies] = useState<string[]>([])
  const [conversionSnapshot, setConversionSnapshot] = useState<ConversionSnapshot | null>(null)
  const [backendLogs, setBackendLogs] = useState<string[]>([])
  const [backendLogsStatus, setBackendLogsStatus] = useState<string | null>(null)
  const [hideSpringConfig, setHideSpringConfig] = useState(false)

  useEffect(() => {
    if (activeStep !== 2) {
      setIsDiscoveryLoading(false)
    }
  }, [activeStep])
  const projectName =
    sourceMethod === "oracle"
      ? dbServiceName || "Generated Project"
      : sourceMethod === "git"
        ? "git-conversion-project"
        : sourceFile?.name?.split(".")[0] || "file-conversion-project"
  const step = workflowSteps[activeStep - 1]

  useEffect(() => {
    if (activeStep !== 3) {
      setHideSpringConfig(false)
    }
  }, [activeStep])

  useEffect(() => {
    onConversionFocusChange?.(activeStep === 3 && hideSpringConfig)
  }, [activeStep, hideSpringConfig, onConversionFocusChange])

  function hasValue(value: string): boolean {
    return value.trim().length > 0
  }

  const isStep1Ready =
    sourceMethod === "git"
      ? hasValue(gitRepoUrl)
      : sourceMethod === "sqlfile"
        ? Boolean(sourceFile)
        : hasValue(dbHost) && hasValue(dbPort) && hasValue(dbServiceName) && hasValue(dbUsername) && hasValue(dbPassword)
  const isStep2Ready =
    sourceMethod === "oracle"
      ? selectedProcedures.length > 0
      : selectedObjects.length > 0 || selectedProcedures.length > 0
  const isStep3Ready =
    hasValue(springBootVersion) &&
    hasValue(javaVersion) &&
    hasValue(projectGroup) &&
    hasValue(projectArtifact) &&
    hasValue(projectDisplayName) &&
    hasValue(projectDescription) &&
    hasValue(projectPackageName)
  const isStep4Ready = conversionSnapshot?.status === "completed"

  function isStepReady(stepId: number): boolean {
    if (stepId === 1) {
      return isStep1Ready
    }
    if (stepId === 2) {
      return isStep2Ready
    }
    if (stepId === 3) {
      return isStep3Ready
    }
    return true
  }

  useEffect(() => {
    let maxStep = 1
    if (isStep1Ready) maxStep = 2
    if (isStep1Ready && isStep2Ready) maxStep = 3
    if (isStep1Ready && isStep2Ready && isStep3Ready && isStep4Ready) maxStep = 4
    onStepAccessChange?.(maxStep)
  }, [isStep1Ready, isStep2Ready, isStep3Ready, isStep4Ready, onStepAccessChange])

  return (
    <section className="space-y-4">
      {hideSpringConfig ? null : (
        <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-lg shadow-slate-200/40 backdrop-blur">
          <p className="text-xs uppercase tracking-[0.12em] text-slate-500">Step {step.id} of {workflowSteps.length}</p>
          <h2 className="text-xl font-bold text-slate-900">{step.title}</h2>
          <p className="text-sm text-slate-600">{step.helper}</p>
        </div>
      )}

      <PanelBody
        activeStep={activeStep}
        hideSpringConfig={hideSpringConfig}
        onConversionStart={() => setHideSpringConfig(true)}
        sourceMethod={sourceMethod}
        setSourceMethod={setSourceMethod}
        gitRepoUrl={gitRepoUrl}
        setGitRepoUrl={setGitRepoUrl}
        dbHost={dbHost}
        setDbHost={setDbHost}
        dbPort={dbPort}
        setDbPort={setDbPort}
        dbServiceName={dbServiceName}
        setDbServiceName={setDbServiceName}
        dbUsername={dbUsername}
        setDbUsername={setDbUsername}
        dbPassword={dbPassword}
        setDbPassword={setDbPassword}
        dbConfigPath={dbConfigPath}
        setDbConfigPath={setDbConfigPath}
        sourceFile={sourceFile}
        setSourceFile={setSourceFile}
        availableDatabases={availableDatabases}
        setAvailableDatabases={setAvailableDatabases}
        selectedDatabases={selectedDatabases}
        setSelectedDatabases={setSelectedDatabases}
        availableSchemas={availableSchemas}
        setAvailableSchemas={setAvailableSchemas}
        selectedSchemas={selectedSchemas}
        setSelectedSchemas={setSelectedSchemas}
        availableObjects={availableObjects}
        setAvailableObjects={setAvailableObjects}
        selectedObjects={selectedObjects}
        setSelectedObjects={setSelectedObjects}
        availableProcedures={availableProcedures}
        setAvailableProcedures={setAvailableProcedures}
        selectedProcedures={selectedProcedures}
        setSelectedProcedures={setSelectedProcedures}
        setAnalyzedDependencies={setAnalyzedDependencies}
        setSuggestedDependencies={setSuggestedDependencies}
        onDiscoveryLoadingChange={setIsDiscoveryLoading}
        selectedStrategy={selectedStrategy}
        springBootVersion={springBootVersion}
        setSpringBootVersion={setSpringBootVersion}
        javaVersion={javaVersion}
        setJavaVersion={setJavaVersion}
        buildTool={buildTool}
        setBuildTool={setBuildTool}
        packaging={packaging}
        setPackaging={setPackaging}
        springConfigFormat={springConfigFormat}
        setSpringConfigFormat={setSpringConfigFormat}
        projectGroup={projectGroup}
        setProjectGroup={setProjectGroup}
        projectArtifact={projectArtifact}
        setProjectArtifact={setProjectArtifact}
        projectDisplayName={projectDisplayName}
        setProjectDisplayName={setProjectDisplayName}
        projectDescription={projectDescription}
        setProjectDescription={setProjectDescription}
        projectPackageName={projectPackageName}
        setProjectPackageName={setProjectPackageName}
        outputDirectory={outputDirectory}
        setOutputDirectory={setOutputDirectory}
        analyzedDependencies={analyzedDependencies}
        suggestedDependencies={suggestedDependencies}
        selectedOptionalDependencies={selectedOptionalDependencies}
        setSelectedOptionalDependencies={setSelectedOptionalDependencies}
        projectName={projectName}
        conversionSnapshot={conversionSnapshot}
        onSnapshotChange={setConversionSnapshot}
        backendLogs={backendLogs}
        backendLogsStatus={backendLogsStatus}
        onBackendLogsChange={(lines, status) => {
          setBackendLogs(lines)
          setBackendLogsStatus(status ?? null)
        }}
      />

      {activeStep === workflowSteps.length ? null : (
        <div className="flex items-center justify-between rounded-2xl border border-slate-200/80 bg-white/90 p-3 shadow-lg shadow-slate-200/40 backdrop-blur">
          <Button variant="outline" onClick={onPrevious} disabled={activeStep === 1}>
            Previous
          </Button>
        <Button
          onClick={onNext}
          disabled={
            activeStep === workflowSteps.length ||
            (activeStep === 2 && isDiscoveryLoading) ||
            (activeStep === 3 && conversionSnapshot?.status !== "completed") ||
            !isStepReady(activeStep)
          }
        >
            {activeStep === 2 && isDiscoveryLoading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
            Next step
          </Button>
        </div>
      )}
    </section>
  )
}
