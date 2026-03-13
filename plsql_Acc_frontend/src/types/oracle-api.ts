import type { ConfigOverrides } from "./jobs-api"

export interface OracleConnectionPayload {
  host: string
  port: number
  service_name: string
  username: string
  password: string
}

export interface OracleObjectsPayload extends OracleConnectionPayload {
  schema_name: string
  object_types: string[]
}

export interface OracleConvertPayload extends OracleConnectionPayload {
  config_path: string
  config_overrides?: ConfigOverrides
  output_directory?: string
}

export interface OracleObjectItem {
  name: string
  type: string
  owner?: string
}
