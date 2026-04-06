export type DiscoveryStage =
  | "connect"
  | "container"
  | "schema"
  | "object"
  | "metadata"

export interface DiscoveryStageInput {
  connected: boolean
  selectedContainers: string[]
  selectedSchemas: string[]
  selectedObjects: string[]
  selectedProcedures: string[]
}

export function resolveDiscoveryStage(input: DiscoveryStageInput): DiscoveryStage {
  if (!input.connected) {
    return "connect"
  }
  if (input.selectedContainers.length === 0) {
    return "container"
  }
  if (input.selectedSchemas.length === 0) {
    return "schema"
  }
  if (input.selectedObjects.length === 0) {
    return "object"
  }
  if (input.selectedProcedures.length === 0) {
    return "metadata"
  }
  return "metadata"
}
