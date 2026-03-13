import { useEffect, useState } from "react"
import {
  ChevronLeft,
  ChevronRight,
  Database,
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
import { testOracleConnection } from "@/lib/oracle-api"
import {
  analyzeGitSqlSource,
  analyzeUploadedSqlFile,
  getGitRepoTree,
  uploadSqlDiscoveryFile,
} from "@/lib/sql-discovery-api"
import { pickOutputDirectory } from "@/lib/jobs-api"
import type { OracleConnectionPayload } from "@/types/oracle-api"
import type { SqlDiscoveryAnalyzeResponse } from "@/types/sql-discovery-api"

interface StepPanelsProps {
  activeStep: number
  onPrevious: () => void
  onNext: () => void
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
}

function SqlSourceDiscovery(props: {
  sourceMethod: SourceMethod
  gitRepoUrl: string
  sourceFile: File | null
  setAvailableObjects: (objects: string[]) => void
  setSelectedObjects: (objects: string[]) => void
  setAvailableProcedures: (procedures: string[]) => void
  setSelectedProcedures: (procedures: string[]) => void
}) {
  const [analysis, setAnalysis] = useState<SqlDiscoveryAnalyzeResponse | null>(null)
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [gitStep, setGitStep] = useState<1 | 2>(1)
  const [gitPath, setGitPath] = useState("")
  const [gitEntries, setGitEntries] = useState<{ name: string; path: string; type: "dir" | "file" }[]>([])
  const [gitTreeError, setGitTreeError] = useState<string | null>(null)
  const [isLoadingTree, setIsLoadingTree] = useState(false)

  useEffect(() => {
    if (props.sourceMethod !== "sqlfile") {
      return
    }
    if (!props.sourceFile) {
      setAnalysis(null)
      props.setAvailableObjects([])
      props.setSelectedObjects([])
      props.setAvailableProcedures([])
      props.setSelectedProcedures([])
      setError("Select a local SQL file in Connect step to preview tables.")
      return
    }

    let isCancelled = false
    const selectedFile = props.sourceFile

    async function analyzeFile() {
      if (!selectedFile) {
        return
      }
      try {
        setIsLoading(true)
        const uploadResponse = await uploadSqlDiscoveryFile(selectedFile)
        if (isCancelled) {
          return
        }
        const analyzed = await analyzeUploadedSqlFile(uploadResponse.file_id)
        if (isCancelled) {
          return
        }

        setAnalysis(analyzed)
        const objectNames = (analyzed.objects ?? []).map(
          (item) => `${item.procedureName} (${item.objectType})`,
        )
        const procedureNames = (analyzed.objects ?? [])
          .filter((item) => item.objectType.toUpperCase() === "PROCEDURE")
          .map((item) => item.procedureName)

        props.setAvailableObjects(objectNames)
        props.setSelectedObjects(objectNames)
        props.setAvailableProcedures(procedureNames)
        props.setSelectedProcedures(procedureNames)
        setError(null)
      } catch (requestError) {
        if (!isCancelled) {
          setAnalysis(null)
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

  useEffect(() => {
    const tables = analysis?.tableDetails?.tables ?? []
    if (!tables.length) {
      setSelectedTable(null)
      return
    }
    if (!selectedTable || !tables.some((table) => table.name === selectedTable)) {
      setSelectedTable(tables[0].name)
    }
  }, [analysis, selectedTable])

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
      return
    }

    let isCancelled = false

    async function analyzeGitRepo() {
      try {
        setIsLoading(true)
        const analyzed = await analyzeGitSqlSource(props.gitRepoUrl.trim())
        if (isCancelled) {
          return
        }
        setAnalysis(analyzed)
        const objectNames = (analyzed.objects ?? []).map(
          (item) => `${item.procedureName} (${item.objectType})`,
        )
        const procedureNames = (analyzed.objects ?? [])
          .filter((item) => item.objectType.toUpperCase() === "PROCEDURE")
          .map((item) => item.procedureName)
        props.setAvailableObjects(objectNames)
        props.setSelectedObjects(objectNames)
        props.setAvailableProcedures(procedureNames)
        props.setSelectedProcedures(procedureNames)
        setError(null)
      } catch (requestError) {
        if (!isCancelled) {
          setAnalysis(null)
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
                  {gitEntries.map((entry) => (
                    entry.name!==".git"&&(
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
                  )))}
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
          {analysis.tableDetails?.tables?.length ? (
            <Card>
              <CardHeader>
                <CardTitle>Schema Explorer</CardTitle>
                <CardDescription>Tables, relationships, and local variables extracted from the SQL source</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 lg:grid-cols-[220px_1fr_260px]">
                <div className="rounded-xl border border-slate-200 bg-white p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Tables ({analysis.tableDetails.tables.length})</p>
                  <div className="mt-2 space-y-1">
                    {analysis.tableDetails.tables.map((table) => (
                      <button
                        key={table.name}
                        onClick={() => setSelectedTable(table.name)}
                        className={`flex w-full items-center justify-between rounded-lg px-2 py-1 text-left text-sm transition ${
                          selectedTable === table.name
                            ? "bg-cyan-50 text-cyan-900"
                            : "text-slate-700 hover:bg-slate-50"
                        }`}
                      >
                        <span>{table.name}</span>
                        <span className="text-xs text-slate-400">{table.columns.length}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <div className="absolute inset-0 bg-grid-pattern opacity-30" />
                  <div className="relative h-full min-h-[320px] overflow-auto p-6">
                    {(() => {
                      const tables = analysis.tableDetails?.tables ?? []
                      const relationships = analysis.tableDetails?.relationships ?? []
                      const cardWidth = 220
                      const cardHeight = 140
                      const gapX = 80
                      const gapY = 90
                      const columns = 2
                      const rows = Math.ceil(tables.length / columns)
                      const width = columns * cardWidth + (columns - 1) * gapX + 40
                      const height = rows * cardHeight + (rows - 1) * gapY + 40
                      const positions = new Map<string, { x: number; y: number }>()
                      tables.forEach((table, index) => {
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
                              const from = positions.get(rel.fromTable)
                              const to = positions.get(rel.toTable)
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
                                  key={`${rel.fromTable}-${rel.toTable}-${idx}`}
                                  d={`M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`}
                                  stroke="#94a3b8"
                                  strokeWidth="1.5"
                                  fill="none"
                                  markerEnd="url(#arrow)"
                                />
                              )
                            })}
                          </svg>

                          {tables.map((table) => {
                            const pos = positions.get(table.name)
                            if (!pos) {
                              return null
                            }
                            return (
                              <div
                                key={table.name}
                                className="absolute rounded-xl border border-slate-200 bg-white shadow-sm"
                                style={{ width: cardWidth, height: cardHeight, left: pos.x, top: pos.y }}
                              >
                                <div className="rounded-t-xl border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700">
                                  {table.name}
                                </div>
                                <div className="px-3 py-2 text-xs text-slate-600">
                                  {table.columns.length > 0 ? (
                                    <ul className="space-y-1">
                                      {table.columns.slice(0, 6).map((col) => (
                                        <li key={col}>{col}</li>
                                      ))}
                                    </ul>
                                  ) : (
                                    <p className="text-slate-400">No columns detected</p>
                                  )}
                                  {table.columns.length > 6 ? (
                                    <p className="mt-1 text-[11px] text-slate-400">
                                      +{table.columns.length - 6} more
                                    </p>
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
                    <p className="text-xs uppercase tracking-wide text-slate-500">Local Variables</p>
                    {(analysis.localVariables ?? []).length > 0 ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {(analysis.localVariables ?? []).map((variable) => (
                          <span
                            key={variable.name}
                            className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700"
                          >
                            {variable.name} ({variable.type})
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-sm text-slate-400">No local variables detected</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Table Properties</p>
                  <div className="mt-3 space-y-3">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-800">
                      {selectedTable ?? "Select a table"}
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Columns</p>
                      <div className="mt-2 space-y-1 text-sm text-slate-700">
                        {(analysis.tableDetails.tables.find((t) => t.name === selectedTable)?.columns ?? []).map(
                          (col) => (
                            <p key={col}>{col}</p>
                          ),
                        )}
                        {selectedTable &&
                        (analysis.tableDetails.tables.find((t) => t.name === selectedTable)?.columns?.length ?? 0) ===
                          0 ? (
                          <p className="text-sm text-slate-400">No columns detected</p>
                        ) : null}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Local Variables</p>
                      <div className="mt-2 space-y-1 text-sm text-slate-700">
                        {(analysis.localVariables ?? []).length > 0 ? (
                          (analysis.localVariables ?? []).map((variable) => (
                            <p key={variable.name}>
                              {variable.name} ({variable.type})
                            </p>
                          ))
                        ) : (
                          <p className="text-sm text-slate-400">No local variables detected</p>
                        )}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Relationships</p>
                      <div className="mt-2 space-y-1 text-sm text-slate-700">
                        {(analysis.tableDetails.relationships ?? []).length > 0 ? (
                          analysis.tableDetails.relationships.map((rel, index) => (
                            <p key={`${rel.fromTable}-${rel.toTable}-${index}`}>
                              {rel.fromTable}.{rel.fromColumn} → {rel.toTable}.{rel.toColumn}
                            </p>
                          ))
                        ) : (
                          <p className="text-sm text-slate-400">No relationships detected</p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Procedure Info</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">Procedure Name</p>
                <p className="text-sm font-semibold text-slate-800">{analysis.procedureName || "N/A"}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">Object Type</p>
                <p className="text-sm font-semibold text-slate-800">{analysis.objectType || "N/A"}</p>
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
                  {(analysis.parameters?.in ?? []).length > 0 ? (
                    analysis.parameters?.in?.map((param) => (
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
                  {(analysis.parameters?.out ?? []).length > 0 ? (
                    analysis.parameters?.out?.map((param) => (
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
                <CardTitle>Tables</CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                {(analysis.tablesUsed ?? []).length > 0 ? (
                  <ul className="space-y-1 text-slate-700">
                    {(analysis.tablesUsed ?? []).map((tableName) => (
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
                <CardTitle>Operations</CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                {(analysis.operations ?? []).length > 0 ? (
                  <ul className="space-y-1 text-slate-700">
                    {(analysis.operations ?? []).map((operation) => (
                      <li key={operation}>{operation}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-slate-500">No operations detected</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Local Variables</CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                {(analysis.localVariables ?? []).length > 0 ? (
                  <ul className="space-y-1 text-slate-700">
                    {(analysis.localVariables ?? []).map((variable) => (
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
                <CardTitle>Exceptions</CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                {(analysis.exceptions ?? []).length > 0 ? (
                  <ul className="space-y-1 text-slate-700">
                    {(analysis.exceptions ?? []).map((exceptionName) => (
                      <li key={exceptionName}>{exceptionName}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-slate-500">No exceptions detected</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Complexity</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm md:grid-cols-2">
                <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                  LOC: {analysis.complexity?.linesOfCode ?? 0}
                </p>
                <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                  Queries: {analysis.complexity?.numberOfQueries ?? 0}
                </p>
                <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                  Conditions: {analysis.complexity?.numberOfConditions ?? 0}
                </p>
                <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                  Loops: {analysis.complexity?.numberOfLoops ?? 0}
                </p>
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
                  <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Tables Used</p>
                  {(analysis.dependencyGraph?.tablesUsed ?? []).length > 0 ? (
                    <ul className="space-y-1 text-slate-700">
                      {(analysis.dependencyGraph?.tablesUsed ?? []).map((tableName) => (
                        <li key={tableName}>{tableName}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-slate-500">No table dependencies detected</p>
                  )}
                </div>
                <div>
                  <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Procedures Called</p>
                  {(analysis.dependencyGraph?.proceduresCalled ?? []).length > 0 ? (
                    <ul className="space-y-1 text-slate-700">
                      {(analysis.dependencyGraph?.proceduresCalled ?? []).map((proc) => (
                        <li key={proc}>{proc}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-slate-500">No procedure dependencies detected</p>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Conversion Preview</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {[
                  { label: "Entities", values: analysis.conversionPreview?.entities ?? [] },
                  { label: "Repositories", values: analysis.conversionPreview?.repositories ?? [] },
                  { label: "Services", values: analysis.conversionPreview?.services ?? [] },
                  { label: "Controllers", values: analysis.conversionPreview?.controllers ?? [] },
                  { label: "DTOs", values: analysis.conversionPreview?.dtos ?? [] },
                ].map((item) => (
                  <div key={item.label}>
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
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Objects</CardTitle>
            </CardHeader>
            <CardContent>
              {(analysis.objects ?? []).length > 0 ? (
                <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="px-3 py-2 text-left font-semibold">Procedure</th>
                        <th className="px-3 py-2 text-left font-semibold">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(analysis.objects ?? []).map((item) => (
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
}

function StrategyPanel(props: StrategyPanelProps) {
  const [language, setLanguage] = useState<"java" | "kotlin" | "groovy">("java")
  const [gradleFlavor, setGradleFlavor] = useState<"groovy" | "kotlin">("groovy")
  const [isPickingDir, setIsPickingDir] = useState(false)
  const [pickDirError, setPickDirError] = useState<string | null>(null)

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
            
          </div>
          <p className="mt-4 text-sm text-slate-500">No dependency selected</p>
          <p className="mt-6 text-xs text-slate-400">
            {DEFAULT_SPRING_DEPENDENCIES.length} defaults will be included during generation.
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
}

function SummaryPanel(props: SummaryPanelProps) {
  const sourceLabel =
    props.sourceMethod === "oracle"
      ? `Oracle DB (${props.dbServiceName})`
      : props.sourceMethod === "git"
        ? `Git repository (${props.gitRepoUrl || "Not provided"})`
        : `Local file (${props.sourceFileName || "Not selected"})`
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

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Project Narrative Summary</CardTitle>
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
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Selected Logic Units</p>
            <p className="text-sm font-semibold text-slate-900">{props.selectedProcedures.length} procedures</p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Primary Logic Domains</p>
            <p className="text-sm font-semibold text-slate-900">
              {dominantDomains.length > 0 ? dominantDomains.join(", ") : "Not inferred yet"}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Applied Strategy</p>
            <p className="text-sm font-semibold text-slate-900">{props.selectedStrategy}</p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
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
          <CardTitle>DB & Output Details</CardTitle>
          <CardDescription>Database context and generated project paths</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
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
            <p className="text-sm font-semibold text-slate-800">
              {defaultDependencyNames.join(", ")}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Output Directory</p>
            <p className="text-sm font-semibold text-slate-800">
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
  gitRepoUrl: string
  projectName: string
  conversionSnapshot: ConversionSnapshot | null
  onSnapshotChange: (snapshot: ConversionSnapshot | null) => void
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
            onConversionStart={props.onConversionStart}
            onSnapshotChange={props.onSnapshotChange}
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
        />
      )
    default:
      return null
  }
}

export function StepPanels({ activeStep, onPrevious, onNext }: StepPanelsProps) {
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
  const [conversionSnapshot, setConversionSnapshot] = useState<ConversionSnapshot | null>(null)
  const [hideSpringConfig, setHideSpringConfig] = useState(false)
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

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-lg shadow-slate-200/40 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.12em] text-slate-500">Step {step.id} of {workflowSteps.length}</p>
        <h2 className="text-xl font-bold text-slate-900">{step.title}</h2>
        <p className="text-sm text-slate-600">{step.helper}</p>
      </div>

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
        projectName={projectName}
        conversionSnapshot={conversionSnapshot}
        onSnapshotChange={setConversionSnapshot}
      />

      <div className="flex items-center justify-between rounded-2xl border border-slate-200/80 bg-white/90 p-3 shadow-lg shadow-slate-200/40 backdrop-blur">
        <Button variant="outline" onClick={onPrevious} disabled={activeStep === 1}>
          Previous
        </Button>
        <Button onClick={onNext} disabled={activeStep === workflowSteps.length}>
          Next step
        </Button>
      </div>
    </section>
  )
}
