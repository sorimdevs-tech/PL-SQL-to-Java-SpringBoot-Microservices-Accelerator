import { afterEach, describe, expect, it, vi } from "vitest"

import { getDiscoveryContainers, testOracleConnection } from "@/api/discoveryClient"

describe("discoveryClient", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("calls oracle test connection endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ connected: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )

    const response = await testOracleConnection({
      host: "localhost",
      port: 1521,
      service_name: "XEPDB1",
      username: "system",
      password: "secret",
    })

    expect(response.connected).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("calls discovery containers endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ containers: [{ name: "ORCLPDB", type: "PDB" }], count: 1 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )

    const response = await getDiscoveryContainers()

    expect(response.count).toBe(1)
    expect(response.containers[0]?.name).toBe("ORCLPDB")
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
