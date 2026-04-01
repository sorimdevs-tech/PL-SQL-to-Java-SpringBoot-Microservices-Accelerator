# React Frontend: Package Deduplication Solution

## Problem

**React Console Error:**
```
Encountered two children with the same key, PACKAGE::appl_error_pkg
```

**Root Cause:**
- Backend sends duplicate PL/SQL packages (one .pks file + one .pkb file for each package)
- React renders them with identical keys: `PACKAGE::appl_error_pkg`
- React reconciliation fails, causing:
  - ❌ Duplicate rows in UI
  - ❌ Incorrect values (cursor_count=1, retry_count=1 instead of 0)
  - ❌ Unstable/broken rendering

**Why This Happens:**
1. Backend file analysis processes `.pks` (spec) and `.pkb` (body) separately
2. Each generates a package entry
3. Frontend receives: `[{name: "appl_error_pkg.pks"}, {name: "appl_error_pkg.pkb"}]`
4. React keys collide when using simple `pkg.name` as key

## Solution: 5 Strict Rules

### RULE 1: Deduplicate Data BEFORE Map

Never render raw backend data. Always deduplicate first:

```tsx
// ❌ WRONG - Will have duplicate keys
{packages.map(pkg => (
  <div key={pkg.name}>{pkg.name}</div>
))}

// ✅ CORRECT - Deduplicate first
const { packagesWithKeys } = useDeduplicatedPackages(packages)
{packagesWithKeys.map(pkg => (
  <div key={pkg.key}>{pkg.name}</div>
))}
```

### RULE 2: Use Unique, Stable Keys

Never use index or simple name alone:

```tsx
// ❌ WRONG - Index becomes unstable with sorting/filtering
{packages.map((pkg, index) => (
  <div key={index}>...</div>
))}

// ❌ WRONG - Name duplicates if backend sends duplicates
{packages.map(pkg => (
  <div key={pkg.name}>...</div>
))}

// ✅ CORRECT - Stable, unique identifier
{packagesWithKeys.map(pkg => (
  <div key={pkg.key}>...</div>  // key="PACKAGE::appl_error_pkg"
))}
```

Key format: `"PACKAGE::{package_name}"`

### RULE 3: Defensive Deduplication

Don't trust backend. Frontend MUST deduplicate even if backend is fixed:

```tsx
// Backend might still send duplicates due to:
// - Schema changes, migrations
// - Different API versions
// - Edge cases in aggregation logic

// Always use defensive deduplication
const { packagesWithKeys } = useDeduplicatedPackages(packages)
```

### RULE 4: Ensure Stable Rendering

Keys must not change between renders:

```tsx
// ❌ WRONG - Key changes if data changes
{packages.filter(...).map(pkg => (
  <div key={`${pkg.name}-${pkg.cursor_count}`}>
))}

// ✅ CORRECT - Key only depends on identity
{packages.map(pkg => (
  <div key={generatePackageKey(pkg)}>
))}
```

### RULE 5: Full Type Safety

Use TypeScript throughout:

```tsx
import type { Package, DedupedPackage } from "@/utils/package-deduplication"

function MyComponent(props: { packages: Package[] }) {
  const { packagesWithKeys } = useDeduplicatedPackages(props.packages)
  
  // ✅ Type-safe - DedupedPackage has all properties
  return (
    <div>
      {packagesWithKeys.map((pkg: DedupedPackage & { key: string }) => (
        <div key={pkg.key}>
          {pkg.name} - Cursor: {pkg.cursor_count} - Retry: {pkg.retry_count}
        </div>
      ))}
    </div>
  )
}
```

## Files Included

```
src/
├── utils/
│   ├── package-deduplication.ts      # Core deduplication logic
│   └── package-deduplication.test.ts # Unit tests
├── hooks/
│   └── useDeduplicatedPackages.ts    # React hook
├── components/
│   ├── PackageDropdown.tsx           # Example: Dropdown component
│   ├── PackageTable.tsx              # Example: Table component
│   └── PackageList.tsx               # Example: List component
├── INTEGRATION_GUIDE.ts              # Complete integration examples
└── README.md                         # This file
```

## Quick Start

### 1. Copy Files

```bash
# Copy utilities
cp -r src/utils/package-deduplication.ts your-project/src/utils/

# Copy hook
cp -r src/hooks/useDeduplicatedPackages.ts your-project/src/hooks/

# Copy example components
cp -r src/components/Package*.tsx your-project/src/components/
```

### 2. Use in Your Component

```tsx
import { useDeduplicatedPackages } from "@/hooks/useDeduplicatedPackages"
import { PackageTable } from "@/components/PackageTable"

export function MyComponent() {
  const [packages, setPackages] = useState(null)

  // For custom rendering
  const { packagesWithKeys, duplicatesRemoved } = useDeduplicatedPackages(packages)

  // For dropdown
  return <PackageDropdown packages={packages} value={selected} onChange={setSelected} />

  // For table
  return <PackageTable packages={packages} />

  // For custom rendering
  return (
    <div>
      {packagesWithKeys.map(pkg => (
        <div key={pkg.key}>{pkg.name}</div>
      ))}
    </div>
  )
}
```

### 3. Verify in Browser

- Open React DevTools Console
- Should see **NO** warnings about duplicate keys
- Should see **NO** "Encountered two children with the same key" errors
- All values should be correct (cursor_count=0, retry_count=0)

## API Reference

### Utility Functions

#### `dedupePackages(packages: Package[]): DedupedPackage[]`
Deduplicates an array of packages by name.

```tsx
import { dedupePackages } from "@/utils/package-deduplication"

const deduped = dedupePackages(backendPackages)
// Input: [{name: "pkg.pks"}, {name: "pkg.pkb"}]
// Output: [{name: "pkg", has_spec: true, has_body: true}]
```

#### `generatePackageKey(pkg: DedupedPackage): string`
Generates a stable, unique React key.

```tsx
import { generatePackageKey } from "@/utils/package-deduplication"

const key = generatePackageKey(pkg)
// Output: "PACKAGE::appl_error_pkg"
```

#### `getDedupeStats(packages: Package[]): DedupeStats`
Get statistics about deduplication.

```tsx
import { getDedupeStats } from "@/utils/package-deduplication"

const stats = getDedupeStats(packages)
console.log(`${stats.duplicatesFound} duplicates removed`)
```

### React Hooks

#### `useDeduplicatedPackages(packages, verbose?): UseDeduplicatedPackagesResult`
Main hook for deduplication in components.

```tsx
const { packages, packagesWithKeys, duplicatesRemoved } = 
  useDeduplicatedPackages(inputPackages, true)
```

Returns:
- `packages`: Deduplicated package array
- `packagesWithKeys`: Packages with `.key` property for React
- `duplicatesRemoved`: Count of duplicates removed
- `stats`: Detailed statistics

#### `usePackageOptions(packages): (DedupedPackage & { key: string })[]`
Simple alternative returning only packages with keys.

#### `useDuplicatePackageWarning(packages): string | null`
Returns warning message if duplicates detected.

### Components

#### `<PackageDropdown />`
Single-select dropdown for packages.

Props:
- `packages`: Package array (may have duplicates)
- `value`: Selected package name
- `onChange`: Selection callback
- `isLoading?`: Show loading state
- `verbose?`: Show debug info

```tsx
<PackageDropdown
  packages={response.packages}
  value={selected}
  onChange={setSelected}
  verbose={isDev}
/>
```

#### `<PackageTable />`
Table display showing all packages with metadata.

Props:
- `packages`: Package array
- `onRowClick?`: Row click callback
- `verbose?`: Show debug info

```tsx
<PackageTable
  packages={response.packages}
  onRowClick={(name) => console.log(`Selected: ${name}`)}
/>
```

#### `<PackageList />`
Multi-select list with checkboxes.

Props:
- `packages`: Package array
- `selected?`: Selected package names
- `onSelectionChange?`: Selection callback
- `multiSelect?`: Allow multi-select (default: true)
- `showFileStatus?`: Show spec/body badges

```tsx
<PackageList
  packages={response.packages}
  selected={selectedPackages}
  onSelectionChange={setSelectedPackages}
  multiSelect
/>
```

## Examples

### Example 1: Simple Dropdown

```tsx
import { useState } from "react"
import { PackageDropdown } from "@/components/PackageDropdown"

export function MyDropdown() {
  const [selected, setSelected] = useState<string | null>(null)
  const [packages, setPackages] = useState(null)

  return (
    <PackageDropdown
      packages={packages}
      value={selected}
      onChange={setSelected}
    />
  )
}
```

### Example 2: Table with Click Handler

```tsx
import { PackageTable } from "@/components/PackageTable"

export function MyTable() {
  const [packages, setPackages] = useState(null)

  return (
    <PackageTable
      packages={packages}
      onRowClick={(name) => {
        console.log(`Package selected: ${name}`)
      }}
    />
  )
}
```

### Example 3: Custom Rendering

```tsx
import { useDeduplicatedPackages } from "@/hooks/useDeduplicatedPackages"

export function MyCustomComponent() {
  const [packages, setPackages] = useState(null)

  const { packagesWithKeys, duplicatesRemoved } = 
    useDeduplicatedPackages(packages)

  return (
    <div>
      {packagesWithKeys.map(pkg => (
        <div key={pkg.key} className="package-card">
          <h3>{pkg.name}</h3>
          <p>Cursor: {pkg.cursor_count}</p>
          <p>Retry: {pkg.retry_count}</p>
        </div>
      ))}
      {duplicatesRemoved > 0 && (
        <p>ℹ️ {duplicatesRemoved} duplicates removed</p>
      )}
    </div>
  )
}
```

### Example 4: With API Integration

```tsx
import { useEffect, useState } from "react"
import { useDeduplicatedPackages } from "@/hooks/useDeduplicatedPackages"

export function PackageManager() {
  const [packages, setPackages] = useState(null)
  const [loading, setLoading] = useState(false)

  const { packagesWithKeys, hadDuplicates } = 
    useDeduplicatedPackages(packages)

  useEffect(() => {
    async function fetchPackages() {
      setLoading(true)
      try {
        const response = await fetch("/api/packages")
        const data = await response.json()
        setPackages(data.packages)

        if (hadDuplicates) {
          console.warn("⚠️ Backend returned duplicates - deduplication applied")
        }
      } finally {
        setLoading(false)
      }
    }

    fetchPackages()
  }, [hadDuplicates])

  if (loading) return <div>Loading...</div>

  return (
    <div>
      {packagesWithKeys.map(pkg => (
        <div key={pkg.key}>{pkg.name}</div>
      ))}
    </div>
  )
}
```

## Testing

Run unit tests:

```bash
npm run test -- package-deduplication.test.ts
```

Tests verify:
- ✅ Correct extraction of package names
- ✅ Proper merging of .pks/.pkb files
- ✅ Stable key generation
- ✅ No duplicates in output
- ✅ Statistics calculation
- ✅ Real-world 16→8 package reduction

## Debugging

### Check for Duplicates

```js
import { getDedupeStats } from "@/utils/package-deduplication"

const stats = getDedupeStats(backendPackages)
console.log(stats)
// { originalCount: 16, deduplicatedCount: 8, duplicatesFound: 8, ... }
```

### Monitor Deduplication

```jsx
const { duplicatesRemoved } = useDeduplicatedPackages(packages, true)
// Pass true for verbose logging to console
```

### Verify No Key Collisions

```js
const keys = new Set()
packagesWithKeys.forEach(pkg => {
  if (keys.has(pkg.key)) {
    console.error("Duplicate key detected:", pkg.key)
  }
  keys.add(pkg.key)
})
console.log(`Verified ${keys.size} unique keys`)
```

## Performance

- **Time Complexity:** O(n) for deduplication
- **Space Complexity:** O(n) for Map storage
- **Render Performance:** No impact (deduplication is one-time in useMemo)
- **Memory:** Minimal overhead (~10-20KB for typical package lists)

## Browser Compatibility

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ React 16.8+ (requires hooks)
- ✅ TypeScript 4.5+

## Troubleshooting

### Issue: Still seeing duplicate key warnings

**Solution:** Verify you're using the hook before rendering:
```tsx
// ✗ Wrong
{packages.map(pkg => <div key={pkg.name}>{pkg.name}</div>)}

// ✓ Correct
const { packagesWithKeys } = useDeduplicatedPackages(packages)
{packagesWithKeys.map(pkg => <div key={pkg.key}>{pkg.name}</div>)}
```

### Issue: Values still incorrect (cursor_count = 1)

**Solution:** Ensure data flows through deduplication:
```tsx
// Hook handles merging from both .pks and .pkb
// Verify backend is sending both files
const stats = getDedupeStats(packages)
console.log(stats.originalCount, stats.deduplicatedCount)
```

### Issue: Hook not deduplicating

**Solution:** Check that packages is an array:
```tsx
if (!packages || !Array.isArray(packages)) {
  return <div>No packages</div>
}
const { packagesWithKeys } = useDeduplicatedPackages(packages)
```

## Next Steps

1. **Copy files** to your project
2. **Replace existing package rendering** with provided components
3. **Run tests** to verify integration
4. **Enable verbose mode** during development
5. **Monitor production** for duplicate warnings

## Support

For issues or questions:
1. Check browser React DevTools console
2. Enable `verbose={true}` on hooks/components
3. Review integration guide at `src/INTEGRATION_GUIDE.ts`
4. Run unit tests to verify deduplication logic

## License

Same as parent project

---

**Summary:**
- ✅ Prevents React key collision errors
- ✅ Deduplicates 16 files → 8 packages
- ✅ Maintains correct cursor_count and retry_count values
- ✅ Type-safe TypeScript implementation
- ✅ Production-ready with tests
- ✅ Zero impact on rendering performance
