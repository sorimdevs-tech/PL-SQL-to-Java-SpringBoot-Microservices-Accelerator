import type {
  DiscoveryAnalyzeByFileRequest,
  DiscoveryAnalyzeByGitRequest,
  DiscoveryAnalyzeResponse,
  DiscoveryContainersResponse,
  DiscoveryObjectsResponse,
  DiscoverySchemasResponse,
  DiscoveryUploadResponse,
  OracleTestConnectionRequest,
  OracleTestConnectionResponse,
} from "@/types/discovery"

const API_BASE_URL = "http://127.0.0.1:8000"

function toApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

export class DiscoveryApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function extractDetail(text: string): string {
  try {
    const parsed = JSON.parse(text) as { detail?: string }
    if (parsed && typeof parsed.detail === "string") {
      return parsed.detail
    }
  } catch {
    // Fall back to raw text when the backend doesn't return JSON.
  }
  return text
}

async function parseJson<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T
  }

  const rawText = await response.text()
  const detail = extractDetail(rawText)
  const mapped =
    response.status === 400
      ? detail.includes("Connect step is required")
        ? `Validation/connect step missing: ${detail}`
        : detail.includes("Unable to parse")
          ? `Parse/analyze issue: ${detail}`
          : detail || "Bad request"
      : response.status === 403
        ? `Insufficient Oracle privileges: ${detail}`
        : response.status === 404
          ? `Resource not found: ${detail}`
          : response.status === 422
            ? `Parse/analyze issue: ${detail}`
            : response.status === 500
              ? `Server error: ${detail}`
              : detail || `Request failed with status ${response.status}`

  throw new DiscoveryApiError(response.status, mapped)
}

export async function testOracleConnection(payload: OracleTestConnectionRequest): Promise<OracleTestConnectionResponse> {
  const response = await fetch(toApiUrl("/api/db/oracle/test-connection"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  return parseJson<OracleTestConnectionResponse>(response)
}

export async function getDiscoveryContainers(): Promise<DiscoveryContainersResponse> {
  const response = await fetch(toApiUrl("/api/discovery/containers"))
  return parseJson<DiscoveryContainersResponse>(response)
}

export async function getDiscoverySchemas(container?: string): Promise<DiscoverySchemasResponse> {
  const query = container ? `?${new URLSearchParams({ container }).toString()}` : ""
  const response = await fetch(toApiUrl(`/api/discovery/schemas${query}`))
  return parseJson<DiscoverySchemasResponse>(response)
}

export async function getDiscoveryObjects(schema: string, container?: string): Promise<DiscoveryObjectsResponse> {
  const params = new URLSearchParams({ schema })
  if (container) {
    params.set("container", container)
  }
  const response = await fetch(toApiUrl(`/api/discovery/objects?${params.toString()}`))
  return parseJson<DiscoveryObjectsResponse>(response)
}

export async function uploadDiscoveryFile(file: File): Promise<DiscoveryUploadResponse> {
  const formData = new FormData()
  formData.append("source_file", file)
  const response = await fetch(toApiUrl("/api/discovery/upload"), {
    method: "POST",
    body: formData,
  })
  return parseJson<DiscoveryUploadResponse>(response)
}

export async function analyzeDiscovery(
  payload: DiscoveryAnalyzeByFileRequest | DiscoveryAnalyzeByGitRequest,
): Promise<DiscoveryAnalyzeResponse> {
  const response = await fetch(toApiUrl("/api/discovery/analyze"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  return parseJson<DiscoveryAnalyzeResponse>(response)
}

export async function getProcedureDiscovery(
  procedureName: string,
  schema?: string,
  container?: string,
): Promise<DiscoveryAnalyzeResponse> {
  const encoded = encodeURIComponent(procedureName)
  const params = new URLSearchParams()
  if (schema) {
    params.set("schema", schema)
  }
  if (container) {
    params.set("container", container)
  }
  const query = params.toString()
  const response = await fetch(toApiUrl(`/api/discovery/${encoded}${query ? `?${query}` : ""}`))
  return parseJson<DiscoveryAnalyzeResponse>(response)
}
