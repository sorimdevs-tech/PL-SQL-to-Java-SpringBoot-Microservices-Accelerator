/**
 * React Hook: useDeduplicatedPackages
 *
 * Safely manages package deduplication and provides stable data for rendering.
 * Implements all 5 RULES:
 * - RULE 1: Deduplicates BEFORE map
 * - RULE 2: Generates unique, stable keys
 * - RULE 3: Defensive (works even if backend sends duplicates)
 * - RULE 4: Stable keys that don't change between renders
 * - RULE 5: Full TypeScript type safety
 */

import { useMemo } from "react"
import {
  dedupePackages,
  dedupePackagesWithKeys,
  generatePackageKey,
  getDedupeStats,
  verifyNoDuplicates,
  type Package,
  type DedupedPackage,
} from "@/utils/package-deduplication"

/**
 * Hook return type with deduplicated packages and metadata.
 */
export interface UseDeduplicatedPackagesResult {
  /** Array of deduplicated packages, ready for rendering */
  packages: DedupedPackage[]
  /** Same packages with .key property added for React rendering */
  packagesWithKeys: (DedupedPackage & { key: string })[]
  /** Number of duplicates that were removed */
  duplicatesRemoved: number
  /** Total original package count */
  originalCount: number
  /** Whether deduplication was needed */
  hadDuplicates: boolean
  /** Debug helper: statistics about deduplication */
  stats: ReturnType<typeof getDedupeStats>
}

/**
 * Hook to safely deduplicate packages and get rendering-ready data.
 *
 * USAGE:
 * ```tsx
 * const { packages, packagesWithKeys, duplicatesRemoved } = useDeduplicatedPackages(apiResponse.packages)
 *
 * // For dropdowns:
 * <select>
 *   {packagesWithKeys.map(pkg => (
 *     <option key={pkg.key} value={pkg.name}>{pkg.name}</option>
 *   ))}
 * </select>
 *
 * // For tables:
 * <tbody>
 *   {packagesWithKeys.map(pkg => (
 *     <tr key={pkg.key}>
 *       <td>{pkg.name}</td>
 *       <td>{pkg.cursor_count}</td>
 *     </tr>
 *   ))}
 * </tbody>
 * ```
 *
 * @param inputPackages - Raw packages from backend (may contain duplicates)
 * @param verbose - Enable console logging for debugging
 * @returns Object with deduplicated packages and metadata
 */
export function useDeduplicatedPackages(
  inputPackages: Package[] | null | undefined,
  verbose = false
): UseDeduplicatedPackagesResult {
  return useMemo(() => {
    // Handle null/undefined input
    if (!inputPackages || !Array.isArray(inputPackages)) {
      return {
        packages: [],
        packagesWithKeys: [],
        duplicatesRemoved: 0,
        originalCount: 0,
        hadDuplicates: false,
        stats: {
          originalCount: 0,
          deduplicatedCount: 0,
          duplicatesFound: 0,
          packageNames: [],
        },
      }
    }

    // Deduplicate packages
    const deduped = dedupePackages(inputPackages)
    const duplicatesRemoved = inputPackages.length - deduped.length
    const hadDuplicates = duplicatesRemoved > 0
    const stats = getDedupeStats(inputPackages)

    // Debug logging
    if (verbose) {
      console.debug("[useDeduplicatedPackages]", {
        originalCount: inputPackages.length,
        deduplicatedCount: deduped.length,
        duplicatesRemoved,
        hadDuplicates,
        packageNames: deduped.map((p) => p.name),
      })

      if (hadDuplicates) {
        console.warn(
          `⚠️  Backend sent ${duplicatesRemoved} duplicate package(s). Deduplication applied.`
        )
      }

      // Verify no duplicates remain
      if (!verifyNoDuplicates(inputPackages)) {
        console.error(
          "❌ Deduplication failed: Duplicates still present after processing"
        )
      }
    }

    // Create packages with keys
    const packagesWithKeys = deduped.map((pkg) => ({
      ...pkg,
      key: generatePackageKey(pkg),
    }))

    return {
      packages: deduped,
      packagesWithKeys,
      duplicatesRemoved,
      originalCount: inputPackages.length,
      hadDuplicates,
      stats,
    }
  }, [inputPackages, verbose])
}

/**
 * Alternative hook for simple dropdown/select rendering.
 * Returns only the deduplicated packages with keys.
 *
 * USAGE:
 * ```tsx
 * const packages = usePackageOptions(apiResponse.packages)
 * <select>
 *   {packages.map(pkg => (
 *     <option key={pkg.key} value={pkg.name}>{pkg.name}</option>
 *   ))}
 * </select>
 * ```
 */
export function usePackageOptions(
  inputPackages: Package[] | null | undefined
): (DedupedPackage & { key: string })[] {
  return useMemo(() => {
    if (!inputPackages || !Array.isArray(inputPackages)) {
      return []
    }
    return dedupePackagesWithKeys(inputPackages)
  }, [inputPackages])
}

/**
 * Hook to detect if backend sent duplicates and provide warnings.
 * Useful for monitoring/debugging production issues.
 *
 * USAGE:
 * ```tsx
 * const warning = useDuplicatePackageWarning(packages)
 * if (warning) console.warn(warning)
 * ```
 */
export function useDuplicatePackageWarning(
  inputPackages: Package[] | null | undefined
): string | null {
  return useMemo(() => {
    if (!inputPackages || !Array.isArray(inputPackages) || inputPackages.length === 0) {
      return null
    }

    const stats = getDedupeStats(inputPackages)
    if (stats.duplicatesFound === 0) {
      return null
    }

    return (
      `⚠️  Backend returned ${stats.duplicatesFound} duplicate package(s). ` +
      `Original: ${stats.originalCount}, Deduplicated: ${stats.deduplicatedCount}. ` +
      `Duplicates have been removed for safe rendering.`
    )
  }, [inputPackages])
}
