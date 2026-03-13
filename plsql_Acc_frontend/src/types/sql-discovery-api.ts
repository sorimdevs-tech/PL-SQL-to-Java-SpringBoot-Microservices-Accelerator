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
  objects?: SqlDiscoveryObject[]
  count?: number
  source?: string
}
