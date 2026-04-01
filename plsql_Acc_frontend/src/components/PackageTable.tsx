/**
 * PackageTable Component
 *
 * Safe, deduplicated table for displaying packages with their properties.
 * Resolves React key collision errors by deduplicating BEFORE rendering.
 */

import { TableIcon } from "lucide-react"
import { useDeduplicatedPackages } from "@/hooks/useDeduplicatedPackages"
import type { Package } from "@/utils/package-deduplication"

interface PackageTableProps {
  /** Packages from backend (may contain duplicates) */
  packages: Package[] | null | undefined
  /** Callback when row is clicked */
  onRowClick?: (packageName: string) => void
  /** Show debug info */
  verbose?: boolean
  /** Optional CSS class for styling */
  className?: string
}

/**
 * Usage:
 * ```tsx
 * <PackageTable
 *   packages={response.packages}
 *   onRowClick={(name) => console.log(`Selected: ${name}`)}
 * />
 * ```
 */
export function PackageTable({
  packages,
  onRowClick,
  verbose = false,
  className = "",
}: PackageTableProps) {
  // RULE 1: Deduplicate BEFORE rendering
  const { packagesWithKeys, duplicatesRemoved, hadDuplicates, stats } =
    useDeduplicatedPackages(packages, verbose)

  if (hadDuplicates) {
    console.warn(
      `[PackageTable] Removed ${duplicatesRemoved} duplicate(s) from ${stats.originalCount} packages`
    )
  }

  if (packagesWithKeys.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-8 text-center">
        <TableIcon className="mx-auto mb-2 h-8 w-8 text-slate-400" />
        <p className="text-sm text-slate-600">No packages available</p>
      </div>
    )
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {hadDuplicates ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          ℹ️  {duplicatesRemoved} duplicate package(s) removed from backend response
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-lg border border-slate-200 shadow-sm">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left font-semibold text-slate-700">
                Package Name
              </th>
              <th className="px-4 py-3 text-left font-semibold text-slate-700">
                Files
              </th>
              <th className="px-4 py-3 text-left font-semibold text-slate-700">
                Cursor Complex
              </th>
              <th className="px-4 py-3 text-left font-semibold text-slate-700">
                Retry Logic
              </th>
              <th className="px-4 py-3 text-left font-semibold text-slate-700">
                Tables
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {/* RULE 2: Use unique, stable keys */}
            {packagesWithKeys.map((pkg) => (
              <tr
                key={pkg.key}
                onClick={() => onRowClick?.(pkg.name)}
                className={`transition ${
                  onRowClick
                    ? "cursor-pointer hover:bg-slate-50"
                    : ""
                }`}
              >
                <td className="px-4 py-3 font-mono text-slate-900">
                  {pkg.name}
                </td>
                <td className="px-4 py-3 text-slate-600">
                  <span className="inline-flex gap-1">
                    {pkg.has_spec ? (
                      <span className="rounded bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700">
                        spec
                      </span>
                    ) : null}
                    {pkg.has_body ? (
                      <span className="rounded bg-green-100 px-2 py-1 text-xs font-medium text-green-700">
                        body
                      </span>
                    ) : null}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600">
                  {pkg.cursor_count !== null &&
                  pkg.cursor_count !== undefined ? (
                    <span
                      className={`font-semibold ${
                        pkg.cursor_count > 0
                          ? "text-orange-600"
                          : "text-slate-500"
                      }`}
                    >
                      {pkg.cursor_count}
                    </span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-600">
                  {pkg.retry_count !== null &&
                  pkg.retry_count !== undefined ? (
                    <span
                      className={`font-semibold ${
                        pkg.retry_count > 0
                          ? "text-orange-600"
                          : "text-slate-500"
                      }`}
                    >
                      {pkg.retry_count}
                    </span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-600">
                  {pkg.tables_used && pkg.tables_used.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {pkg.tables_used.slice(0, 3).map((table) => (
                        <span
                          key={table}
                          className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-700"
                        >
                          {table}
                        </span>
                      ))}
                      {pkg.tables_used.length > 3 ? (
                        <span className="px-2 py-1 text-xs text-slate-500">
                          +{pkg.tables_used.length - 3} more
                        </span>
                      ) : null}
                    </div>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-500">
        Showing {packagesWithKeys.length} package(s)
        {hadDuplicates ? ` (${duplicatesRemoved} duplicate(s) removed)` : ""}
      </p>
    </div>
  )
}
