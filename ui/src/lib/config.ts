export interface LabDefaultsConfig {
  defaultInstrumentId?: string;
  defaultInstrumentLabel?: string;
  defaultThermalChamberId?: string;
  defaultThermalChamberLabel?: string;
  defaultEisInstrumentId?: string;
  defaultEisInstrumentLabel?: string;
  defaultEisSetupNotes?: string;
}

export type ConversationDensity = "comfortable" | "compact";

export interface UiPreferencesConfig {
  conversationDensity?: ConversationDensity;
  showThreadSummary?: boolean;
  smoothStreaming?: boolean;
}

export interface StandaloneConfig {
  deploymentUrl: string;
  assistantId: string;
  labDefaults?: LabDefaultsConfig;
  uiPreferences?: UiPreferencesConfig;
}

const CONFIG_KEY = "battery-lab-config-v2";
const DEFAULT_DEPLOYMENT_URL = "/api/langgraph";
const DEFAULT_ASSISTANT_ID = "battery_lab";

export const DEFAULT_UI_PREFERENCES: Required<UiPreferencesConfig> = {
  conversationDensity: "comfortable",
  showThreadSummary: true,
  smoothStreaming: true,
};

function normalizeOptionalText(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function normalizeLabDefaults(value: unknown): LabDefaultsConfig | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }

  const record = value as Record<string, unknown>;
  const defaultInstrumentId = normalizeOptionalText(record.defaultInstrumentId);
  const defaultInstrumentLabel = normalizeOptionalText(
    record.defaultInstrumentLabel
  );
  const defaultThermalChamberId = normalizeOptionalText(
    record.defaultThermalChamberId
  );
  const defaultThermalChamberLabel = normalizeOptionalText(
    record.defaultThermalChamberLabel
  );
  const defaultEisInstrumentId = normalizeOptionalText(
    record.defaultEisInstrumentId
  );
  const defaultEisInstrumentLabel = normalizeOptionalText(
    record.defaultEisInstrumentLabel
  );
  const defaultEisSetupNotes = normalizeOptionalText(record.defaultEisSetupNotes);

  const normalized: LabDefaultsConfig = {
    defaultInstrumentId,
    defaultInstrumentLabel: defaultInstrumentId ? defaultInstrumentLabel : undefined,
    defaultThermalChamberId,
    defaultThermalChamberLabel: defaultThermalChamberId
      ? defaultThermalChamberLabel
      : undefined,
    defaultEisInstrumentId,
    defaultEisInstrumentLabel: defaultEisInstrumentId
      ? defaultEisInstrumentLabel
      : undefined,
    defaultEisSetupNotes:
      defaultEisSetupNotes ??
      (defaultEisInstrumentId ? undefined : defaultEisInstrumentLabel),
  };

  if (
    !normalized.defaultInstrumentId &&
    !normalized.defaultInstrumentLabel &&
    !normalized.defaultThermalChamberId &&
    !normalized.defaultThermalChamberLabel &&
    !normalized.defaultEisInstrumentId &&
    !normalized.defaultEisInstrumentLabel &&
    !normalized.defaultEisSetupNotes
  ) {
    return undefined;
  }

  return normalized;
}

function normalizeOptionalBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function normalizeUiPreferences(value: unknown): UiPreferencesConfig | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }

  const record = value as Record<string, unknown>;
  const smoothStreaming = normalizeOptionalBoolean(record.smoothStreaming);

  if (smoothStreaming === undefined) {
    return undefined;
  }

  return {
    ...(smoothStreaming !== undefined ? { smoothStreaming } : {}),
  };
}

function buildInitialConfig(): StandaloneConfig {
  const assistantId =
    normalizeOptionalText(process.env.NEXT_PUBLIC_ASSISTANT_ID) ??
    DEFAULT_ASSISTANT_ID;

  return {
    deploymentUrl: DEFAULT_DEPLOYMENT_URL,
    assistantId,
    uiPreferences: { ...DEFAULT_UI_PREFERENCES },
  };
}

function withDefaultUiPreferences(
  value?: UiPreferencesConfig
): Required<UiPreferencesConfig> {
  return {
    ...DEFAULT_UI_PREFERENCES,
    ...value,
  };
}

function normalizeStoredConfig(
  value: unknown
): Pick<StandaloneConfig, "labDefaults" | "uiPreferences"> | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const record = value as Record<string, unknown>;

  return {
    labDefaults: normalizeLabDefaults(record.labDefaults),
    uiPreferences: normalizeUiPreferences(record.uiPreferences),
  };
}

export function getInitialConfig(): StandaloneConfig {
  return buildInitialConfig();
}

export function getConfig(): StandaloneConfig | null {
  const runtimeConfig = buildInitialConfig();

  if (typeof window === "undefined") {
    return runtimeConfig;
  }

  const stored = localStorage.getItem(CONFIG_KEY);
  if (!stored) {
    return runtimeConfig;
  }

  try {
    const normalized = normalizeStoredConfig(JSON.parse(stored));
    return {
      ...runtimeConfig,
      labDefaults: normalized?.labDefaults,
      uiPreferences: withDefaultUiPreferences(normalized?.uiPreferences),
    };
  } catch {
    return {
      ...runtimeConfig,
      uiPreferences: { ...DEFAULT_UI_PREFERENCES },
    };
  }
}

export function saveConfig(config: StandaloneConfig): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(
    CONFIG_KEY,
    JSON.stringify({
      labDefaults: normalizeLabDefaults(config.labDefaults),
      uiPreferences: normalizeUiPreferences(config.uiPreferences),
    })
  );
}
