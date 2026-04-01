/**
 * INTEGRATION GUIDE: Package Deduplication Solution
 *
 * This guide shows how to integrate the deduplication solution into your React components.
 * Follow RULE 1-5 strictly to prevent React key collision errors.
 */

// ============================================================================
// PATTERN 1: Simple Dropdown (Recommended for single-select)
// ============================================================================

import { PackageDropdown } from "@/components/PackageDropdown"
import { useState } from "react"

export function MyDropdownExample() {
  const [selectedPackage, setSelectedPackage] = useState<string | null>(null)
  const [packages, setPackages] = useState(null) // From API call

  return (
    <div>
      <label>Select Package</label>
      <PackageDropdown
        packages={packages}
        value={selectedPackage}
        onChange={setSelectedPackage}
        verbose={process.env.NODE_ENV === "development"}
      />
    </div>
  )
}

// ============================================================================
// PATTERN 2: Data Table (Recommended for displaying multiple packages)
// ============================================================================

import { PackageTable } from "@/components/PackageTable"

export function MyTableExample() {
  const [packages, setPackages] = useState(null) // From API call

  function handleRowClick(packageName: string) {
    console.log(`Selected package: ${packageName}`)
  }

  return (
    <PackageTable
      packages={packages}
      onRowClick={handleRowClick}
      verbose={process.env.NODE_ENV === "development"}
    />
  )
}

// ============================================================================
// PATTERN 3: Multi-Select List
// ============================================================================

import { PackageList } from "@/components/PackageList"

export function MyListExample() {
  const [selectedPackages, setSelectedPackages] = useState<string[]>([])
  const [packages, setPackages] = useState(null) // From API call

  return (
    <PackageList
      packages={packages}
      selected={selectedPackages}
      onSelectionChange={setSelectedPackages}
      multiSelect
      showFileStatus
      verbose={process.env.NODE_ENV === "development"}
    />
  )
}

// ============================================================================
// PATTERN 4: Direct Hook Usage (For Custom Rendering)
// ============================================================================

import { useDeduplicatedPackages } from "@/hooks/useDeduplicatedPackages"

export function MyCustomRender() {
  const [packages, setPackages] = useState(null)

  // RULE 1: Deduplicate BEFORE map
  const { packagesWithKeys, duplicatesRemoved, stats } =
    useDeduplicatedPackages(packages, true)

  return (
    <div>
      {/* RULE 2: Use stable, unique keys */}
      {packagesWithKeys.map((pkg) => (
        <div key={pkg.key} className="my-custom-component">
          <h3>{pkg.name}</h3>
          <p>Cursor complexity: {pkg.cursor_count}</p>
          <p>Retry logic: {pkg.retry_count}</p>
        </div>
      ))}

      {duplicatesRemoved > 0 ? (
        <p>ℹ️ ({duplicatesRemoved} duplicates removed)</p>
      ) : null}
    </div>
  )
}

// ============================================================================
// PATTERN 5: Monitoring Hook (For Debugging)
// ============================================================================

import { useDuplicatePackageWarning } from "@/hooks/useDeduplicatedPackages"

export function MyMonitoredComponent() {
  const [packages, setPackages] = useState(null)

  // Automatically detects and logs duplicates
  const warning = useDuplicatePackageWarning(packages)

  if (warning) {
    console.warn(warning)
  }

  // ... rest of component
  return <div>Component with automatic duplicate detection</div>
}

// ============================================================================
// PATTERN 6: API Integration Example
// ============================================================================

import { useEffect, useState } from "react"
import { useDeduplicatedPackages } from "@/hooks/useDeduplicatedPackages"
import type { Package } from "@/utils/package-deduplication"

export function ApiIntegrationExample() {
  const [rawPackages, setRawPackages] = useState<Package[] | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  // RULE 3: Defensive deduplication even if backend fixed
  const { packagesWithKeys, hadDuplicates } =
    useDeduplicatedPackages(rawPackages)

  useEffect(() => {
    async function fetchPackages() {
      try {
        setIsLoading(true)
        const response = await fetch("/api/packages")
        const data = await response.json()
        setRawPackages(data.packages)
      } catch (error) {
        console.error("Failed to fetch packages:", error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchPackages()
  }, [])

  if (isLoading) {
    return <div>Loading packages...</div>
  }

  return (
    <div>
      {hadDuplicates ? (
        <p className="text-amber-600">
          ⚠️ Backend returned duplicate packages. Deduplication applied.
        </p>
      ) : null}

      {/* RULE 2: Use packagesWithKeys for stable rendering */}
      <div>
        {packagesWithKeys.map((pkg) => (
          <div key={pkg.key} className="p-4 border rounded">
            <h4>{pkg.name}</h4>
            <p>Files: {pkg.has_spec && pkg.has_body ? "spec + body" : "partial"}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================================
// MIGRATION GUIDE: Fixing Existing Code
// ============================================================================

/*
BEFORE (❌ BROKEN - Causes duplicate key errors):
```tsx
{packages.map((pkg) => (
  <div key={pkg.name}> {/* PROBLEM: Duplicate keys if backend sends duplicates */}
    {pkg.name}
  </div>
))}
```

AFTER (✅ FIXED - Safe with deduplication):
```tsx
const { packagesWithKeys } = useDeduplicatedPackages(packages)

{packagesWithKeys.map((pkg) => (
  <div key={pkg.key}> {/* SOLUTION: Unique, stable keys */}
    {pkg.name}
  </div>
))}
```
*/

// ============================================================================
// UTILITIES: Standalone Functions (No Hook/Component)
// ============================================================================

import {
  dedupePackages,
  generatePackageKey,
  getDedupeStats,
  verifyNoDuplicates,
  type Package,
} from "@/utils/package-deduplication"

// If you can't use hooks or components, use standalone utilities:

function processPackagesStandalone(packages: Package[]) {
  // RULE 1: Deduplicate
  const deduped = dedupePackages(packages)

  // Get statistics
  const stats = getDedupeStats(packages)
  console.log(`Removed ${stats.duplicatesFound} duplicates`)

  // Verify no duplicates remain (assertion)
  const noDups = verifyNoDuplicates(packages)
  console.assert(
    noDups,
    "Deduplication failed: Duplicates still present"
  )

  // RULE 2: Generate keys
  const keyed = deduped.map((pkg) => ({
    ...pkg,
    key: generatePackageKey(pkg), // "PACKAGE::appl_error_pkg"
  }))

  return keyed
}

// ============================================================================
// TESTING: Unit Tests for Deduplication
// ============================================================================

import { describe, it, expect } from "vitest"

describe("Package Deduplication", () => {
  it("removes duplicate packages by name", () => {
    const input: Package[] = [
      { name: "appl_error_pkg.pks", cursor_count: 0 },
      { name: "appl_error_pkg.pkb", cursor_count: 0 }, // Duplicate
    ]

    const result = dedupePackages(input)

    expect(result).toHaveLength(1)
    expect(result[0].name).toBe("appl_error_pkg")
    expect(result[0].has_spec).toBe(true)
    expect(result[0].has_body).toBe(true)
  })

  it("generates stable, unique keys", () => {
    const pkg: Package = { name: "test_pkg" }
    const key = generatePackageKey(pkg as any)

    expect(key).toBe("PACKAGE::test_pkg")
    expect(key).toBe(generatePackageKey(pkg as any)) // Stable
  })

  it("detects duplicates", () => {
    const input: Package[] = [
      { name: "pkg1" },
      { name: "pkg1" }, // Duplicate
    ]

    const hasDuplicates = !verifyNoDuplicates(input)
    expect(hasDuplicates).toBe(true)
  })

  it("provides statistics", () => {
    const input: Package[] = [
      { name: "pkg1" },
      { name: "pkg1" },
      { name: "pkg2" },
    ]

    const stats = getDedupeStats(input)

    expect(stats.originalCount).toBe(3)
    expect(stats.deduplicatedCount).toBe(2)
    expect(stats.duplicatesFound).toBe(1)
  })
})

// ============================================================================
// CHECKLIST: Integration Steps
// ============================================================================

/*
✓ Step 1: Copy util files to src/utils/
  - package-deduplication.ts

✓ Step 2: Copy hook file to src/hooks/
  - useDeduplicatedPackages.ts

✓ Step 3: Copy component files to src/components/
  - PackageDropdown.tsx
  - PackageTable.tsx
  - PackageList.tsx

✓ Step 4: Replace existing package rendering with provided components
  - Use PackageDropdown for single-select
  - Use PackageTable for data display
  - Use PackageList for multi-select

✓ Step 5: Test in browser
  - Check React console for warnings (should see none)
  - Verify no duplicate rows/options
  - Check for error: "Encountered two children with the same key"

✓ Step 6: Monitor
  - Enable verbose=true in development
  - Watch for warnings about duplicate package removal
  - Confirm duplicates are being caught and removed

✓ Step 7: Verify
  - cursor_count should be correct (not overridden)
  - retry_count should be correct (not overridden)
  - All package names unique in UI
  - Rendering stable between re-renders
*/

// ============================================================================
// DEBUGGING: Console Commands
// ============================================================================

/*
If you see warnings in console, use these to debug:

1. Check for duplicates in raw backend data:
   import { verifyNoDuplicates, getDedupeStats } from "@/utils/package-deduplication"
   const stats = getDedupeStats(backendPackages)
   console.log(stats)

2. Verify deduplication worked:
   const { packagesWithKeys } = useDeduplicatedPackages(packages)
   console.log(packagesWithKeys.map(p => p.key))
   // Should show: ["PACKAGE::appl_error_pkg", "PACKAGE::customer_pkg", ...]

3. Check for key collisions:
   const keys = new Set()
   packagesWithKeys.forEach(p => {
     if (keys.has(p.key)) console.error("Duplicate key:", p.key)
     keys.add(p.key)
   })

4. Monitor duplicate removal:
   const { duplicatesRemoved, originalCount } = useDeduplicatedPackages(packages, true)
   console.log(`Removed ${duplicatesRemoved} from ${originalCount}`)
*/

export {}
