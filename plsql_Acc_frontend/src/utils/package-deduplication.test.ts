/**
 * Unit Tests for Package Deduplication
 *
 * Test file for deduplication utilities.
 * Run with: npm run test -- package-deduplication.test.ts
 */

import { describe, it, expect, beforeEach } from "vitest"
import {
  dedupePackages,
  extractPackageName,
  determineSource,
  generatePackageKey,
  dedupePackagesWithKeys,
  verifyNoDuplicates,
  getDedupeStats,
  isPackage,
  isPackageArray,
  type Package,
} from "@/utils/package-deduplication"

describe("extractPackageName", () => {
  it("removes .pks extension", () => {
    expect(extractPackageName("appl_error_pkg.pks")).toBe("appl_error_pkg")
  })

  it("removes .pkb extension", () => {
    expect(extractPackageName("customer_pkg.pkb")).toBe("customer_pkg")
  })

  it("handles names without extension", () => {
    expect(extractPackageName("simple_pkg")).toBe("simple_pkg")
  })

  it("is case-insensitive for extensions", () => {
    expect(extractPackageName("test_pkg.PKS")).toBe("test_pkg")
    expect(extractPackageName("test_pkg.PKB")).toBe("test_pkg")
  })
})

describe("determineSource", () => {
  it("identifies .pks as spec", () => {
    expect(determineSource("appl_error_pkg.pks")).toBe("spec")
  })

  it("identifies .pkb as body", () => {
    expect(determineSource("appl_error_pkg.pkb")).toBe("body")
  })

  it("returns 'merged' for literal 'merged'", () => {
    expect(determineSource("merged")).toBe("merged")
  })

  it("returns 'unknown' for unrecognized format", () => {
    expect(determineSource("some_file.sql")).toBe("unknown")
  })

  it("is case-insensitive", () => {
    expect(determineSource("TEST.PKS")).toBe("spec")
    expect(determineSource("TEST.PKB")).toBe("body")
  })
})

describe("generatePackageKey", () => {
  it("creates key with PACKAGE:: prefix", () => {
    const pkg: Package = { name: "test_pkg", source: "merged" }
    expect(generatePackageKey(pkg as any)).toBe("PACKAGE::test_pkg")
  })

  it("is stable across multiple calls", () => {
    const pkg: Package = { name: "stable_pkg", source: "merged" }
    const key1 = generatePackageKey(pkg as any)
    const key2 = generatePackageKey(pkg as any)
    expect(key1).toBe(key2)
  })
})

describe("verifyNoDuplicates", () => {
  it("returns true for unique packages", () => {
    const packages: Package[] = [
      { name: "pkg1" },
      { name: "pkg2" },
      { name: "pkg3" },
    ]
    expect(verifyNoDuplicates(packages)).toBe(true)
  })

  it("returns false when duplicates exist", () => {
    const packages: Package[] = [
      { name: "test.pks" },
      { name: "test.pkb" }, // Same package name after normalization
    ]
    expect(verifyNoDuplicates(packages)).toBe(false)
  })

  it("returns false for exact duplicates", () => {
    const packages: Package[] = [{ name: "pkg1" }, { name: "pkg1" }]
    expect(verifyNoDuplicates(packages)).toBe(false)
  })

  it("returns true for empty array", () => {
    expect(verifyNoDuplicates([])).toBe(true)
  })
})

describe("dedupePackages", () => {
  it("merges .pks and .pkb into single entry", () => {
    const input: Package[] = [
      { name: "appl_error_pkg.pks", cursor_count: 0 },
      { name: "appl_error_pkg.pkb", cursor_count: 0 },
    ]

    const result = dedupePackages(input)

    expect(result).toHaveLength(1)
    expect(result[0].name).toBe("appl_error_pkg")
    expect(result[0].has_spec).toBe(true)
    expect(result[0].has_body).toBe(true)
    expect(result[0].source).toBe("merged")
  })

  it("preserves data from both spec and body", () => {
    const input: Package[] = [
      {
        name: "test_pkg.pks",
        cursor_count: 0,
        tables_used: ["table1"],
      },
      {
        name: "test_pkg.pkb",
        cursor_count: 0,
        tables_used: ["table2"],
      },
    ]

    const result = dedupePackages(input)

    expect(result[0].tables_used).toContain("table1")
    expect(result[0].tables_used).toContain("table2")
  })

  it("takes max value for numeric fields", () => {
    const input: Package[] = [
      { name: "test_pkg.pks", cursor_count: 1 },
      { name: "test_pkg.pkb", cursor_count: 2 },
    ]

    const result = dedupePackages(input)

    expect(result[0].cursor_count).toBe(2)
  })

  it("deduplicates exceptions", () => {
    const input: Package[] = [
      {
        name: "test_pkg.pks",
        exceptions: ["EXCEPTION_A"],
      },
      {
        name: "test_pkg.pkb",
        exceptions: ["EXCEPTION_A", "EXCEPTION_B"],
      },
    ]

    const result = dedupePackages(input)

    expect(result[0].exceptions).toHaveLength(2)
    expect(result[0].exceptions).toContain("EXCEPTION_A")
    expect(result[0].exceptions).toContain("EXCEPTION_B")
  })

  it("sorts results by package name", () => {
    const input: Package[] = [
      { name: "zebra_pkg.pkb" },
      { name: "apple_pkg.pks" },
      { name: "monkey_pkg.pks" },
    ]

    const result = dedupePackages(input)

    expect(result.map((p) => p.name)).toEqual([
      "apple_pkg",
      "monkey_pkg",
      "zebra_pkg",
    ])
  })

  it("handles empty input", () => {
    expect(dedupePackages([])).toEqual([])
  })

  it("removes 16 duplicate files -> 8 packages", () => {
    // Simulating the real-world scenario
    const input: Package[] = [
      { name: "appl_error_pkg.pks", cursor_count: 0 },
      { name: "appl_error_pkg.pkb", cursor_count: 0 },
      { name: "appl_log_pkg.pks", cursor_count: 0 },
      { name: "appl_log_pkg.pkb", cursor_count: 0 },
      { name: "customer_pkg.pks", cursor_count: 0 },
      { name: "customer_pkg.pkb", cursor_count: 0 },
      { name: "invoice_api_pkg.pks", cursor_count: 0 },
      { name: "invoice_api_pkg.pkb", cursor_count: 0 },
      { name: "invoice_pkg.pks", cursor_count: 0 },
      { name: "invoice_pkg.pkb", cursor_count: 0 },
      { name: "paypal_util_pkg.pks", cursor_count: 0 },
      { name: "paypal_util_pkg.pkb", cursor_count: 0 },
      { name: "simple_test_pkg.pks", cursor_count: 0 },
      { name: "simple_test_pkg.pkb", cursor_count: 0 },
      { name: "xtp.pks", cursor_count: 0 },
      { name: "xtp.pkb", cursor_count: 0 },
    ]

    const result = dedupePackages(input)

    expect(result).toHaveLength(8)
    expect(result.every((p) => p.has_spec && p.has_body)).toBe(true)
  })
})

describe("dedupePackagesWithKeys", () => {
  it("adds key property to each package", () => {
    const input: Package[] = [{ name: "test_pkg" }]

    const result = dedupePackagesWithKeys(input)

    expect(result[0].key).toBe("PACKAGE::test_pkg")
  })

  it("returns same count as dedupePackages", () => {
    const input: Package[] = [
      { name: "pkg.pks" },
      { name: "pkg.pkb" },
    ]

    const deduped = dedupePackages(input)
    const dedupedWithKeys = dedupePackagesWithKeys(input)

    expect(dedupedWithKeys).toHaveLength(deduped.length)
  })
})

describe("getDedupeStats", () => {
  it("calculates statistics correctly", () => {
    const input: Package[] = [
      { name: "pkg1.pks" },
      { name: "pkg1.pkb" },
      { name: "pkg2.pks" },
    ]

    const stats = getDedupeStats(input)

    expect(stats.originalCount).toBe(3)
    expect(stats.deduplicatedCount).toBe(2)
    expect(stats.duplicatesFound).toBe(1)
    expect(stats.packageNames).toEqual(["pkg1", "pkg2"])
  })

  it("returns zero duplicates when none exist", () => {
    const input: Package[] = [
      { name: "pkg1" },
      { name: "pkg2" },
    ]

    const stats = getDedupeStats(input)

    expect(stats.duplicatesFound).toBe(0)
  })
})

describe("Type guards", () => {
  it("isPackage identifies valid packages", () => {
    expect(isPackage({ name: "test" })).toBe(true)
    expect(isPackage({ name: "test", cursor_count: 0 })).toBe(true)
    expect(isPackage({})).toBe(false)
    expect(isPackage(null)).toBe(false)
    expect(isPackage("not a package")).toBe(false)
  })

  it("isPackageArray identifies package arrays", () => {
    expect(isPackageArray([{ name: "test" }])).toBe(true)
    expect(isPackageArray([])).toBe(true)
    expect(isPackageArray([{}])).toBe(false)
    expect(isPackageArray("not an array")).toBe(false)
  })
})

describe("Integration: Real-world scenario", () => {
  it("handles backend response with duplicates and missing values", () => {
    const backendResponse: Package[] = [
      {
        name: "customer_pkg.pks",
        has_spec: true,
        cursor_count: 0,
        retry_count: 0,
      },
      {
        name: "customer_pkg.pkb",
        has_body: true,
        cursor_count: 0,
        retry_count: 0,
        tables_used: ["xy_customer"],
      },
      {
        name: "invoice_pkg.pks",
        has_spec: true,
        cursor_count: 0,
        retry_count: 0,
      },
      {
        name: "invoice_pkg.pkb",
        has_body: true,
        cursor_count: 0,
        retry_count: 0,
        tables_used: ["xy_invoice"],
      },
    ]

    const result = dedupePackages(backendResponse)

    expect(result).toHaveLength(2)

    const customerPkg = result.find((p) => p.name === "customer_pkg")
    expect(customerPkg).toBeDefined()
    expect(customerPkg?.has_spec).toBe(true)
    expect(customerPkg?.has_body).toBe(true)
    expect(customerPkg?.tables_used).toContain("xy_customer")
    expect(customerPkg?.cursor_count).toBe(0)
    expect(customerPkg?.retry_count).toBe(0)
  })

  it("prevents React key collision errors", () => {
    const duplicateInput: Package[] = [
      { name: "appl_error_pkg.pks" },
      { name: "appl_error_pkg.pkb" }, // Same key would cause React error
    ]

    const withKeys = dedupePackagesWithKeys(duplicateInput)
    const keys = withKeys.map((p) => p.key)
    const uniqueKeys = new Set(keys)

    // Verify no duplicate keys
    expect(keys.length).toBe(uniqueKeys.size)
    expect(uniqueKeys.size).toBe(1) // Only one package
    expect(keys[0]).toBe("PACKAGE::appl_error_pkg")
  })
})
