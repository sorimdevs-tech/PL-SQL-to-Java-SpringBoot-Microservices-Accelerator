import { useCallback, useEffect, useRef, useState } from "react"
import { Download, FileText, LoaderCircle, Play, RefreshCcw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  createFileJob,
  createGitJob,
  getBackendHealth,
  getJobDownloadUrl,
  getJobFileContent,
  getJobFiles,
  getJobStatus,
} from "@/lib/jobs-api"
import { startOracleConvert } from "@/lib/oracle-api"
import type { ConfigOverrides, ConversionJob, GeneratedFile } from "@/types/jobs-api"

type SourceMethod = "git" | "oracle" | "sqlfile"

export interface ConversionSnapshot {
  jobId: string
  status: string
  outputDirectory: string
  generatedFiles: string[]
  backendSummary?: string
  backendSummaryData?: Record<string, unknown>
}

interface ConversionJobPanelProps {
  sourceMethod: SourceMethod
  projectName: string
  gitRepoUrl: string
  sourceFile: File | null
  dbHost: string
  dbPort: string
  dbServiceName: string
  dbUsername: string
  dbPassword: string
  dbConfigPath: string
  springBootVersion: string
  javaVersion: string
  buildTool: "mvn" | "gradle"
  packaging: "jar" | "war"
  springConfigFormat: "properties" | "yaml"
  projectGroup: string
  projectArtifact: string
  projectDisplayName: string
  projectDescription: string
  projectPackageName: string
  outputDirectory: string
  onConversionStart: () => void
  onSnapshotChange: (snapshot: ConversionSnapshot | null) => void
}

function statusVariant(status: string) {
  switch (status) {
    case "completed":
      return "success"
    case "failed":
      return "danger"
    case "running":
      return "info"
    default:
      return "warning"
  }
}

export function ConversionJobPanel(props: ConversionJobPanelProps) {
  const { onSnapshotChange } = props
  const [job, setJob] = useState<ConversionJob | null>(null)
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([])
  const [selectedFilePath, setSelectedFilePath] = useState("")
  const [selectedFileContent, setSelectedFileContent] = useState("")
  const [isStarting, setIsStarting] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isLoadingFiles, setIsLoadingFiles] = useState(false)
  const [isLoadingFileContent, setIsLoadingFileContent] = useState(false)
  const [isCheckingHealth, setIsCheckingHealth] = useState(false)
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [logs, setLogs] = useState<{ id: string; message: string; time: string }[]>([])
  const [progressStage, setProgressStage] = useState<"idle" | "queued" | "running" | "completed" | "failed">("idle")
  const lastStatusRef = useRef<string | null>(null)
  const [conversionStarted, setConversionStarted] = useState(false)

  const isPolling = job?.status === "queued" || job?.status === "running"

  useEffect(() => {
    if (!job?.job_id) {
      onSnapshotChange(null)
      setProgressStage("idle")
      return
    }
    const rawSummary = job.result?.summary
    const backendSummary =
      typeof rawSummary === "string"
        ? rawSummary
        : rawSummary
          ? JSON.stringify(rawSummary, null, 2)
          : undefined
    const backendSummaryData =
      rawSummary && typeof rawSummary === "object" && !Array.isArray(rawSummary)
        ? (rawSummary as Record<string, unknown>)
        : undefined
    onSnapshotChange({
      jobId: job.job_id,
      status: job.status,
      outputDirectory:
        job.result?.output_directory ?? job.output_directory ?? "Output directory not available yet",
      generatedFiles: generatedFiles.map((file) => file.path),
      backendSummary,
      backendSummaryData,
    })
  }, [generatedFiles, job, onSnapshotChange])

  useEffect(() => {
    if (!job) {
      return
    }
    if (lastStatusRef.current !== job.status) {
      const now = new Date()
      const time = now.toLocaleTimeString()
      const message =
        job.status === "queued"
          ? "Job queued. Preparing pipeline..."
          : job.status === "running"
            ? "Pipeline running. Generating Spring Boot project..."
            : job.status === "completed"
              ? "Generation complete. Output is ready."
              : job.status === "failed"
                ? `Job failed: ${job.error ?? "Unknown error"}`
                : `Status update: ${job.status}`
      setLogs((prev) => [{ id: `${job.job_id}-${job.status}-${time}`, message, time }, ...prev].slice(0, 12))
      lastStatusRef.current = job.status
    }
    if (job.status === "queued" || job.status === "running") {
      setProgressStage(job.status)
    } else if (job.status === "completed") {
      setProgressStage("completed")
    } else if (job.status === "failed") {
      setProgressStage("failed")
    }
  }, [job])

  const loadGeneratedFiles = useCallback(async (jobId: string) => {
    try {
      setIsLoadingFiles(true)
      const files = await getJobFiles(jobId)
      setGeneratedFiles(files)
      setError(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load generated files.")
    } finally {
      setIsLoadingFiles(false)
    }
  }, [])

  const refreshJobStatus = useCallback(async (jobId: string, showLoader = false) => {
    try {
      if (showLoader) {
        setIsRefreshing(true)
      }
      const latest = await getJobStatus(jobId)
      setJob(latest)
      setError(null)

      if (latest.status === "completed") {
        await loadGeneratedFiles(latest.job_id)
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to refresh job status.")
    } finally {
      setIsRefreshing(false)
    }
  }, [loadGeneratedFiles])

  useEffect(() => {
    if (!job?.job_id || !isPolling) {
      return
    }

    const interval = window.setInterval(() => {
      void refreshJobStatus(job.job_id)
    }, 2500)

    return () => window.clearInterval(interval)
  }, [isPolling, job?.job_id, refreshJobStatus])

  useEffect(() => {
    if (props.sourceMethod !== "git") {
      setIsBackendHealthy(null)
      return
    }

    let isCancelled = false

    async function checkHealth() {
      try {
        setIsCheckingHealth(true)
        const response = await getBackendHealth()
        if (isCancelled) {
          return
        }
        setIsBackendHealthy(response.status === "ok")
      } catch {
        if (!isCancelled) {
          setIsBackendHealthy(false)
        }
      } finally {
        if (!isCancelled) {
          setIsCheckingHealth(false)
        }
      }
    }

    void checkHealth()

    return () => {
      isCancelled = true
    }
  }, [props.sourceMethod])

  async function loadFileContent(path: string) {
    if (!job?.job_id) {
      return
    }
    try {
      setIsLoadingFileContent(true)
      const content = await getJobFileContent(job.job_id, path)
      setSelectedFilePath(path)
      setSelectedFileContent(content)
      setError(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load file content.")
    } finally {
      setIsLoadingFileContent(false)
    }
  }

  async function startConversion() {
    setError(null)
    setGeneratedFiles([])
    setSelectedFilePath("")
    setSelectedFileContent("")
    setLogs([])
    setProgressStage("queued")
    props.onConversionStart()
    setConversionStarted(true)
    try {
      setIsStarting(true)
      let createdJob: ConversionJob | null = null
      const configPath = props.dbConfigPath || "config.json"
      const configOverrides: ConfigOverrides = {
        output: {
          project_name: props.projectDisplayName.trim() || props.projectArtifact.trim() || props.projectName,
          group_id: props.projectGroup.trim() || "com.company",
          artifact_id: props.projectArtifact.trim() || props.projectName,
          package_name: props.projectPackageName.trim() || props.projectGroup.trim() || "com.company.project",
          description: props.projectDescription.trim() || "PL/SQL to Java Modernization Project",
          java_version: props.javaVersion,
          spring_boot_version: props.springBootVersion,
          build_tool: props.buildTool === "mvn" ? "maven" : "gradle",
          packaging: props.packaging,
          config_format: props.springConfigFormat,
          target_directory: props.outputDirectory.trim() || undefined,
        },
      }
      const outputDirectory = props.outputDirectory.trim() || undefined

      if (props.sourceMethod === "sqlfile") {
        if (!props.sourceFile) {
          setError("Select a local SQL file before starting conversion.")
          return
        }
        createdJob = await createFileJob(props.sourceFile, configPath, configOverrides, outputDirectory)
      } else if (props.sourceMethod === "git") {
        if (!props.gitRepoUrl.trim()) {
          setError("Enter a valid Git repository URL.")
          return
        }
        if (isBackendHealthy === false) {
          setError("Backend health check failed. Ensure API server is running before starting Git conversion.")
          return
        }
        createdJob = await createGitJob(props.gitRepoUrl.trim(), configPath, configOverrides, outputDirectory)
      } else {
        const response = await startOracleConvert({
          host: props.dbHost.trim(),
          port: Number(props.dbPort),
          service_name: props.dbServiceName.trim(),
          username: props.dbUsername.trim(),
          password: props.dbPassword,
          config_path: configPath,
          config_overrides: configOverrides,
          output_directory: outputDirectory,
        })

        const maybeJob = response as Partial<ConversionJob>
        if (!maybeJob.job_id) {
          setError("Oracle convert response did not return a job_id.")
          return
        }
        createdJob = maybeJob as ConversionJob
      }

      setJob(createdJob)
      if (createdJob.status === "completed") {
        await loadGeneratedFiles(createdJob.job_id)
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to start conversion.")
      setProgressStage("failed")
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <Card className="border-none bg-gradient-to-br from-slate-900 via-slate-800 to-cyan-900 text-white">
      <CardHeader>
        <CardTitle className="text-white">Ready to convert: {props.projectName}</CardTitle>
        <CardDescription className="text-slate-200">
          Start conversion and track job progress, generated files, preview, and download.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {props.sourceMethod === "git" ? (
          <div className="rounded-xl border border-white/20 bg-white/10 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-200">Git API Health</p>
            <p className="mt-1 text-sm text-slate-100">
              {isCheckingHealth
                ? "Checking /health ..."
                : isBackendHealthy === true
                  ? "Backend is healthy."
                  : isBackendHealthy === false
                    ? "Backend is unreachable or unhealthy."
                    : "Health check pending."}
            </p>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          {isStarting ? (
            <div className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/30 bg-white/10 px-4 text-sm font-semibold text-white">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              Starting...
            </div>
          ): job?.status === "completed" ? (
            <Badge className="inline-flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-500/15 px-4 py-1.5 text-sm font-semibold text-emerald-300 backdrop-blur-sm">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              Completed
            </Badge>
          ) : conversionStarted && !isStarting ? (
            <div className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/30 bg-white/10 px-4 text-sm font-semibold text-white">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              Converting...
            </div>
           ) :(
            <Button
              variant="secondary"
              onClick={startConversion}
              disabled={props.sourceMethod === "git" && (isCheckingHealth || isBackendHealthy === false)}
            >
              <Play className="h-4 w-4" />
              Start Conversion
            </Button>
          )}
          {job?.job_id ? (
            <Button variant="outline" onClick={() => void refreshJobStatus(job.job_id, true)} disabled={isRefreshing}>
              {isRefreshing ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              Refresh Status
            </Button>
          ) : null}
          {job?.job_id && job.status === "completed" ? (
            <a
              href={getJobDownloadUrl(job.job_id)}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-emerald-500 px-4 text-sm font-semibold text-white shadow-md shadow-emerald-500/30 transition-all duration-200 hover:-translate-y-0.5 hover:bg-emerald-600"
            >
              <Download className="h-4 w-4" />
              Download ZIP
            </a>
          ) : null}
        </div>

        {progressStage !== "idle" ? (
          <div className="rounded-xl border border-white/20 bg-white/10 p-3">
            <div className="flex items-center justify-between text-xs text-slate-200">
              <span>Application creation</span>
              <span className="uppercase tracking-wide">{progressStage}</span>
            </div>
            <div className="relative mt-2 h-2 overflow-hidden rounded-full bg-white/20">
              {progressStage === "completed" ? (
                <div className="h-full w-full bg-emerald-400" />
              ) : progressStage === "failed" ? (
                <div className="h-full w-full bg-rose-500" />
              ) : (
                <div className="progress-stripe" />
              )}
            </div>
          </div>
        ) : null}

        {job ? (
          <div className="rounded-xl border border-white/20 bg-white/10 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold">Job ID: {job.job_id}</p>
              <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
            </div>
            <p className="mt-1 text-xs text-slate-200">Source: {job.source_type}</p>
            {job.error ? <p className="mt-2 text-xs font-medium text-rose-200">{job.error}</p> : null}
          </div>
        ) : null}

        {logs.length > 0 ? (
          <div className="rounded-xl border border-white/20 bg-white/10 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-200">Backend Logs</p>
            <div className="mt-2 space-y-2">
              {logs.map((entry, index) => (
                <div
                  key={entry.id}
                  className="animate-rise rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-100 transition"
                  style={{ animationDelay: `${index * 60}ms` }}
                >
                  <div className="flex items-center justify-between text-[11px] text-slate-300">
                    <span>{entry.time}</span>
                    <span>pipeline</span>
                  </div>
                  <p className="mt-1 text-sm text-slate-100">{entry.message}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {job?.status === "completed" ? (
          <div className="space-y-3 rounded-xl border border-white/20 bg-white/10 p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-white">Generated Files</p>
              <Button variant="outline" size="sm" onClick={() => void loadGeneratedFiles(job.job_id)} disabled={isLoadingFiles}>
                {isLoadingFiles ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                Refresh Files
              </Button>
            </div>

            {generatedFiles.length > 0 ? (
              <div className="grid gap-2">
                {generatedFiles.map((file) => (
                  <button
                    key={file.path}
                    onClick={() => void loadFileContent(file.path)}
                    className="rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-left text-xs text-slate-100 transition-colors hover:bg-white/20"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span>{file.path}</span>
                      <span className="text-slate-300">{file.size ? `${file.size} B` : ""}</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-300">No generated files available yet.</p>
            )}

            {selectedFilePath ? (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-slate-100">Preview: {selectedFilePath}</p>
                <pre className="max-h-72 overflow-auto rounded-lg border border-white/20 bg-slate-950/80 p-3 text-xs text-slate-100">
                  {isLoadingFileContent ? "Loading file content..." : selectedFileContent}
                </pre>
              </div>
            ) : null}
          </div>
        ) : null}

        {error ? <p className="text-xs font-medium text-rose-200">{error}</p> : null}
      </CardContent>
    </Card>
  )
}
