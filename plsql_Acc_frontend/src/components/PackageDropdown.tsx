/**
 * PackageDropdown Component
 *
 * Safe, deduplicated dropdown for selecting packages.
 * Resolves React key collision errors by deduplicating BEFORE rendering.
 */

import { Loader } from "lucide-react"
import { useDeduplicatedPackages } from "@/hooks/useDeduplicatedPackages"
import type { Package } from "@/utils/package-deduplication"

interface PackageDropdownProps {
  /** Packages from backend (may contain duplicates) */
  packages: Package[] | null | undefined
  /** Selected package name */
  value: string | null
  /** Callback when selection changes */
  onChange: (packageName: string) => void
  /** Loading state */
  isLoading?: boolean
  /** Optional CSS class for styling */
  className?: string
  /** Show debug info */
  verbose?: boolean
}

/**
 * Usage:
 * ```tsx
 * <PackageDropdown
 *   packages={response.packages}
 *   value={selectedPackage}
 *   onChange={setSelectedPackage}
 * />
 * ```
 */
export function PackageDropdown({
  packages,
  value,
  onChange,
  isLoading = false,
  className = "",
  verbose = false,
}: PackageDropdownProps) {
  // RULE 1: Deduplicate BEFORE rendering
  const { packagesWithKeys, duplicatesRemoved, hadDuplicates } =
    useDeduplicatedPackages(packages, verbose)

  // Warn if duplicates were found
  if (hadDuplicates && verbose) {
    console.warn(
      `[PackageDropdown] Removed ${duplicatesRemoved} duplicates from backend response`
    )
  }

  return (
    <div className="space-y-1">
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={isLoading || packagesWithKeys.length === 0}
        className={`rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 ${className}`}
      >
        <option value="">
          {isLoading
            ? "Loading packages..."
            : packagesWithKeys.length === 0
              ? "No packages available"
              : "Select a package"}
        </option>

        {/* RULE 2: Use unique, stable keys */}
        {packagesWithKeys.map((pkg) => (
          <option key={pkg.key} value={pkg.name}>
            {pkg.name}
            {pkg.has_spec && pkg.has_body ? " (spec + body)" : ""}
            {pkg.has_spec && !pkg.has_body ? " (spec only)" : ""}
            {pkg.has_body && !pkg.has_spec ? " (body only)" : ""}
          </option>
        ))}
      </select>

      {hadDuplicates && verbose ? (
        <p className="text-xs text-amber-600">
          ℹ️  {duplicatesRemoved} duplicate(s) removed from backend response
        </p>
      ) : null}
    </div>
  )
}
