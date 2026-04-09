export type LabDefaultOption = {
  value: string;
  label: string;
  description?: string;
};

export type LabDefaultOptionsPayload = {
  cyclers: LabDefaultOption[];
  thermalChambers: LabDefaultOption[];
  eisInstruments: LabDefaultOption[];
};

export const EMPTY_LAB_DEFAULT_OPTIONS: LabDefaultOptionsPayload = {
  cyclers: [],
  thermalChambers: [],
  eisInstruments: [],
};

export function getLabDefaultDisplayLabel(
  label: string | undefined,
  fallbackValue: string | undefined
): string | undefined {
  const normalizedLabel = label?.trim();
  if (normalizedLabel) {
    return normalizedLabel;
  }

  const normalizedFallback = fallbackValue?.trim();
  return normalizedFallback || undefined;
}

export function findLabDefaultOption(
  options: LabDefaultOption[],
  value: string | undefined
): LabDefaultOption | undefined {
  if (!value) {
    return undefined;
  }
  return options.find((option) => option.value === value);
}
