export interface SqlDiscoveryUploadResponse {
  file_id: string
  filename: string
  size: number
  created_at: string
}

export interface SqlParameter {
  name: string
  type: string
}

export interface SqlLocalVariable {
  name: string
  type: string
}

export interface SqlDiscoveryObject {
  procedureName: string
  objectType: string
}

export interface SqlComplexityMetrics {
  linesOfCode: number
  numberOfQueries: number
  numberOfConditions: number
  numberOfLoops: number
}

export interface SqlDependencyGraph {
  tablesUsed: string[]
  proceduresCalled: string[]
}

export interface SqlConversionPreview {
  entities: string[]
  repositories: string[]
  services: string[]
  controllers: string[]
  dtos: string[]
}

export interface SqlTableDetail {
  name: string
  columns: string[]
}

export interface SqlTableRelationship {
  fromTable: string
  fromColumn: string
  toTable: string
  toColumn: string
}

export interface SqlTableDetails {
  tables: SqlTableDetail[]
  relationships: SqlTableRelationship[]
}

export interface GitTreeEntry {
  name: string
  path: string
  type: "dir" | "file"
}

export interface GitRepoTreeResponse {
  path: string
  entries: GitTreeEntry[]
  count?: number
}

export interface SqlDiscoveryAnalyzeResponse {
  procedureName: string
  objectType: string
  parameters?: {
    in?: SqlParameter[]
    out?: SqlParameter[]
  }
  tablesUsed?: string[]
  operations?: string[]
  localVariables?: SqlLocalVariable[]
  exceptions?: string[]
  complexity?: SqlComplexityMetrics
  dependencyGraph?: SqlDependencyGraph
  conversionPreview?: SqlConversionPreview
  tableDetails?: SqlTableDetails
  objects?: SqlDiscoveryObject[]
  count?: number
  source?: string
}
