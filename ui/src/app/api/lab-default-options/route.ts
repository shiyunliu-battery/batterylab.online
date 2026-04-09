import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

const repoRoot = path.resolve(process.cwd(), "..");
const equipmentRulesPath = path.join(repoRoot, "data", "kb", "equipment_rules.json");
const manualIndexPath = path.join(
  repoRoot,
  "data",
  "reference",
  "equipment_manuals",
  "manual_index.json"
);

type LabDefaultOption = {
  value: string;
  label: string;
  description?: string;
};

type EquipmentRule = {
  label?: string;
  max_current_a?: number;
  max_voltage_v?: number;
  max_parallel_channels?: number;
  min_sampling_seconds?: number;
  notes?: string[];
};

type ThermalChamberRule = {
  label?: string;
  temperature_range_c?: [number, number];
  notes?: string[];
};

type EquipmentRulesPayload = Record<string, unknown> & {
  thermal_chambers?: Record<string, ThermalChamberRule>;
};

type ManualAsset = {
  asset_id: string;
  equipment_type: string;
  manufacturer: string;
  model: string;
  coverage?: string[];
  notes?: string[];
};

function isInstrumentRule(value: unknown): value is EquipmentRule {
  return Boolean(
    value &&
      typeof value === "object" &&
      "label" in value &&
      "max_current_a" in value &&
      "max_voltage_v" in value
  );
}

function formatCyclerDescription(rule: EquipmentRule): string {
  const capability = `${rule.max_current_a} A / ${rule.max_voltage_v} V`;
  const channelSummary = rule.max_parallel_channels
    ? `, ${rule.max_parallel_channels} channel${rule.max_parallel_channels === 1 ? "" : "s"}`
    : "";
  const note = rule.notes?.[0];
  return note ? `${capability}${channelSummary}. ${note}` : `${capability}${channelSummary}`;
}

function formatChamberDescription(rule: ThermalChamberRule): string {
  const range = Array.isArray(rule.temperature_range_c)
    ? `${rule.temperature_range_c[0]} to ${rule.temperature_range_c[1]} C`
    : "Temperature range not summarized";
  const note = rule.notes?.[0];
  return note ? `${range}. ${note}` : range;
}

function formatEisDescription(manual: ManualAsset): string {
  const firstCoverage = manual.coverage?.[0];
  if (firstCoverage) {
    return firstCoverage;
  }
  const firstNote = manual.notes?.[0];
  return firstNote || manual.equipment_type;
}

function sortOptions(options: LabDefaultOption[]): LabDefaultOption[] {
  return [...options].sort((left, right) => left.label.localeCompare(right.label));
}

export const runtime = "nodejs";

export async function GET() {
  try {
    const [equipmentRulesRaw, manualIndexRaw] = await Promise.all([
      fs.readFile(equipmentRulesPath, "utf-8"),
      fs.readFile(manualIndexPath, "utf-8"),
    ]);

    const equipmentRules = JSON.parse(equipmentRulesRaw) as EquipmentRulesPayload;
    const manualIndex = JSON.parse(manualIndexRaw) as { manuals?: ManualAsset[] };

    const cyclerEntries = Object.entries(equipmentRules).filter(
      (entry): entry is [string, EquipmentRule] =>
        entry[0] !== "thermal_chambers" && isInstrumentRule(entry[1])
    );
    const cyclers = sortOptions(
      cyclerEntries.map(([value, rule]) => ({
        value,
        label: rule.label || value,
        description: formatCyclerDescription(rule),
      }))
    );

    const thermalChambers = sortOptions(
      Object.entries(equipmentRules.thermal_chambers ?? {}).map(([value, rule]) => ({
        value,
        label: rule.label || value,
        description: formatChamberDescription(rule),
      }))
    );

    const eisInstruments = sortOptions(
      (manualIndex.manuals ?? [])
        .filter((manual) => manual.equipment_type === "potentiostat_hardware_datasheet")
        .map((manual) => ({
          value: manual.asset_id,
          label: `${manual.manufacturer} ${manual.model}`,
          description: formatEisDescription(manual),
        }))
    );

    return NextResponse.json({
      cyclers,
      thermalChambers,
      eisInstruments,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to load approved lab equipment options.",
      },
      { status: 500 }
    );
  }
}
