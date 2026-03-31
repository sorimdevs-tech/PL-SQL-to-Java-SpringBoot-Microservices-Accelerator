export interface ParsedGitHubRepoInput {
  repoUrl: string
  branch?: string
}

export function parseGitHubRepoInput(rawValue: string): ParsedGitHubRepoInput {
  const trimmed = rawValue.trim()
  if (!trimmed) {
    return { repoUrl: "" }
  }

  try {
    const url = new URL(trimmed)
    const pathSegments = url.pathname.split("/").filter(Boolean)

    if (url.hostname.toLowerCase() === "github.com" && pathSegments.length >= 2) {
      const owner = pathSegments[0]
      const repo = pathSegments[1].replace(/\.git$/i, "")
      const normalized = `${url.protocol}//${url.host}/${owner}/${repo}.git`

      if (pathSegments[2] === "tree" && pathSegments[3]) {
        return {
          repoUrl: normalized,
          branch: decodeURIComponent(pathSegments[3]),
        }
      }

      return { repoUrl: normalized }
    }
  } catch {
    return { repoUrl: trimmed }
  }

  return { repoUrl: trimmed }
}
