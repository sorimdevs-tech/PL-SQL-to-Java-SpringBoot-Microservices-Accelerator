export interface SqlDiscoveryUploadResponse {
  file_id: string
  filename: string
  size: number
  created_at: string
}

export interface SqlParameter {
  name: string
  type: string
  direction?: string
}

export interface SqlLocalVariable {
  name: string
  type: string
}

export interface SqlDiscoveryObject {
  procedureName: string
  objectType: string
  parameters?: {
    in?: SqlParameter[]
    out?: SqlParameter[]
  }
  tablesUsed?: string[]
  operations?: string[]
  operationsByTable?: Record<string, string[]>
  localVariables?: SqlLocalVariable[]
  exceptions?: string[]
  exceptionSources?: SqlExceptionSource[]
  businessRules?: SqlBusinessRule[]
  dataFlow?: SqlDataFlow[]
  variableSemantics?: SqlVariableSemantic[]
  dependencies?: string[]
  complexity?: SqlComplexityMetrics
  dependencyGraph?: SqlDependencyGraph
  conversionPreview?: SqlConversionPreview
  tableDetails?: SqlTableDetails
  unusedVariables?: SqlUnusedVariable[]
  idGeneration?: SqlIdGeneration
  transaction?: SqlTransactionSummary
  issues?: SqlProcedureIssue[]
  dependencyChain?: string[]
  bulkOperations?: SqlBulkOperation[]
  cursor?: SqlCursorPattern
  retryLogic?: SqlRetryLogic
  errorHandling?: SqlErrorHandling
  performancePatterns?: string[]
  collections?: SqlCollectionVariable[]
}

export interface SqlComplexityMetrics {
  linesOfCode: number
  numberOfQueries: number
  numberOfConditions: number
  numberOfLoops: number
  level?: string
  type?: string
}

export interface SqlDependencyGraph {
  tablesUsed: string[]
  proceduresCalled: string[]
  sequencesUsed?: string[]
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

export interface SqlBusinessRule {
  condition: string
  action?: string
  true_action: string
  false_action?: string
  type?: string
  pattern?: string
  severity?: string
}

export interface SqlDataFlow {
  type?: string
  variable: string
  source: string
  source_table?: string
  source_column?: string
  target?: string
  used?: boolean
  semantic_type?: string
}

export interface SqlUnusedVariable {
  name: string
  type: string
  reason: string
  source?: string
}

export interface SqlExceptionSource {
  statement: string
  exceptions: string[]
  certainty?: string
  reason: string
}

export interface SqlVariableSemantic {
  variable: string
  type: string
}

export interface SqlIdGeneration {
  uses_sequence: boolean
  input_id_provided: boolean
  conflict: boolean
  pattern?: string
  strategy?: string
  impact?: string
  details: string
}

export interface SqlTransactionSummary {
  required: boolean
  type?: string
  reason: string
  features?: string[]
  risk?: string
  has_savepoint?: boolean
  has_partial_rollback?: boolean
  has_commit?: boolean
  has_rollback?: boolean
}

export interface SqlProcedureIssue {
  type: string
  details: string
  impact?: string
}

export interface SqlBulkOperation {
  type: string
  operation?: string
  cursor?: string
  target?: string
  table?: string
  source?: string
  limit?: string
  batch_size?: string
  save_exceptions?: boolean
}

export interface SqlCursorPattern {
  type: string
  locking?: string
  purpose?: string
}

export interface SqlRetryLogic {
  enabled: boolean
  uses_goto?: boolean
  max_attempts?: number | null
  pattern?: string
}

export interface SqlErrorHandling {
  type: string
  mechanism?: string
  behavior?: string
}

export interface SqlCollectionVariable {
  name: string
  type: string
  declared_type?: string
  element_type?: string
  index_by?: string
  source_table?: string
}

export interface SqlSchemaColumn {
  name: string
  type: string
}

export interface SqlSchemaForeignKey {
  source_column: string
  target_table: string
  target_column: string
}

export interface SqlSchemaTable {
  name: string
  columns: SqlSchemaColumn[]
  primary_keys: string[]
  foreign_keys: SqlSchemaForeignKey[]
}

export interface SqlSchemaRelationship {
  source_table: string
  source_column: string
  target_table: string
  target_column: string
}

export interface SqlSequenceDefinition {
  name: string
}

export interface SqlSequenceMapping {
  sequence_name: string
  mapped_table: string
}

export interface SqlDiscoverySchema {
  tables: SqlSchemaTable[]
  relationships: SqlSchemaRelationship[]
  sequences: SqlSequenceDefinition[]
  sequence_mapping: SqlSequenceMapping[]
}

export interface SqlDiscoveryProcedure {
  name: string
  object_type: string
  parameters: SqlParameter[]
  input_parameters: SqlParameter[]
  output_parameters: SqlParameter[]
  variables: SqlLocalVariable[]
  tables_used: string[]
  operations: Record<string, string[]>
  data_flow: SqlDataFlow[]
  business_rules: SqlBusinessRule[]
  dependencies: string[]
  exceptions?: string[]
  exception_sources?: SqlExceptionSource[]
  variable_semantics?: SqlVariableSemantic[]
  dependency_graph?: {
    tables_used: string[]
    procedures_called: string[]
    sequences_used?: string[]
  }
  table_details?: {
    tables: {
      name: string
      columns: string[]
      primary_keys: string[]
      foreign_keys: SqlSchemaForeignKey[]
    }[]
    relationships: SqlSchemaRelationship[]
  }
  complexity?: SqlComplexityMetrics
  unused_variables?: SqlUnusedVariable[]
  id_generation?: SqlIdGeneration
  transaction?: SqlTransactionSummary
  issues?: SqlProcedureIssue[]
  dependency_chain?: string[]
  bulk_operations?: SqlBulkOperation[]
  cursor?: SqlCursorPattern
  retry_logic?: SqlRetryLogic
  error_handling?: SqlErrorHandling
  performance_patterns?: string[]
  collections?: SqlCollectionVariable[]
}

export interface SqlDiscoveryModel {
  schema: SqlDiscoverySchema
  procedures: SqlDiscoveryProcedure[]
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

export interface DependencySuggestionRequest {
  procedure_name?: string
  object_type?: string
  tables_used?: string[]
  operations?: string[]
  parameters_in?: { name: string; type: string }[]
  parameters_out?: { name: string; type: string }[]
  local_variables?: { name: string; type: string }[]
  exceptions?: string[]
}

export interface DependencySuggestionResponse {
  suggestions: { name: string; reason: string; coordinate?: string }[]
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
  operationsByTable?: Record<string, string[]>
  localVariables?: SqlLocalVariable[]
  exceptions?: string[]
  exceptionSources?: SqlExceptionSource[]
  businessRules?: SqlBusinessRule[]
  dataFlow?: SqlDataFlow[]
  variableSemantics?: SqlVariableSemantic[]
  dependencies?: string[]
  complexity?: SqlComplexityMetrics
  dependencyGraph?: SqlDependencyGraph
  conversionPreview?: SqlConversionPreview
  tableDetails?: SqlTableDetails
  unusedVariables?: SqlUnusedVariable[]
  idGeneration?: SqlIdGeneration
  transaction?: SqlTransactionSummary
  issues?: SqlProcedureIssue[]
  dependencyChain?: string[]
  bulkOperations?: SqlBulkOperation[]
  cursor?: SqlCursorPattern
  retryLogic?: SqlRetryLogic
  errorHandling?: SqlErrorHandling
  performancePatterns?: string[]
  collections?: SqlCollectionVariable[]
  discovery?: SqlDiscoveryModel
  objects?: SqlDiscoveryObject[]
  count?: number
  source?: string
}
