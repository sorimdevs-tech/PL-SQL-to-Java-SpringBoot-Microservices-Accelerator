import type {
  OracleConnectionPayload,
  OracleConvertPayload,
  OracleObjectsPayload,
} from "@/types/oracle-api"

const API_BASE_URL = "http://127.0.0.1:8000"

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

  const message = await response.text()
  throw new Error(message || `Request failed with status ${response.status}`)
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
