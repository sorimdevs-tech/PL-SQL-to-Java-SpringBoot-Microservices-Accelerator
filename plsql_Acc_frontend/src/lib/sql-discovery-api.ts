import type { SqlDiscoveryAnalyzeResponse, SqlDiscoveryUploadResponse } from "@/types/sql-discovery-api"

const API_BASE_URL = "http://127.0.0.1:8000"

function toApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T
  }

  const message = await response.text()
  throw new Error(message || `Request failed with status ${response.status}`)
}

export async function uploadSqlDiscoveryFile(file: File): Promise<SqlDiscoveryUploadResponse> {
  const formData = new FormData()
  formData.append("source_file", file)

  const response = await fetch(toApiUrl("/api/discovery/upload"), {
    method: "POST",
    body: formData,
  })

  return parseJsonResponse<SqlDiscoveryUploadResponse>(response)
}

export async function analyzeUploadedSqlFile(fileId: string): Promise<SqlDiscoveryAnalyzeResponse> {
  const response = await fetch(toApiUrl("/api/discovery/analyze"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId }),
  })

  return parseJsonResponse<SqlDiscoveryAnalyzeResponse>(response)
}
