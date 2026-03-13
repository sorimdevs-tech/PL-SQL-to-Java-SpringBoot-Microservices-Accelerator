import type {
  ConversionJob,
  ConfigOverrides,
  DatabaseJobRequest,
  FileContentResponse,
  FilesResponse,
  GeneratedFile,
} from "@/types/jobs-api"

const API_BASE_URL = "http://127.0.0.1:8000"

function toApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

function buildConnectionString({
  host,
  port,
  serviceName,
  username,
  password,
}: Omit<DatabaseJobRequest, "configPath">) {
  const encodedUsername = encodeURIComponent(username)
  const encodedPassword = encodeURIComponent(password)
  return `oracle://${encodedUsername}:${encodedPassword}@${host}:${port}/${serviceName}`
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T
  }

  const message = await response.text()
  throw new Error(message || `Request failed with status ${response.status}`)
}

export async function createDatabaseJob(
  payload: DatabaseJobRequest,
  configOverrides?: ConfigOverrides,
  outputDirectory?: string,
): Promise<ConversionJob> {
  const connectionString = buildConnectionString(payload)

  const response = await fetch(toApiUrl("/api/jobs/database"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      connection_string: connectionString,
      config_path: payload.configPath ?? "config.json",
      config_overrides: configOverrides,
      output_directory: outputDirectory,
    }),
  })

  return parseResponse<ConversionJob>(response)
}

export async function createFileJob(
  file: File,
  configPath = "config.json",
  configOverrides?: ConfigOverrides,
  outputDirectory?: string,
): Promise<ConversionJob> {
  const formData = new FormData()
  formData.append("source_file", file)
  formData.append("config_path", configPath)
  if (configOverrides) {
    formData.append("config_overrides", JSON.stringify(configOverrides))
  }
  if (outputDirectory) {
    formData.append("output_directory", outputDirectory)
  }

  const response = await fetch(toApiUrl("/api/jobs/file"), {
    method: "POST",
    body: formData,
  })

  return parseResponse<ConversionJob>(response)
}

export async function createGitJob(
  repoUrl: string,
  configPath = "config.json",
  configOverrides?: ConfigOverrides,
  outputDirectory?: string,
): Promise<ConversionJob> {
  const response = await fetch(toApiUrl("/api/jobs/git"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_url: repoUrl,
      config_path: configPath,
      config_overrides: configOverrides,
      output_directory: outputDirectory,
    }),
  })

  return parseResponse<ConversionJob>(response)
}

export async function getJobStatus(jobId: string): Promise<ConversionJob> {
  const response = await fetch(toApiUrl(`/api/jobs/${jobId}`))
  return parseResponse<ConversionJob>(response)
}

export async function getJobFiles(jobId: string): Promise<GeneratedFile[]> {
  const response = await fetch(toApiUrl(`/api/jobs/${jobId}/files`))
  const data = await parseResponse<FilesResponse | string[]>(response)
  const rawFiles = Array.isArray(data) ? data : data.files
  return rawFiles.map((item) => {
    if (typeof item === "string") {
      return { path: item }
    }
    return {
      path: item.path,
      size: item.size,
    }
  })
}

export async function getJobFileContent(jobId: string, path: string): Promise<string> {
  const query = new URLSearchParams({ path }).toString()
  const response = await fetch(toApiUrl(`/api/jobs/${jobId}/file-content?${query}`))
  if (response.ok) {
    const contentType = response.headers.get("content-type") ?? ""
    if (contentType.includes("application/json")) {
      const json = (await response.json()) as FileContentResponse
      return json.content
    }
    return response.text()
  }
  const message = await response.text()
  throw new Error(message || `Request failed with status ${response.status}`)
}

export function getJobDownloadUrl(jobId: string): string {
  return toApiUrl(`/api/jobs/${jobId}/download`)
}

export async function getBackendHealth(): Promise<{ status: string }> {
  const response = await fetch(toApiUrl("/health"))
  return parseResponse<{ status: string }>(response)
}

export async function pickOutputDirectory(): Promise<string | null> {
  const response = await fetch(toApiUrl("/api/paths/pick-directory"))
  const data = await parseResponse<{ path?: string | null }>(response)
  return data.path ?? null
}
