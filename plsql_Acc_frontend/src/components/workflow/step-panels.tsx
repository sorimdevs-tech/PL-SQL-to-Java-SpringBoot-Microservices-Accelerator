import { useEffect, useState } from "react"
import { Database, FileCode2, GitBranch, LoaderCircle, RefreshCcw } from "lucide-react"

import { ConversionJobPanel, type ConversionSnapshot } from "@/components/workflow/conversion-job-panel"
import { OracleDiscovery } from "@/components/workflow/oracle-discovery"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { strategyOptions, workflowSteps } from "@/data/converter-workflow"
import { testOracleConnection } from "@/lib/oracle-api"
import { analyzeUploadedSqlFile, uploadSqlDiscoveryFile } from "@/lib/sql-discovery-api"
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
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    if (props.sourceMethod !== "git") {
      return
    }
    setAnalysis(null)
    props.setAvailableObjects([])
    props.setSelectedObjects([])
    props.setAvailableProcedures([])
    props.setSelectedProcedures([])
    if (!props.gitRepoUrl.trim()) {
      setError("Provide a Git repository URL in Connect step to discover SQL tables.")
      return
    }
    setError("Git SQL discovery API is not connected yet. Use SQL file mode or wire backend git discovery endpoint.")
  }, [
    props.gitRepoUrl,
    props.setAvailableObjects,
    props.setAvailableProcedures,
    props.setSelectedObjects,
    props.setSelectedProcedures,
    props.sourceMethod,
  ])

  return (
    <div className="space-y-4">
      {isLoading ? (
        <Card>
          <CardContent className="p-4">
            <p className="inline-flex items-center gap-2 text-sm text-slate-600">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              Analyzing SQL file...
            </p>
          </CardContent>
        </Card>
      ) : null}

      {error ? (
        <Card>
          <CardContent className="p-4">
            <p className="text-sm font-medium text-rose-700">{error}</p>
          </CardContent>
        </Card>
      ) : null}

      {analysis ? (
        <>
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
}

function StrategyPanel(props: StrategyPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Spring Project Specifications</CardTitle>
        <CardDescription>Configure project metadata and choose baseline dependencies</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5 lg:grid-cols-[1.15fr_1fr]">
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Build Tool</p>
              <select
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
                value={props.buildTool}
                onChange={(event) => props.setBuildTool(event.target.value as BuildTool)}
              >
                <option value="mvn">Maven</option>
                <option value="gradle">Gradle</option>
              </select>
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Spring Boot</p>
              <select
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
                value={props.springBootVersion}
                onChange={(event) => props.setSpringBootVersion(event.target.value)}
              >
                <option value="3.4.5">3.4.5 (Recommended)</option>
                <option value="3.3.11">3.3.11</option>
              </select>
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Java Version</p>
              <select
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
                value={props.javaVersion}
                onChange={(event) => props.setJavaVersion(event.target.value)}
              >
                <option value="17">17 (LTS)</option>
                <option value="21">21 (LTS)</option>
              </select>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Packaging</p>
              <select
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
                value={props.packaging}
                onChange={(event) => props.setPackaging(event.target.value as PackagingType)}
              >
                <option value="jar">Jar</option>
                <option value="war">War</option>
              </select>
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Configuration</p>
              <select
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
                value={props.springConfigFormat}
                onChange={(event) => props.setSpringConfigFormat(event.target.value as SpringConfigFormat)}
              >
                <option value="properties">application.properties</option>
                <option value="yaml">application.yml</option>
              </select>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Group</p>
              <Input value={props.projectGroup} onChange={(event) => props.setProjectGroup(event.target.value)} />
            </div>
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Artifact</p>
              <Input value={props.projectArtifact} onChange={(event) => props.setProjectArtifact(event.target.value)} />
            </div>
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Name</p>
              <Input value={props.projectDisplayName} onChange={(event) => props.setProjectDisplayName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">Package Name</p>
              <Input value={props.projectPackageName} onChange={(event) => props.setProjectPackageName(event.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-slate-500">Description</p>
            <Input value={props.projectDescription} onChange={(event) => props.setProjectDescription(event.target.value)} />
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-900">Dependencies</p>
            <p className="text-xs text-slate-500">{DEFAULT_SPRING_DEPENDENCIES.length} defaults</p>
          </div>
          <div className="mt-3 space-y-2">
            {DEFAULT_SPRING_DEPENDENCIES.map((dependency) => (
              <div
                key={dependency.id}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
              >
                <span>
                  <span className="block font-medium text-slate-900">{dependency.name}</span>
                  <span className="text-xs text-slate-500">{dependency.description}</span>
                </span>
              </div>
            ))}
            <p className="rounded-lg border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs text-cyan-800">
              These dependencies will be added automatically by our LLM Engine during Application generation.
            </p>
          </div>
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
  const dummySummary = `This conversion project originates from the ${sourceLabel} source and is prepared as project "${props.projectName}". The selected database scope contains ${props.selectedDatabases.length} database(s), ${props.selectedSchemas.length} schema(s), ${props.selectedObjects.length} objects, and ${props.selectedProcedures.length} stored procedures for migration. Based on selected procedure patterns, the main business logic focus is ${dominantDomains.length > 0 ? dominantDomains.join(", ") : "functional decomposition and service extraction"}.

The conversion strategy "${props.selectedStrategy}" will generate Spring Boot components that separate business rules into service classes, persistence operations into repository layers, and operational workflows into structured API/service boundaries. The runtime target is Java ${props.javaVersion} using ${props.buildTool}, with configuration expected in ${props.springConfigFormat === "properties" ? "application.properties" : "application.yml"}. Baseline dependencies include ${defaultDependencyNames.join(", ")} and will be added by our LLM; output is expected at ${props.conversionSnapshot?.outputDirectory ?? "the configured output directory once conversion is executed"}.

Generated artifacts are expected to include application source classes, repositories, DTOs, and supporting build files. This summary is currently generated from frontend context and selected scope.`
  const resolvedSummary = props.conversionSnapshot?.backendSummary?.trim() || dummySummary

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Project Narrative Summary</CardTitle>
          <CardDescription>
            {props.conversionSnapshot?.backendSummary ? "From backend conversion summary" : "Frontend dummy summary (fallback)"}
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
          />
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
  const [springBootVersion, setSpringBootVersion] = useState("3.4.5")
  const [javaVersion, setJavaVersion] = useState("17")
  const [buildTool, setBuildTool] = useState<BuildTool>("mvn")
  const [packaging, setPackaging] = useState<PackagingType>("jar")
  const [springConfigFormat, setSpringConfigFormat] = useState<SpringConfigFormat>("properties")
  const [projectGroup, setProjectGroup] = useState("com.example")
  const [projectArtifact, setProjectArtifact] = useState("demo")
  const [projectDisplayName, setProjectDisplayName] = useState("demo")
  const [projectDescription, setProjectDescription] = useState("Demo project for Spring Boot")
  const [projectPackageName, setProjectPackageName] = useState("com.example.demo")
  const [conversionSnapshot, setConversionSnapshot] = useState<ConversionSnapshot | null>(null)
  const projectName =
    sourceMethod === "oracle"
      ? dbServiceName || "Generated Project"
      : sourceMethod === "git"
        ? "git-conversion-project"
        : sourceFile?.name?.split(".")[0] || "file-conversion-project"
  const step = workflowSteps[activeStep - 1]

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-lg shadow-slate-200/40 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.12em] text-slate-500">Step {step.id} of {workflowSteps.length}</p>
        <h2 className="text-xl font-bold text-slate-900">{step.title}</h2>
        <p className="text-sm text-slate-600">{step.helper}</p>
      </div>

      <PanelBody
        activeStep={activeStep}
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
