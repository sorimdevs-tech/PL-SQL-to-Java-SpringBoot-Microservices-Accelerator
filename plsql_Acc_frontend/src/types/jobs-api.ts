export interface DatabaseJobRequest {
  host: string
  port: string
  serviceName: string
  username: string
  password: string
  configPath?: string
}

export interface OutputConfigOverrides {
  project_name?: string
  group_id?: string
  artifact_id?: string
  package_name?: string
  description?: string
  java_version?: string
  spring_boot_version?: string
  build_tool?: "maven" | "gradle" | "mvn"
  packaging?: "jar" | "war"
  config_format?: "properties" | "yaml"
  target_directory?: string
  dependencies?: string[]
}

export interface ConfigOverrides {
  output?: OutputConfigOverrides
}

export interface GitHubOutputConfig {
  repo_url: string
  branch?: string
  target_path?: string
  access_token?: string
  username?: string
  commit_message?: string
}

export interface GitHubPublishResult {
  published: boolean
  repo_url: string
  branch: string
  target_path: string
  message?: string
  commit_message?: string
  commit_hash?: string
}

export interface JobResult {
  output_directory?: string
  generated_files?: string[]
  summary?: string
  artifacts?: Record<string, unknown>
  github_publish?: GitHubPublishResult
}

export interface ConversionJob {
  job_id: string
  source_type: string
  source_value?: string
  status: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  error: string | null
  result: JobResult | null
  output_directory: string | null
  github_output?: GitHubOutputConfig | null
  download_url: string | null
  files_url: string | null
}

export interface GeneratedFile {
  path: string
  size?: number
}

export interface FilesResponse {
  job_id?: string
  output_directory?: string
  files: GeneratedFile[] | string[]
}

export interface FileContentResponse {
  job_id?: string
  path?: string
  content: string
}
