import { useEffect, useMemo, useState } from "react"
import { ChevronLeft, ChevronRight, LoaderCircle } from "lucide-react"

import {
  getDiscoveryContainers,
  getDiscoveryObjects,
  getDiscoverySchemas,
  getProcedureDiscovery,
  testOracleConnection,
} from "@/api/discoveryClient"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { DiscoveryAnalyzeResponse, DiscoveryObject, OracleTestConnectionRequest } from "@/types/discovery"

interface OracleDiscoveryProps {
  host: string
  port: string
  serviceName: string
  username: string
  password: string
  availableDatabases: string[]
  setAvailableDatabases: (databases: string[]) => void
  selectedDatabases: string[]
  setSelectedDatabases: (databases: string[]) => void
  availableSchemas: string[]
  setAvailableSchemas: (schemas: string[]) => void
  selectedSchemas: string[]
  setSelectedSchemas: (schemas: string[]) => void
  availableObjects: string[]
  setAvailableObjects: (objects: string[]) => void
  selectedObjects: string[]
  setSelectedObjects: (objects: string[]) => void
  availableProcedures: string[]
  setAvailableProcedures: (procedures: string[]) => void
  selectedProcedures: string[]
  setSelectedProcedures: (procedures: string[]) => void
}

interface DualListSelectorProps {
  title: string
  description: string
  availableItems: string[]
  selectedItems: string[]
  onSelectedItemsChange: (items: string[]) => void
  isLoading?: boolean
  error?: string | null
  onRetry?: () => void
  navigation?: {
    onPrevious?: () => void
    onNext?: () => void
    disablePrevious?: boolean
    disableNext?: boolean
  }
}

const STORAGE_KEYS = {
  container: "oracle.discovery.selectedContainer",
  schemas: "oracle.discovery.selectedSchemas",
  objects: "oracle.discovery.selectedObjects",
}

function toConnectionPayload(props: OracleDiscoveryProps): OracleTestConnectionRequest {
  return {
    host: props.host.trim(),
    port: Number(props.port),
    service_name: props.serviceName.trim(),
    username: props.username.trim(),
    password: props.password,
  }
}

function isValidConnection(payload: OracleTestConnectionRequest): boolean {
  return !!payload.host && !!payload.service_name && !!payload.username && !!payload.password && Number.isFinite(payload.port)
}

function unique(items: string[]): string[] {
  return Array.from(new Set(items))
}

function objectLabel(item: DiscoveryObject): string {
  return `${item.schema}.${item.name} (${item.type})`
}

function objectType(label: string): string {
  const match = label.match(/\(([^)]+)\)$/)
  return match ? match[1].toUpperCase() : ""
}

function objectName(label: string): string {
  const namePart = label.replace(/\s*\([^)]+\)\s*$/, "").trim()
  const segments = namePart.split(".")
  return segments[segments.length - 1] || namePart
}

function objectSchema(label: string): string {
  const namePart = label.replace(/\s*\([^)]+\)\s*$/, "").trim()
  const segments = namePart.split(".")
  return segments.length > 1 ? segments[0] : ""
}

function readStorageArray(key: string): string[] {
  try {
    const value = sessionStorage.getItem(key)
    if (!value) {
      return []
    }
    const parsed = JSON.parse(value) as unknown
    return Array.isArray(parsed) ? parsed.map((item) => String(item)) : []
  } catch {
    return []
  }
}

function writeStorageArray(key: string, value: string[]) {
  sessionStorage.setItem(key, JSON.stringify(value))
}

function DualListSelector(props: DualListSelectorProps) {
  const [checkedAvailable, setCheckedAvailable] = useState<string[]>([])
  const [checkedSelected, setCheckedSelected] = useState<string[]>([])
  const availablePool = props.availableItems.filter((item) => !props.selectedItems.includes(item))

  function toggleCheckedAvailable(item: string) {
    if (checkedAvailable.includes(item)) {
      setCheckedAvailable(checkedAvailable.filter((entry) => entry !== item))
      return
    }
    setCheckedAvailable([...checkedAvailable, item])
  }

  function toggleCheckedSelected(item: string) {
    if (checkedSelected.includes(item)) {
      setCheckedSelected(checkedSelected.filter((entry) => entry !== item))
      return
    }
    setCheckedSelected([...checkedSelected, item])
  }

  function addChecked() {
    props.onSelectedItemsChange(unique([...props.selectedItems, ...checkedAvailable]))
    setCheckedAvailable([])
  }

  function addAll() {
    props.onSelectedItemsChange(unique([...props.selectedItems, ...availablePool]))
    setCheckedAvailable([])
  }

  function removeChecked() {
    props.onSelectedItemsChange(props.selectedItems.filter((item) => !checkedSelected.includes(item)))
    setCheckedSelected([])
  }

  function removeAll() {
    props.onSelectedItemsChange([])
    setCheckedSelected([])
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle>{props.title}</CardTitle>
            <CardDescription>{props.description}</CardDescription>
          </div>
          {props.onRetry ? (
            <Button variant="outline" size="sm" onClick={props.onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {props.error ? <p className="text-sm font-medium text-rose-600">{props.error}</p> : null}
        <div className="grid gap-3 lg:grid-cols-[1fr_auto_1fr]">
          <div className="rounded-xl border border-slate-200 bg-white p-3">
            <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Available ({availablePool.length})</p>
            <div className="max-h-48 space-y-1 overflow-auto">
              {props.isLoading ? (
                <p className="inline-flex items-center gap-2 text-sm text-slate-500">
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                  Loading...
                </p>
              ) : availablePool.length > 0 ? (
                availablePool.map((item) => (
                  <label
                    key={item}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-sm text-slate-700 hover:bg-slate-50"
                  >
                    <input
                      type="checkbox"
                      checked={checkedAvailable.includes(item)}
                      onChange={() => toggleCheckedAvailable(item)}
                      className="h-4 w-4 rounded border-slate-300 accent-cyan-600"
                    />
                    <span>{item}</span>
                  </label>
                ))
              ) : (
                <p className="text-sm text-slate-500">No available items.</p>
              )}
            </div>
          </div>

          <div className="flex items-center justify-center gap-2 lg:flex-col">
            <Button variant="outline" size="sm" onClick={addChecked} disabled={checkedAvailable.length === 0}>
              Add selected
            </Button>
            <Button variant="outline" size="sm" onClick={addAll} disabled={availablePool.length === 0}>
              Add all
            </Button>
            <Button variant="outline" size="sm" onClick={removeChecked} disabled={checkedSelected.length === 0}>
              Remove selected
            </Button>
            <Button variant="outline" size="sm" onClick={removeAll} disabled={props.selectedItems.length === 0}>
              Remove all
            </Button>
          </div>

          <div className="rounded-xl border border-cyan-300 bg-cyan-50/50 p-3">
            <p className="mb-2 text-xs uppercase tracking-wide text-cyan-700">Selected ({props.selectedItems.length})</p>
            <div className="max-h-48 space-y-1 overflow-auto">
              {props.selectedItems.length > 0 ? (
                props.selectedItems.map((item) => (
                  <label
                    key={item}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-sm text-slate-800 hover:bg-cyan-100/60"
                  >
                    <input
                      type="checkbox"
                      checked={checkedSelected.includes(item)}
                      onChange={() => toggleCheckedSelected(item)}
                      className="h-4 w-4 rounded border-slate-300 accent-cyan-600"
                    />
                    <span>{item}</span>
                  </label>
                ))
              ) : (
                <p className="text-sm text-slate-500">No selected items.</p>
              )}
            </div>
          </div>
        </div>
        {props.navigation ? (
          <div className="flex items-center justify-between border-t border-slate-200 pt-3">
            <button
              type="button"
              onClick={props.navigation.onPrevious}
              disabled={props.navigation.disablePrevious}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Previous"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={props.navigation.onNext}
              disabled={props.navigation.disableNext}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Next"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function OracleDiscovery(props: OracleDiscoveryProps) {
  const [activeSelectorStep, setActiveSelectorStep] = useState<1 | 2 | 3 | 4>(1)
  const [isConnecting, setIsConnecting] = useState(false)
  const [isLoadingContainers, setIsLoadingContainers] = useState(false)
  const [isLoadingSchemas, setIsLoadingSchemas] = useState(false)
  const [isLoadingObjects, setIsLoadingObjects] = useState(false)
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [connectError, setConnectError] = useState<string | null>(null)
  const [containerError, setContainerError] = useState<string | null>(null)
  const [schemaError, setSchemaError] = useState<string | null>(null)
  const [objectError, setObjectError] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<DiscoveryAnalyzeResponse | null>(null)

  const connectionPayload = useMemo(
    () => toConnectionPayload(props),
    [props.host, props.port, props.serviceName, props.username, props.password],
  )
  const canCallApis = useMemo(() => isValidConnection(connectionPayload), [connectionPayload])

  const selectedContainer = props.selectedDatabases[0] ?? ""
  const hasContainerSelection = props.selectedDatabases.length > 0
  const hasSchemaSelection = props.selectedSchemas.length > 0
  const nonProcedureSelections = props.selectedObjects.filter(
    (label) => objectType(label) !== "PROCEDURE" && objectType(label) !== "FUNCTION",
  )
  const hasObjectSelection = nonProcedureSelections.length > 0
  const hasNonProcedureOptions =
    props.availableObjects.filter((label) => objectType(label) !== "PROCEDURE" && objectType(label) !== "FUNCTION")
      .length > 0
  const canSkipObjectStep = !hasNonProcedureOptions
  const hasProcedureSelection = props.selectedProcedures.length > 0

  async function loadContainers() {
    if (!canCallApis) {
      return
    }

    try {
      setIsConnecting(true)
      setConnectError(null)
      const connectResult = await testOracleConnection(connectionPayload)
      if (connectResult.connected === false) {
        setConnectError(connectResult.message ?? "Connection failed.")
        return
      }
      setIsConnecting(false)

      setIsLoadingContainers(true)
      setContainerError(null)
      const containerResponse = await getDiscoveryContainers()
      const containers = (containerResponse.containers ?? []).map((item) => item.name)
      props.setAvailableDatabases(containers)

      if (props.selectedDatabases.length === 0) {
        const persisted = readStorageArray(STORAGE_KEYS.container)
        if (persisted.length > 0) {
          props.setSelectedDatabases(persisted.filter((item) => containers.includes(item)))
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load containers."
      if (isConnecting) {
        setConnectError(message)
      } else {
        setContainerError(message)
      }
    } finally {
      setIsConnecting(false)
      setIsLoadingContainers(false)
    }
  }

  async function loadSchemas(containerName: string) {
    if (!containerName) {
      props.setAvailableSchemas([])
      props.setSelectedSchemas([])
      return
    }

    try {
      setIsLoadingSchemas(true)
      setSchemaError(null)
      const schemaResponse = await getDiscoverySchemas(containerName)
      const schemas = schemaResponse.schemas ?? []
      props.setAvailableSchemas(schemas)
      const persisted = readStorageArray(STORAGE_KEYS.schemas)
      if (props.selectedSchemas.length === 0 && persisted.length > 0) {
        props.setSelectedSchemas(persisted.filter((item) => schemas.includes(item)))
      }
    } catch (error) {
      setSchemaError(error instanceof Error ? error.message : "Failed to load schemas.")
    } finally {
      setIsLoadingSchemas(false)
    }
  }

  async function loadObjects(containerName: string, schemas: string[]) {
    if (!containerName || schemas.length === 0) {
      props.setAvailableObjects([])
      props.setSelectedObjects([])
      return
    }

    try {
      setIsLoadingObjects(true)
      setObjectError(null)
      const responses = await Promise.all(schemas.map((schema) => getDiscoveryObjects(schema, containerName)))
      const merged = responses.flatMap((item) => item.objects ?? [])
      const uniqueObjects = Array.from(new Map(merged.map((item) => [objectLabel(item), item])).values())
      const labels = uniqueObjects.map(objectLabel).sort()
      props.setAvailableObjects(labels)
      const persisted = readStorageArray(STORAGE_KEYS.objects)
      if (props.selectedObjects.length === 0 && persisted.length > 0) {
        props.setSelectedObjects(persisted.filter((item) => labels.includes(item)))
      }
    } catch (error) {
      setObjectError(error instanceof Error ? error.message : "Failed to load objects.")
    } finally {
      setIsLoadingObjects(false)
    }
  }

  async function loadProcedureDetail(procedureLabel: string) {
    if (!procedureLabel) {
      setAnalysis(null)
      return
    }
    try {
      setIsLoadingPreview(true)
      setPreviewError(null)
      const schema = objectSchema(procedureLabel) || props.selectedSchemas[0]
      const procedureName = objectName(procedureLabel)
      const detail = await getProcedureDiscovery(procedureName, schema, selectedContainer)
      setAnalysis(detail)
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : "Failed to load procedure detail.")
      setAnalysis(null)
    } finally {
      setIsLoadingPreview(false)
    }
  }

  useEffect(() => {
    if (!canCallApis) {
      setConnectError("Fill valid host, port, service name, username, and password first.")
      return
    }
    void loadContainers()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canCallApis, connectionPayload])

  useEffect(() => {
    writeStorageArray(STORAGE_KEYS.container, props.selectedDatabases)
  }, [props.selectedDatabases])

  useEffect(() => {
    writeStorageArray(STORAGE_KEYS.schemas, props.selectedSchemas)
  }, [props.selectedSchemas])

  useEffect(() => {
    writeStorageArray(STORAGE_KEYS.objects, props.selectedObjects)
  }, [props.selectedObjects])

  useEffect(() => {
    void loadSchemas(selectedContainer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedContainer])

  useEffect(() => {
    void loadObjects(selectedContainer, props.selectedSchemas)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedContainer, props.selectedSchemas])

  useEffect(() => {
    const procedureLabels = props.availableObjects.filter(
      (label) => objectType(label) === "PROCEDURE" || objectType(label) === "FUNCTION",
    )
    props.setAvailableProcedures(procedureLabels)
    if (props.selectedProcedures.length === 0) {
      const persisted = readStorageArray("oracle.discovery.selectedProcedures")
      if (persisted.length > 0) {
        props.setSelectedProcedures(persisted.filter((item) => procedureLabels.includes(item)))
      }
    }
  }, [props.availableObjects, props.selectedProcedures.length, props.setAvailableProcedures, props.setSelectedProcedures])

  useEffect(() => {
    writeStorageArray("oracle.discovery.selectedProcedures", props.selectedProcedures)
  }, [props.selectedProcedures])

  useEffect(() => {
    void loadProcedureDetail(props.selectedProcedures[0] ?? "")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.selectedProcedures])

  useEffect(() => {
    const maxReachableStep: 1 | 2 | 3 | 4 =
      hasObjectSelection || canSkipObjectStep || hasProcedureSelection
        ? 4
        : hasSchemaSelection
          ? 3
          : hasContainerSelection
            ? 2
            : 1
    if (activeSelectorStep > maxReachableStep) {
      setActiveSelectorStep(maxReachableStep)
    }
  }, [
    activeSelectorStep,
    canSkipObjectStep,
    hasContainerSelection,
    hasObjectSelection,
    hasProcedureSelection,
    hasSchemaSelection,
  ])

  function canProceedFromCurrentStep(): boolean {
    if (activeSelectorStep === 1) {
      return hasContainerSelection
    }
    if (activeSelectorStep === 2) {
      return hasSchemaSelection
    }
    if (activeSelectorStep === 3) {
      return hasObjectSelection || hasProcedureSelection || canSkipObjectStep
    }
    return hasProcedureSelection
  }

  function goPreviousStep() {
    setActiveSelectorStep((current) => (current > 1 ? ((current - 1) as 1 | 2 | 3 | 4) : current))
  }

  function goNextStep() {
    if (!canProceedFromCurrentStep()) {
      return
    }
    setActiveSelectorStep((current) => (current < 4 ? ((current + 1) as 1 | 2 | 3 | 4) : current))
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4">
          <div className="grid gap-2 md:grid-cols-4">
            {[
              { id: 1, label: "Container", done: hasContainerSelection },
              { id: 2, label: "Schema", done: hasSchemaSelection },
              { id: 3, label: "Object", done: hasObjectSelection },
              { id: 4, label: "Procedure", done: hasProcedureSelection },
            ].map((step) => {
              const isActive = activeSelectorStep === step.id
              return (
                <button
                  key={step.id}
                  onClick={() => setActiveSelectorStep(step.id as 1 | 2 | 3 | 4)}
                  className={`rounded-xl border px-3 py-2 text-left text-sm transition-all ${
                    isActive
                      ? "border-cyan-300 bg-cyan-50"
                      : step.done
                        ? "border-emerald-300 bg-emerald-50"
                        : "border-slate-200 bg-white"
                  }`}
                >
                  <p className="font-semibold text-slate-900">{step.id}. {step.label}</p>
                  <p className="text-xs text-slate-500">{step.done ? "Selected" : "Pending"}</p>
                </button>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {activeSelectorStep === 1 ? (
        <DualListSelector
          title="Containers"
          description="Step 1: Select Oracle CDB/PDB container."
          availableItems={props.availableDatabases}
          selectedItems={props.selectedDatabases}
          onSelectedItemsChange={(items) => props.setSelectedDatabases(items.slice(0, 1))}
          isLoading={isConnecting || isLoadingContainers}
          error={connectError || containerError}
          onRetry={() => void loadContainers()}
          navigation={{
            onPrevious: goPreviousStep,
            onNext: goNextStep,
            disablePrevious: activeSelectorStep === 1,
            disableNext: !canProceedFromCurrentStep(),
          }}
        />
      ) : null}

      {activeSelectorStep === 2 ? (
        <DualListSelector
          title="Schemas"
          description="Step 2: Select schema."
          availableItems={props.availableSchemas}
          selectedItems={props.selectedSchemas}
          onSelectedItemsChange={props.setSelectedSchemas}
          isLoading={isLoadingSchemas}
          error={schemaError}
          onRetry={() => void loadSchemas(selectedContainer)}
          navigation={{
            onPrevious: goPreviousStep,
            onNext: goNextStep,
            disablePrevious: activeSelectorStep === 1,
            disableNext: !canProceedFromCurrentStep(),
          }}
        />
      ) : null}

      {activeSelectorStep === 3 ? (
        <DualListSelector
          title="Objects"
          description="Step 3: Select object (PROCEDURE/FUNCTION/PACKAGE/TRIGGER)."
          availableItems={props.availableObjects.filter(
            (label) => objectType(label) !== "PROCEDURE" && objectType(label) !== "FUNCTION",
          )}
          selectedItems={props.selectedObjects.filter(
            (label) => objectType(label) !== "PROCEDURE" && objectType(label) !== "FUNCTION",
          )}
          onSelectedItemsChange={(items) =>
            props.setSelectedObjects([
              ...props.selectedObjects.filter(
                (label) => objectType(label) === "PROCEDURE" || objectType(label) === "FUNCTION",
              ),
              ...items,
            ])
          }
          isLoading={isLoadingObjects}
          error={objectError}
          onRetry={() => void loadObjects(selectedContainer, props.selectedSchemas)}
          navigation={{
            onPrevious: goPreviousStep,
            onNext: goNextStep,
            disablePrevious: activeSelectorStep === 1,
            disableNext: !canProceedFromCurrentStep(),
          }}
        />
      ) : null}

      {activeSelectorStep === 4 ? (
        <DualListSelector
          title="Stored Procedures"
          description="Step 4: Choose a procedure to preview analysis."
          availableItems={props.availableProcedures}
          selectedItems={props.selectedProcedures}
          onSelectedItemsChange={(items) => props.setSelectedProcedures(items.slice(0, 1))}
          isLoading={isLoadingPreview}
          error={previewError}
          onRetry={() => void loadProcedureDetail(props.selectedProcedures[0] ?? "")}
          navigation={{
            onPrevious: goPreviousStep,
            onNext: goNextStep,
            disablePrevious: activeSelectorStep === 1,
            disableNext: activeSelectorStep === 4 || !canProceedFromCurrentStep(),
          }}
        />
      ) : null}

      {hasProcedureSelection ? (
        <Card>
          <CardHeader>
            <CardTitle>Metadata Analysis & Conversion Preview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoadingPreview ? (
              <p className="inline-flex items-center gap-2 text-sm text-slate-600">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                Loading metadata...
              </p>
            ) : null}

            {analysis ? (
              <>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Procedure</p>
                    <p className="text-sm font-semibold text-slate-900">{analysis.procedureName}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Object Type</p>
                    <p className="text-sm font-semibold text-slate-900">{analysis.objectType}</p>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Tables Used</p>
                    {(analysis.tablesUsed ?? []).length > 0 ? (analysis.tablesUsed ?? []).join(", ") : "No tables detected"}
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Operations</p>
                    {(analysis.operations ?? []).length > 0 ? (analysis.operations ?? []).join(", ") : "No operations detected"}
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Variables</p>
                    {(analysis.localVariables ?? []).length > 0
                      ? (analysis.localVariables ?? []).map((item) => `${item.name} (${item.type})`).join(", ")
                      : "No variables detected"}
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Exceptions</p>
                    {(analysis.exceptions ?? []).length > 0 ? (analysis.exceptions ?? []).join(", ") : "No exceptions detected"}
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-4">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                    LOC: {analysis.complexity?.linesOfCode ?? 0}
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                    Queries: {analysis.complexity?.numberOfQueries ?? 0}
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                    Conditions: {analysis.complexity?.numberOfConditions ?? 0}
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                    Loops: {analysis.complexity?.numberOfLoops ?? 0}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Dependency Graph</p>
                  <p>Tables: {(analysis.dependencyGraph?.tablesUsed ?? []).join(", ") || "None"}</p>
                  <p>Procedures: {(analysis.dependencyGraph?.proceduresCalled ?? []).join(", ") || "None"}</p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Conversion Preview</p>
                  <p>Entities: {(analysis.conversionPreview?.entities ?? []).join(", ") || "None"}</p>
                  <p>Repositories: {(analysis.conversionPreview?.repositories ?? []).join(", ") || "None"}</p>
                  <p>Services: {(analysis.conversionPreview?.services ?? []).join(", ") || "None"}</p>
                  <p>Controllers: {(analysis.conversionPreview?.controllers ?? []).join(", ") || "None"}</p>
                  <p>DTOs: {(analysis.conversionPreview?.dtos ?? []).join(", ") || "None"}</p>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500">Select a stored procedure to load metadata analysis and conversion preview.</p>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
