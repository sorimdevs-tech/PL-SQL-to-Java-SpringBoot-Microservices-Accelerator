/**
 * PackageList Component
 *
 * Safe, deduplicated list for displaying packages.
 * Resolves React key collision errors by deduplicating BEFORE rendering.
 */

import { CheckCircle2, Circle } from "lucide-react"
import { useDeduplicatedPackages } from "@/hooks/useDeduplicatedPackages"
import type { Package } from "@/utils/package-deduplication"

interface PackageListProps {
  /** Packages from backend (may contain duplicates) */
  packages: Package[] | null | undefined
  /** Selected package names (for multi-select) */
  selected?: string[]
  /** Callback when package selection changes */
  onSelectionChange?: (selected: string[]) => void
  /** Allow multi-select */
  multiSelect?: boolean
  /** Show spec/body status */
  showFileStatus?: boolean
  /** Show debug info */
  verbose?: boolean
  /** Optional CSS class for styling */
  className?: string
}

/**
 * Usage:
 * ```tsx
 * <PackageList
 *   packages={response.packages}
 *   selected={selectedPackages}
 *   onSelectionChange={setSelectedPackages}
 *   multiSelect
 * />
 * ```
 */
export function PackageList({
  packages,
  selected = [],
  onSelectionChange,
  multiSelect = false,
  showFileStatus = true,
  verbose = false,
  className = "",
}: PackageListProps) {
  // RULE 1: Deduplicate BEFORE rendering
  const { packagesWithKeys, duplicatesRemoved, hadDuplicates } =
    useDeduplicatedPackages(packages, verbose)

  function toggleSelection(packageName: string) {
    if (!onSelectionChange) return

    if (multiSelect) {
      const newSelected = selected.includes(packageName)
        ? selected.filter((name) => name !== packageName)
        : [...selected, packageName]
      onSelectionChange(newSelected)
    } else {
      onSelectionChange(selected.includes(packageName) ? [] : [packageName])
    }
  }

  if (packagesWithKeys.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-center">
        <p className="text-sm text-slate-600">No packages available</p>
      </div>
    )
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {hadDuplicates ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          ℹ️  {duplicatesRemoved} duplicate package(s) removed
        </div>
      ) : null}

      <div className="space-y-1">
        {/* RULE 2: Use unique, stable keys */}
        {packagesWithKeys.map((pkg) => {
          const isSelected = selected.includes(pkg.name)

          return (
            <div
              key={pkg.key}
              onClick={() => toggleSelection(pkg.name)}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2 transition ${
                isSelected
                  ? "border-cyan-300 bg-cyan-50"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              {/* Selection indicator */}
              {onSelectionChange ? (
                isSelected ? (
                  <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-cyan-600" />
                ) : (
                  <Circle className="mt-0.5 h-5 w-5 flex-shrink-0 text-slate-300" />
                )
              ) : null}

              {/* Package info */}
              <div className="flex-1 min-w-0">
                <p
                  className={`font-mono text-sm font-medium ${
                    isSelected ? "text-cyan-900" : "text-slate-900"
                  }`}
                >
                  {pkg.name}
                </p>

                {/* File status */}
                {showFileStatus && (pkg.has_spec || pkg.has_body) ? (
                  <p className="mt-1 text-xs text-slate-500">
                    {pkg.has_spec && pkg.has_body
                      ? "✓ Spec + Body"
                      : pkg.has_spec
                        ? "✓ Spec only"
                        : "✓ Body only"}
                  </p>
                ) : null}

                {/* Metadata */}
                {pkg.cursor_count !== null ||
                pkg.retry_count !== null ||
                (pkg.tables_used && pkg.tables_used.length > 0) ? (
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-600">
                    {pkg.cursor_count !== null &&
                    pkg.cursor_count !== undefined ? (
                      <span className="rounded bg-slate-100 px-2 py-0.5">
                        Cursor: {pkg.cursor_count}
                      </span>
                    ) : null}
                    {pkg.retry_count !== null &&
                    pkg.retry_count !== undefined ? (
                      <span className="rounded bg-slate-100 px-2 py-0.5">
                        Retry: {pkg.retry_count}
                      </span>
                    ) : null}
                    {pkg.tables_used && pkg.tables_used.length > 0 ? (
                      <span className="rounded bg-slate-100 px-2 py-0.5">
                        Tables: {pkg.tables_used.length}
                      </span>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>

      {selected.length > 0 ? (
        <p className="text-xs text-slate-500">
          {selected.length} package(s) selected
        </p>
      ) : null}
    </div>
  )
}
