/**
 * Package Deduplication Utilities
 * 
 * This module provides strict deduplication logic for PL/SQL packages
 * to prevent React key collision errors when backend sends duplicates.
 * 
 * RULE 1: Deduplicate data BEFORE map/render
 * RULE 2: Use stable, unique keys (NEVER use index alone)
 * RULE 3: Defensive deduplication (don't trust backend)
 * RULE 4: Stable keys that don't change between renders
 * RULE 5: Type-safe TypeScript implementation
 */

/**
 * Represents a PL/SQL package with deduplication awareness.
 * Can contain both spec (.pks) and body (.pkb) information.
 */
export type Package = {
  /** Package name (stripped of .pks/.pkb extension) */
  name: string
  /** Source indicator: "spec", "body", or "merged" */
  source?: "spec" | "body" | "merged"
  /** Whether package has spec file */
  has_spec?: boolean
  /** Whether package has body file */
  has_body?: boolean
  /** Cursor complexity count */
  cursor_count?: number
  /** Retry logic count */
  retry_count?: number
  /** Tables used by this package */
  tables_used?: string[]
  /** Exceptions handled */
  exceptions?: string[]
  /** Additional metadata that shouldn't affect deduplication */
  [key: string]: unknown
}

/**
 * Represents a package after deduplication.
 * Guaranteed to be unique by name.
 */
export type DedupedPackage = Required<
  Pick<Package, "name" | "source">
> &
  Omit<Package, "name" | "source">

/**
 * Extract package name from filename, removing .pks/.pkb extensions.
 *
 * @example
 * extractPackageName("appl_error_pkg.pks") // "appl_error_pkg"
 * extractPackageName("appl_error_pkg.pkb") // "appl_error_pkg"
 * extractPackageName("appl_error_pkg") // "appl_error_pkg"
 */
export function extractPackageName(filename: string): string {
  return filename.replace(/\.(pks|pkb)$/i, "").trim()
}

/**
 * Determine the source type (.pks = spec, .pkb = body).
 *
 * @example
 * determineSource("appl_error_pkg.pks") // "spec"
 * determineSource("appl_error_pkg.pkb") // "body"
 */
export function determineSource(
  filename: string
): "spec" | "body" | "merged" | "unknown" {
  const lower = filename.toLowerCase()
  if (lower.endsWith(".pks")) return "spec"
  if (lower.endsWith(".pkb")) return "body"
  if (filename === "merged") return "merged"
  return "unknown"
}

/**
 * Deduplicate an array of packages.
 *
 * RULE 1: Merges .pks and .pkb into single entry by package name
 * RULE 2: Uses Map for O(n) deduplication
 * RULE 3: Defensive - works even if backend sends duplicates
 * RULE 4: Preserves data from both spec and body files
 *
 * @param packages - Input array that may contain duplicates
 * @returns Array of unique packages with stable keys
 *
 * @example
 * const input = [
 *   { name: "appl_error_pkg.pks", cursor_count: 0 },
 *   { name: "appl_error_pkg.pkb", cursor_count: 0 }
 * ]
 * const deduped = dedupePackages(input)
 * // Result: [{ name: "appl_error_pkg", has_spec: true, has_body: true, ... }]
 */
export function dedupePackages(packages: Package[]): DedupedPackage[] {
  const packageMap = new Map<string, DedupedPackage>()

  for (const pkg of packages) {
    const name = extractPackageName(pkg.name)
    const source = determineSource(pkg.name)

    // Get existing entry or create new one
    let existing = packageMap.get(name)
    if (!existing) {
      existing = {
        name,
        source: "merged",
        has_spec: false,
        has_body: false,
        ...pkg,
      } as DedupedPackage
      packageMap.set(name, existing)
    }

    // Merge source information
    if (source === "spec") {
      existing.has_spec = true
    } else if (source === "body") {
      existing.has_body = true
    }

    // Merge package data (body data takes precedence as it has implementation)
    if (source === "body") {
      existing.cursor_count = Math.max(
        existing.cursor_count ?? 0,
        pkg.cursor_count ?? 0
      )
      existing.retry_count = Math.max(
        existing.retry_count ?? 0,
        pkg.retry_count ?? 0
      )
      existing.tables_used = Array.from(
        new Set([...(existing.tables_used ?? []), ...(pkg.tables_used ?? [])])
      )
      existing.exceptions = Array.from(
        new Set([...(existing.exceptions ?? []), ...(pkg.exceptions ?? [])])
      )
    }
  }

  // Convert Map to sorted array for stable rendering
  return Array.from(packageMap.values()).sort((a, b) =>
    a.name.localeCompare(b.name)
  )
}

/**
 * Generate a stable, unique React key for a package.
 *
 * RULE 2: Use this instead of simple package name keys
 * RULE 4: Key is stable and won't change between renders
 *
 * Format: "PACKAGE::{name}" (e.g., "PACKAGE::appl_error_pkg")
 *
 * @example
 * const pkg = { name: "appl_error_pkg", has_spec: true }
 * const key = generatePackageKey(pkg) // "PACKAGE::appl_error_pkg"
 */
export function generatePackageKey(pkg: DedupedPackage): string {
  return `PACKAGE::${pkg.name}`
}

/**
 * Deduplicate AND generate keys in one pass.
 * Useful for mapping to JSX elements directly.
 *
 * @returns Array of deduplicated packages with stable keys
 */
export function dedupePackagesWithKeys(
  packages: Package[]
): (DedupedPackage & { key: string })[] {
  return dedupePackages(packages).map((pkg) => ({
    ...pkg,
    key: generatePackageKey(pkg),
  }))
}

/**
 * Verify that an array of packages has no duplicates by name.
 * Useful for debugging and assertions.
 *
 * @returns true if all package names are unique
 */
export function verifyNoDuplicates(packages: Package[]): boolean {
  const names = new Set<string>()
  for (const pkg of packages) {
    const name = extractPackageName(pkg.name)
    if (names.has(name)) return false
    names.add(name)
  }
  return true
}

/**
 * Get deduplication statistics for debugging.
 *
 * @example
 * const stats = getDedupeStats(packages)
 * console.log(`${stats.duplicatesFound} duplicates removed`)
 */
export function getDedupeStats(packages: Package[]): {
  originalCount: number
  deduplicatedCount: number
  duplicatesFound: number
  packageNames: string[]
} {
  const deduped = dedupePackages(packages)
  return {
    originalCount: packages.length,
    deduplicatedCount: deduped.length,
    duplicatesFound: packages.length - deduped.length,
    packageNames: deduped.map((p) => p.name),
  }
}

/**
 * Type guard: Check if value is a valid Package.
 */
export function isPackage(value: unknown): value is Package {
  if (typeof value !== "object" || value === null) return false
  const pkg = value as Partial<Package>
  return typeof pkg.name === "string"
}

/**
 * Type guard: Check if array contains only packages.
 */
export function isPackageArray(value: unknown): value is Package[] {
  return (
    Array.isArray(value) &&
    value.every((item) => isPackage(item))
  )
}
