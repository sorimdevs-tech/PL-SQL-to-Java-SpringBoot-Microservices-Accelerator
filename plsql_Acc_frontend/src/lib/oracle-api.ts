import type {
  OracleConnectionPayload,
  OracleConvertPayload,
  OracleObjectsPayload,
} from "@/types/oracle-api"

const API_BASE_URL = "http://127.0.0.1:8001"

function toApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

async function postOracle<TRequest, TResponse>(url: string, payload: TRequest): Promise<TResponse> {
  const response = await fetch(toApiUrl(url), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })

  if (response.ok) {
    return (await response.json()) as TResponse
  }

  const rawBody = await response.text()
  try {
    const parsed = JSON.parse(rawBody) as { detail?: unknown }
    if (Array.isArray(parsed.detail)) {
      const issues = parsed.detail
        .map((item) => {
          if (!item || typeof item !== "object") {
            return null
          }
          const entry = item as { loc?: unknown[]; msg?: string }
          const fieldName = Array.isArray(entry.loc) ? entry.loc[entry.loc.length - 1] : null
          if (typeof fieldName === "string" && typeof entry.msg === "string") {
            return `${fieldName}: ${entry.msg}`
          }
          return typeof entry.msg === "string" ? entry.msg : null
        })
        .filter((value): value is string => Boolean(value))
      if (issues.length > 0) {
        throw new Error(issues.join("; "))
      }
    }
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      throw new Error(parsed.detail)
    }
  } catch (error) {
    if (error instanceof Error) {
      throw error
    }
  }

  throw new Error(rawBody || `Request failed with status ${response.status}`)
}

export function testOracleConnection(payload: OracleConnectionPayload) {
  return postOracle<OracleConnectionPayload, unknown>("/api/db/oracle/test-connection", payload)
}

export function listOracleDatabases(payload: OracleConnectionPayload) {
  return postOracle<OracleConnectionPayload, unknown>("/api/db/oracle/databases", payload)
}

export function listOracleSchemas(payload: OracleConnectionPayload) {
  return postOracle<OracleConnectionPayload, unknown>("/api/db/oracle/schemas", payload)
}

export function listOracleObjects(payload: OracleObjectsPayload) {
  return postOracle<OracleObjectsPayload, unknown>("/api/db/oracle/objects", payload)
}

export function startOracleConvert(payload: OracleConvertPayload) {
  return postOracle<OracleConvertPayload, unknown>("/api/db/oracle/convert", payload)
}
