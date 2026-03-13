import { useCallback, useEffect, useState } from "react"
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
import type { ConversionJob, GeneratedFile } from "@/types/jobs-api"

type SourceMethod = "git" | "oracle" | "sqlfile"

export interface ConversionSnapshot {
  jobId: string
  status: string
  outputDirectory: string
  generatedFiles: string[]
  backendSummary?: string
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

  const isPolling = job?.status === "queued" || job?.status === "running"

  useEffect(() => {
    if (!job?.job_id) {
      onSnapshotChange(null)
      return
    }
    onSnapshotChange({
      jobId: job.job_id,
      status: job.status,
      outputDirectory:
        job.result?.output_directory ?? job.output_directory ?? "Output directory not available yet",
      generatedFiles: generatedFiles.map((file) => file.path),
      backendSummary: job.result?.summary,
    })
  }, [generatedFiles, job, onSnapshotChange])

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

    try {
      setIsStarting(true)
      let createdJob: ConversionJob | null = null
      const configPath = props.dbConfigPath || "config.json"

      if (props.sourceMethod === "sqlfile") {
        if (!props.sourceFile) {
          setError("Select a local SQL file before starting conversion.")
          return
        }
        createdJob = await createFileJob(props.sourceFile, configPath)
      } else if (props.sourceMethod === "git") {
        if (!props.gitRepoUrl.trim()) {
          setError("Enter a valid Git repository URL.")
          return
        }
        if (isBackendHealthy === false) {
          setError("Backend health check failed. Ensure API server is running before starting Git conversion.")
          return
        }
        createdJob = await createGitJob(props.gitRepoUrl.trim(), configPath)
      } else {
        const response = await startOracleConvert({
          host: props.dbHost.trim(),
          port: Number(props.dbPort),
          service_name: props.dbServiceName.trim(),
          username: props.dbUsername.trim(),
          password: props.dbPassword,
          config_path: configPath,
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
          <Button
            variant="secondary"
            onClick={startConversion}
            disabled={isStarting || (props.sourceMethod === "git" && (isCheckingHealth || isBackendHealthy === false))}
          >
            {isStarting ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Play className="h-4 w-4" />
                Start Conversion
              </>
            )}
          </Button>
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
