export interface OracleTestConnectionRequest {
  host: string
  port: number
  service_name: string
  username: string
  password: string
}

export interface OracleTestConnectionResponse {
  connected?: boolean
  message?: string
}

export interface DiscoveryContainer {
  name: string
  type: string
  openMode?: string
}

export interface DiscoveryContainersResponse {
  containers: DiscoveryContainer[]
  count: number
}

export interface DiscoverySchemasResponse {
  schemas: string[]
  count: number
}

export interface DiscoveryObject {
  name: string
  type: string
  schema: string
}

export interface DiscoveryObjectsResponse {
  objects: DiscoveryObject[]
  count: number
}

export interface DiscoveryParameter {
  name: string
  type: string
}

export interface DiscoveryLocalVariable {
  name: string
  type: string
}

export interface DiscoveryComplexity {
  linesOfCode: number
  numberOfQueries: number
  numberOfConditions: number
  numberOfLoops: number
}

export interface DiscoveryDependencyGraph {
  tablesUsed: string[]
  proceduresCalled: string[]
}

export interface DiscoveryConversionPreview {
  entities: string[]
  repositories: string[]
  services: string[]
  controllers: string[]
  dtos: string[]
}

export interface DiscoveryAnalyzeObject {
  procedureName: string
  objectType: string
}

export interface DiscoveryAnalyzeResponse {
  procedureName: string
  objectType: string
  parameters?: {
    in?: DiscoveryParameter[]
    out?: DiscoveryParameter[]
  }
  tablesUsed?: string[]
  operations?: string[]
  localVariables?: DiscoveryLocalVariable[]
  exceptions?: string[]
  complexity?: DiscoveryComplexity
  dependencyGraph?: DiscoveryDependencyGraph
  conversionPreview?: DiscoveryConversionPreview
  objects?: DiscoveryAnalyzeObject[]
  count?: number
  source?: string
}

export interface DiscoveryUploadResponse {
  file_id: string
  filename: string
  size: number
  created_at: string
}

export interface DiscoveryAnalyzeByFileRequest {
  file_id: string
}

export interface DiscoveryAnalyzeByGitRequest {
  repo_url: string
  branch?: string
  path_filters?: string[]
}
