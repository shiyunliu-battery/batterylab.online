import type { Assistant } from "@langchain/langgraph-sdk";

function normalizeScopeValue(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function isAssistantUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
    value.trim()
  );
}

export function buildThreadMetadata(
  assistant: Assistant | null | undefined
): Record<string, string> | undefined {
  const assistantId = normalizeScopeValue(assistant?.assistant_id);
  const graphId = normalizeScopeValue(assistant?.graph_id);

  if (!assistantId && !graphId) {
    return undefined;
  }

  return {
    ...(assistantId ? { assistant_id: assistantId } : {}),
    ...(graphId ? { graph_id: graphId } : {}),
  };
}

export function getThreadMetadataFilter(
  assistantScope: string
): Record<string, string> | undefined {
  const normalizedScope = normalizeScopeValue(assistantScope);
  if (!normalizedScope) {
    return undefined;
  }

  return isAssistantUuid(normalizedScope)
    ? { assistant_id: normalizedScope }
    : { graph_id: normalizedScope };
}

export function doesThreadMatchAssistantScope(
  thread: { metadata?: unknown } | null | undefined,
  assistantScope: string
): boolean {
  const normalizedScope = normalizeScopeValue(assistantScope);
  if (!normalizedScope) {
    return false;
  }

  const metadata =
    thread?.metadata && typeof thread.metadata === "object"
      ? (thread.metadata as Record<string, unknown>)
      : {};
  const assistantId = normalizeScopeValue(metadata.assistant_id);
  const graphId = normalizeScopeValue(metadata.graph_id);

  return isAssistantUuid(normalizedScope)
    ? assistantId === normalizedScope
    : graphId === normalizedScope;
}
