import type {
  ConversionJob,
  ConfigOverrides,
  DatabaseJobRequest,
  FileContentResponse,
  FilesResponse,
  GeneratedFile,
  GitHubRepoBranchesResponse,
  GitHubOutputConfig,
} from "@/types/jobs-api"

const API_BASE_URL = "http://127.0.0.1:8001"

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
  githubOutput?: GitHubOutputConfig,
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
      github_output: githubOutput,
    }),
  })

  return parseResponse<ConversionJob>(response)
}

export async function createFileJob(
  file: File,
  configPath = "config.json",
  configOverrides?: ConfigOverrides,
  outputDirectory?: string,
  githubOutput?: GitHubOutputConfig,
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
  if (githubOutput) {
    formData.append("github_output", JSON.stringify(githubOutput))
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
  githubOutput?: GitHubOutputConfig,
): Promise<ConversionJob> {
  const response = await fetch(toApiUrl("/api/jobs/git"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_url: repoUrl,
      config_path: configPath,
      config_overrides: configOverrides,
      output_directory: outputDirectory,
      github_output: githubOutput,
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

export async function getJobLogs(jobId: string, limit = 200): Promise<{ lines: string[]; status?: string }> {
  const query = new URLSearchParams({ limit: String(limit) }).toString()
  const response = await fetch(toApiUrl(`/api/jobs/${jobId}/logs?${query}`))
  const data = await parseResponse<{ lines?: string[]; status?: string }>(response)
  return { lines: data.lines ?? [], status: data.status }
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

function parseGitHubRepository(repoUrl: string): { owner: string; repo: string } | null {
  try {
    const parsed = new URL(repoUrl)
    if (parsed.hostname.toLowerCase() !== "github.com") {
      return null
    }

    const segments = parsed.pathname.split("/").filter(Boolean)
    if (segments.length < 2) {
      return null
    }

    return {
      owner: segments[0],
      repo: segments[1].replace(/\.git$/i, ""),
    }
  } catch {
    return null
  }
}

async function getGitHubRepoBranchesFromGitHub(
  repoUrl: string,
  accessToken?: string,
): Promise<GitHubRepoBranchesResponse> {
  const repoInfo = parseGitHubRepository(repoUrl)
  if (!repoInfo) {
    throw new Error("Fetch Repo fallback only supports github.com repository URLs.")
  }

  const headers: HeadersInit = {
    Accept: "application/vnd.github+json",
  }
  if (accessToken?.trim()) {
    headers.Authorization = `Bearer ${accessToken.trim()}`
  }

  const repoResponse = await fetch(`https://api.github.com/repos/${repoInfo.owner}/${repoInfo.repo}`, {
    headers,
  })
  if (!repoResponse.ok) {
    const message = await repoResponse.text()
    throw new Error(message || `GitHub repo request failed with status ${repoResponse.status}`)
  }

  const repoData = (await repoResponse.json()) as { default_branch?: string }

  const branchesResponse = await fetch(
    `https://api.github.com/repos/${repoInfo.owner}/${repoInfo.repo}/branches?per_page=100`,
    { headers },
  )
  if (!branchesResponse.ok) {
    const message = await branchesResponse.text()
    throw new Error(message || `GitHub branches request failed with status ${branchesResponse.status}`)
  }

  const branchesData = (await branchesResponse.json()) as Array<{ name?: string }>
  const branches = branchesData.map((branch) => branch.name).filter((name): name is string => Boolean(name))
  const defaultBranch = repoData.default_branch
  const orderedBranches = [...branches]
  if (defaultBranch && orderedBranches.includes(defaultBranch)) {
    orderedBranches.splice(orderedBranches.indexOf(defaultBranch), 1)
    orderedBranches.unshift(defaultBranch)
  }

  return {
    repo_url: repoUrl,
    default_branch: defaultBranch,
    branches: orderedBranches,
    count: orderedBranches.length,
  }
}

export async function getGitHubRepoBranches(
  repoUrl: string,
  accessToken?: string,
): Promise<GitHubRepoBranchesResponse> {
  const response = await fetch(toApiUrl("/api/github/branches"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl }),
  })

  if (response.status === 404) {
    return getGitHubRepoBranchesFromGitHub(repoUrl, accessToken)
  }

  return parseResponse<GitHubRepoBranchesResponse>(response)
}

export async function pickOutputDirectory(): Promise<string | null> {
  const response = await fetch(toApiUrl("/api/paths/pick-directory"))
  const data = await parseResponse<{ path?: string | null }>(response)
  return data.path ?? null
}
