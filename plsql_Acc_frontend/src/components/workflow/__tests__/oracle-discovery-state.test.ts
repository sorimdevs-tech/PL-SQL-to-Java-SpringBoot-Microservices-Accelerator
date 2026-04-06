import { describe, expect, it } from "vitest"

import { resolveDiscoveryStage } from "@/components/workflow/oracle-discovery-state"

describe("resolveDiscoveryStage", () => {
  it("returns connect when not connected", () => {
    expect(
      resolveDiscoveryStage({
        connected: false,
        selectedContainers: [],
        selectedSchemas: [],
        selectedObjects: [],
        selectedProcedures: [],
      }),
    ).toBe("connect")
  })

  it("returns container when connected but no container selected", () => {
    expect(
      resolveDiscoveryStage({
        connected: true,
        selectedContainers: [],
        selectedSchemas: [],
        selectedObjects: [],
        selectedProcedures: [],
      }),
    ).toBe("container")
  })

  it("returns schema when container selected but no schema", () => {
    expect(
      resolveDiscoveryStage({
        connected: true,
        selectedContainers: ["ORCLPDB"],
        selectedSchemas: [],
        selectedObjects: [],
        selectedProcedures: [],
      }),
    ).toBe("schema")
  })
})
