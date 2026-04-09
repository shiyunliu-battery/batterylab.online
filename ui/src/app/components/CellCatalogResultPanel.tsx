"use client";

import React, { useCallback, useMemo, useState } from "react";
import {
  BatteryCharging,
  Building2,
  ChartNoAxesCombined,
  FlaskConical,
  Waves,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useChatContext } from "@/providers/ChatProvider";
import { cn } from "@/lib/utils";

type RecordLike = Record<string, unknown>;

interface CellRecord extends RecordLike {
  cell_id?: string;
  display_name?: string;
  manufacturer?: string;
  model?: string;
  project_chemistry_hint?: string;
  form_factor?: string | null;
  completeness_status?: string;
  approval_status?: string;
  approval_basis?: string;
  confidence_status?: string;
  eligibility_tags?: string[];
  waived_missing_required_fields?: string[];
  literature_reference?: RecordLike;
  electrical?: RecordLike;
  planner_context?: RecordLike;
}

interface ManufacturerGroup extends RecordLike {
  manufacturer?: string;
  count?: number;
  cells?: CellRecord[];
}

interface CellCatalogResultPanelProps {
  toolName: string;
  payload: RecordLike;
}

interface PlannerPreset {
  methodId: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  plannerInstruction: string;
}

const PLANNER_PRESETS: PlannerPreset[] = [
  {
    methodId: "soc_ocv",
    label: "SOC-OCV",
    icon: Waves,
    plannerInstruction:
      "Start a SOC-OCV planning flow for this selected cell. Ask only for missing instrument information if needed.",
  },
  {
    methodId: "pulse_hppc",
    label: "HPPC",
    icon: ChartNoAxesCombined,
    plannerInstruction:
      "Start an HPPC planning flow for this selected cell. Ask only for missing instrument information if needed.",
  },
  {
    methodId: "capacity_test",
    label: "Capacity",
    icon: BatteryCharging,
    plannerInstruction:
      "Start a capacity or rate-capability planning flow for this selected cell. Ask only for missing instrument information if needed.",
  },
  {
    methodId: "cycle_life",
    label: "Cycle life",
    icon: FlaskConical,
    plannerInstruction:
      "Start a cycle-life planning flow for this selected cell. Ask only for missing instrument information if needed.",
  },
] as const;

function asRecord(value: unknown): RecordLike | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as RecordLike)
    : null;
}

function asRecordArray(value: unknown): RecordLike[] {
  return Array.isArray(value)
    ? value.filter(
        (item): item is RecordLike =>
          typeof item === "object" && item !== null && !Array.isArray(item)
      )
    : [];
}

function formatValue(value: unknown, suffix = ""): string {
  if (value === null || value === undefined || value === "") return "n/a";
  if (typeof value === "number") {
    return `${Number.isInteger(value) ? value : value.toFixed(3).replace(/\.?0+$/, "")}${suffix}`;
  }
  return `${String(value)}${suffix}`;
}

function formatTag(value: unknown): string {
  if (value === null || value === undefined || value === "") return "unknown";
  return String(value).replace(/_/g, " ");
}

function getStatusChipClasses(value: string | undefined): string {
  const normalized = String(value || "unknown").toLowerCase();
  if (
    normalized === "approved" ||
    normalized === "complete" ||
    normalized === "high"
  ) {
    return "border-[rgba(52,126,95,0.18)] bg-[rgba(229,244,236,0.95)] text-[rgb(41,104,79)]";
  }
  if (normalized === "literature_backed") {
    return "border-[rgba(176,115,28,0.18)] bg-[rgba(251,241,221,0.95)] text-[rgb(135,87,20)]";
  }
  return "border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] text-muted-foreground";
}

function getRecordId(record: CellRecord): string {
  return String(record.cell_id || record.display_name || record.model || "unknown");
}

function buildPlannerPrompt(record: CellRecord, preset: PlannerPreset): string {
  const plannerContext = asRecord(record.planner_context) || {};
  const electrical = asRecord(record.electrical) || {};
  const chemistry = String(
    plannerContext.chemistry || record.project_chemistry_hint || "unknown"
  );
  const formFactor = String(
    plannerContext.form_factor || record.form_factor || "unknown"
  );

  return [
    `Use imported cell record \`${getRecordId(record)}\` as the selected cell for protocol planning.`,
    `Selected cell: ${record.display_name || getRecordId(record)}.`,
    `Manufacturer: ${record.manufacturer || "unknown"}.`,
    `Chemistry hint: \`${chemistry}\`.`,
    `Form factor: \`${formFactor}\`.`,
    `Nominal capacity: ${formatValue(electrical.nominal_capacity_ah, " Ah")}.`,
    `Nominal voltage: ${formatValue(electrical.nominal_voltage_v, " V")}.`,
    `Charge voltage: ${formatValue(electrical.charge_voltage_v, " V")}.`,
    `Discharge cut-off voltage: ${formatValue(electrical.discharge_cutoff_v, " V")}.`,
    `Preferred method_id: \`${preset.methodId}\`.`,
    preset.plannerInstruction,
    "Use the controlled registries and imported cell metadata together, and keep hard safety constraints in the registry layer.",
  ].join(" ");
}

function getSupportedPresets(record: CellRecord): PlannerPreset[] {
  const plannerContext = asRecord(record.planner_context) || {};
  const supportedMethods = Array.isArray(plannerContext.supported_methods)
    ? plannerContext.supported_methods.map((item) => String(item))
    : [];
  if (supportedMethods.length === 0) return [...PLANNER_PRESETS];
  return PLANNER_PRESETS.filter((preset) => supportedMethods.includes(preset.methodId));
}

function CellCard({
  record,
  selected,
  onSelect,
}: {
  record: CellRecord;
  selected: boolean;
  onSelect: () => void;
}) {
  const electrical = asRecord(record.electrical) || {};
  const literatureReference = asRecord(record.literature_reference) || {};
  const citationText =
    typeof literatureReference.citation_text === "string"
      ? literatureReference.citation_text
      : null;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "rounded-[14px] border px-3 py-3 text-left transition-colors",
        selected
          ? "border-[rgba(36,87,93,0.26)] bg-[rgba(232,242,239,0.85)]"
          : "border-[rgba(24,33,38,0.08)] bg-white hover:bg-[rgba(247,245,241,0.9)]"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-foreground">
            {record.display_name || getRecordId(record)}
          </div>
          <div className="truncate text-xs text-muted-foreground">
            {record.manufacturer || "unknown manufacturer"}
          </div>
          {record.approval_basis === "literature_backed_manual_asset" && (
            <div className="truncate text-[11px] text-muted-foreground">
              Literature-backed sodium asset
            </div>
          )}
          <div className="mt-2 flex flex-wrap gap-1">
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.08em]",
                getStatusChipClasses(record.completeness_status)
              )}
            >
              {formatTag(record.completeness_status)}
            </span>
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.08em]",
                getStatusChipClasses(record.approval_status)
              )}
            >
              {formatTag(record.approval_status)}
            </span>
          </div>
        </div>
        <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
          {record.project_chemistry_hint || "unknown"}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-muted-foreground">
        <div>Capacity: {formatValue(electrical.nominal_capacity_ah, " Ah")}</div>
        <div>Nominal V: {formatValue(electrical.nominal_voltage_v, " V")}</div>
        <div>Form: {formatValue(record.form_factor)}</div>
        <div>Cut-off: {formatValue(electrical.discharge_cutoff_v, " V")}</div>
        {citationText && (
          <div className="col-span-2 truncate">
            Source: {citationText}
          </div>
        )}
      </div>
    </button>
  );
}

export function CellCatalogResultPanel({
  toolName,
  payload,
}: CellCatalogResultPanelProps) {
  const { sendMessage, isLoading } = useChatContext();

  const directRecord = useMemo(
    () => asRecord(payload.record) as CellRecord | null,
    [payload]
  );

  const records = useMemo(() => {
    if (directRecord) return [directRecord];
    return asRecordArray(payload.records) as CellRecord[];
  }, [directRecord, payload]);

  const manufacturerGroups = useMemo(
    () => asRecordArray(payload.manufacturer_groups) as ManufacturerGroup[],
    [payload]
  );

  const topRepresentativeCells = useMemo(() => {
    const items = asRecordArray(payload.top_representative_cells) as CellRecord[];
    return items.length > 0 ? items : records.slice(0, 6);
  }, [payload, records]);

  const initialSelectedId = topRepresentativeCells[0]
    ? getRecordId(topRepresentativeCells[0])
    : directRecord
      ? getRecordId(directRecord)
      : records[0]
        ? getRecordId(records[0])
        : null;

  const [selectedCellId, setSelectedCellId] = useState<string | null>(
    initialSelectedId
  );

  const selectedRecord = useMemo(() => {
    if (!selectedCellId) return records[0] || null;
    return records.find((record) => getRecordId(record) === selectedCellId) || null;
  }, [records, selectedCellId]);

  const supportedPresets = selectedRecord
    ? getSupportedPresets(selectedRecord)
    : [];

  const handlePlannerAction = useCallback(
    (preset: PlannerPreset) => {
      if (!selectedRecord || isLoading) return;
      sendMessage(buildPlannerPrompt(selectedRecord, preset));
    },
    [isLoading, selectedRecord, sendMessage]
  );

  const summary = useMemo(
    () => ({
      recordCount:
        typeof payload.record_count === "number" ? payload.record_count : records.length,
      approvedRecordCount:
        typeof payload.approved_record_count === "number"
          ? payload.approved_record_count
          : records.length,
      rawRecordCount:
        typeof payload.raw_record_count === "number"
          ? payload.raw_record_count
          : records.length,
      excludedRecordCount:
        typeof payload.excluded_record_count === "number"
          ? payload.excluded_record_count
          : 0,
      manufacturerCount:
        manufacturerGroups.length > 0
          ? manufacturerGroups.length
          : new Set(records.map((record) => String(record.manufacturer || "unknown"))).size,
    }),
    [manufacturerGroups.length, payload, records]
  );

  if (records.length === 0) {
    return (
      <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-white p-4 text-sm text-muted-foreground">
        No imported cell records were available in this result.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-sm font-medium text-foreground">
            Imported cell catalog
          </div>
          <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] px-2 py-0.5 text-[10px] text-muted-foreground">
            {summary.recordCount} records
          </span>
          <span className="rounded-full border border-[rgba(52,126,95,0.18)] bg-[rgba(229,244,236,0.95)] px-2 py-0.5 text-[10px] text-[rgb(41,104,79)]">
            {summary.approvedRecordCount} approved
          </span>
          <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] px-2 py-0.5 text-[10px] text-muted-foreground">
            {summary.rawRecordCount} raw
          </span>
          <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] px-2 py-0.5 text-[10px] text-muted-foreground">
            {summary.excludedRecordCount} excluded
          </span>
          <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] px-2 py-0.5 text-[10px] text-muted-foreground">
            {summary.manufacturerCount} manufacturers
          </span>
        </div>
      </div>

      {topRepresentativeCells.length > 0 && (
        <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-white p-4">
          <h4 className="mb-3 text-sm font-medium text-foreground">
            Top representative cells
          </h4>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {topRepresentativeCells.map((record) => (
              <CellCard
                key={`rep-${getRecordId(record)}`}
                record={record}
                selected={getRecordId(record) === getRecordId(selectedRecord || {})}
                onSelect={() => setSelectedCellId(getRecordId(record))}
              />
            ))}
          </div>
        </div>
      )}

      {selectedRecord && (
        <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-white p-4">
          <h4 className="mb-3 text-sm font-medium text-foreground">
            Use in protocol planner
          </h4>
          <div className="rounded-[12px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.75)] px-3 py-3">
            {(() => {
              const literatureReference =
                asRecord(selectedRecord.literature_reference) || {};
              const citationText =
                typeof literatureReference.citation_text === "string"
                  ? literatureReference.citation_text
                  : null;
              return (
                <>
            <div className="text-sm font-medium text-foreground">
              {selectedRecord.display_name || getRecordId(selectedRecord)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {selectedRecord.manufacturer || "unknown"} ·{" "}
              {selectedRecord.project_chemistry_hint || "unknown"} ·{" "}
              {selectedRecord.form_factor || "unknown"}
            </div>
            {selectedRecord.approval_basis && (
              <div className="mt-1 text-[11px] text-muted-foreground">
                Approval basis: {formatTag(selectedRecord.approval_basis)}
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-1">
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.08em]",
                  getStatusChipClasses(selectedRecord.completeness_status)
                )}
              >
                {formatTag(selectedRecord.completeness_status)}
              </span>
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.08em]",
                  getStatusChipClasses(selectedRecord.approval_status)
                )}
              >
                {formatTag(selectedRecord.approval_status)}
              </span>
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.08em]",
                  getStatusChipClasses(selectedRecord.confidence_status)
                )}
              >
                {formatTag(selectedRecord.confidence_status)}
              </span>
            </div>
            <div className="mt-3 grid gap-2 text-[11px] text-muted-foreground md:grid-cols-2">
              <div>
                Capacity:{" "}
                {formatValue(
                  asRecord(selectedRecord.electrical)?.nominal_capacity_ah,
                  " Ah"
                )}
              </div>
              <div>
                Nominal V:{" "}
                {formatValue(
                  asRecord(selectedRecord.electrical)?.nominal_voltage_v,
                  " V"
                )}
              </div>
              <div>
                Charge V:{" "}
                {formatValue(
                  asRecord(selectedRecord.electrical)?.charge_voltage_v,
                  " V"
                )}
              </div>
              <div>
                Cut-off V:{" "}
                {formatValue(
                  asRecord(selectedRecord.electrical)?.discharge_cutoff_v,
                  " V"
                )}
              </div>
              <div>
                Waived fields:{" "}
                {Array.isArray(selectedRecord.waived_missing_required_fields) &&
                selectedRecord.waived_missing_required_fields.length > 0
                  ? selectedRecord.waived_missing_required_fields.join(", ")
                  : "none"}
              </div>
              <div>
                Evidence DOI: {formatValue(literatureReference.doi)}
              </div>
              {citationText && (
                <div className="md:col-span-2">
                  Source: {citationText}
                </div>
              )}
            </div>
                </>
              );
            })()}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {supportedPresets.map((preset) => {
              const Icon = preset.icon;
              return (
                <Button
                  key={preset.methodId}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => handlePlannerAction(preset)}
                  disabled={isLoading}
                  className="rounded-full"
                >
                  <Icon className="h-4 w-4" />
                  {preset.label}
                </Button>
              );
            })}
          </div>
        </div>
      )}

      {manufacturerGroups.length > 0 && toolName === "search_imported_cell_catalog" && (
        <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-white p-4">
          <div className="mb-3 flex items-center gap-2">
            <Building2 className="h-4 w-4 text-muted-foreground" />
            <h4 className="text-sm font-medium text-foreground">
              By manufacturer
            </h4>
          </div>
          <div className="space-y-3">
            {manufacturerGroups.map((group) => (
              <div
                key={String(group.manufacturer || "unknown")}
                className="rounded-[12px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.75)] p-3"
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-foreground">
                      {group.manufacturer || "unknown"}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {formatValue(group.count)} matching cells
                    </div>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {(group.cells || []).map((record) => (
                    <CellCard
                      key={`${String(group.manufacturer)}-${getRecordId(record)}`}
                      record={record}
                      selected={getRecordId(record) === getRecordId(selectedRecord || {})}
                      onSelect={() => setSelectedCellId(getRecordId(record))}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
