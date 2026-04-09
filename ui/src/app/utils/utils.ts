import { Message } from "@langchain/langgraph-sdk";
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const INTERNAL_IDENTIFIER_LABELS: Record<string, string> = {
  load_battery_knowledge: "battery knowledge lookup",
  load_pdf_test_method: "method detail lookup",
  plan_standard_test: "standard test planner",
  design_battery_protocol: "protocol planner",
  search_imported_cell_catalog: "cell catalog search",
  export_imported_cell_catalog: "cell catalog export",
  load_imported_cell_record: "cell record lookup",
  extract_uploaded_cell_datasheet: "datasheet extractor",
  extract_uploaded_cell_datasheet_to_provisional_asset: "datasheet review intake",
  search_knowledge_evidence_cards: "knowledge evidence search",
  load_knowledge_source: "knowledge source lookup",
  review_request_protocol: "protocol review",
};

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function toTitleCaseWords(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

export function humanizeInternalIdentifier(value: string): string {
  const normalized = value.trim();
  if (!normalized) {
    return "";
  }

  const explicitLabel = INTERNAL_IDENTIFIER_LABELS[normalized];
  if (explicitLabel) {
    return toTitleCaseWords(explicitLabel);
  }

  if (normalized.includes("_")) {
    return toTitleCaseWords(normalized.replace(/_/g, " "));
  }

  return normalized;
}

function replaceInternalIdentifiers(content: string): string {
  return Object.entries(INTERNAL_IDENTIFIER_LABELS).reduce(
    (nextContent, [identifier, label]) =>
      nextContent.replace(
        new RegExp(`(?<![A-Za-z0-9])${escapeRegExp(identifier)}(?![A-Za-z0-9])`, "g"),
        label
      ),
    content
  );
}

export function extractStringFromMessageContent(message: Message): string {
  return typeof message.content === "string"
    ? message.content
    : Array.isArray(message.content)
    ? message.content
        .filter(
          (c: unknown) =>
            (typeof c === "object" &&
              c !== null &&
              "type" in c &&
              (c as { type: string }).type === "text") ||
            typeof c === "string"
        )
        .map((c: unknown) =>
          typeof c === "string"
            ? c
            : typeof c === "object" && c !== null && "text" in c
            ? (c as { text?: string }).text || ""
            : ""
        )
        .join("\n\n")
    : "";
}

export function sanitizeAssistantDisplayText(content: string): string {
  return replaceInternalIdentifiers(content)
    .replace(/Clean Experiment Plan/g, "Experiment Plan")
    .replace(/Core Handbook Reference/g, "Core Method Reference")
    .replace(/Strict Handbook Reference Mode/g, "Strict Method Reference Mode")
    .replace(/Handbook Evidence Cards/g, "Method Evidence Cards")
    .replace(/handbook_source_id/gi, "method_source_id")
    .replace(/core_handbook_primary/gi, "core_method_primary")
    .replace(/core_handbook_locked/gi, "core_method_locked")
    .replace(/core_handbook_primary/gi, "core_method_primary")
    .replace(/strict_handbook_reference_mode/gi, "strict_method_reference_mode")
    .replace(/handbook_/gi, "method_")
    .replace(/_handbook/gi, "_method")
    .replace(/handbook source-example/gi, "source-example")
    .replace(/handbook chapter/gi, "source reference")
    .replace(/handbook method/gi, "structured method")
    .replace(/the handbook/gi, "the method reference")
    .replace(/\bhandbook\b/gi, "method reference");
}

export function extractSubAgentContent(data: unknown): string {
  if (typeof data === "string") {
    return data;
  }

  if (data && typeof data === "object") {
    const dataObj = data as Record<string, unknown>;

    // Try to extract description first
    if (dataObj.description && typeof dataObj.description === "string") {
      return dataObj.description;
    }

    // Then try prompt
    if (dataObj.prompt && typeof dataObj.prompt === "string") {
      return dataObj.prompt;
    }

    // For output objects, try result
    if (dataObj.result && typeof dataObj.result === "string") {
      return dataObj.result;
    }

    // Fallback to JSON stringification
    return JSON.stringify(data, null, 2);
  }

  // Fallback for any other type
  return JSON.stringify(data, null, 2);
}

export function isPreparingToCallTaskTool(messages: Message[]): boolean {
  const lastMessage = messages[messages.length - 1];
  return (
    (lastMessage.type === "ai" &&
      lastMessage.tool_calls?.some(
        (call: { name?: string }) => call.name === "task"
      )) ||
    false
  );
}

export function formatMessageForLLM(message: Message): string {
  let role: string;
  if (message.type === "human") {
    role = "Human";
  } else if (message.type === "ai") {
    role = "Assistant";
  } else if (message.type === "tool") {
    role = `Tool Result`;
  } else {
    role = message.type || "Unknown";
  }

  const timestamp = message.id ? ` (${message.id.slice(0, 8)})` : "";

  let contentText = "";

  // Extract content text
  if (typeof message.content === "string") {
    contentText = message.content;
  } else if (Array.isArray(message.content)) {
    const textParts: string[] = [];

    message.content.forEach((part: any) => {
      if (typeof part === "string") {
        textParts.push(part);
      } else if (part && typeof part === "object" && part.type === "text") {
        textParts.push(part.text || "");
      }
      // Ignore other types like tool_use in content - we handle tool calls separately
    });

    contentText = textParts.join("\n\n").trim();
  }

  // For tool messages, include additional tool metadata
  if (message.type === "tool") {
    const toolName = (message as any).name || "unknown_tool";
    const toolCallId = (message as any).tool_call_id || "";
    role = `Tool Result [${toolName}]`;
    if (toolCallId) {
      role += ` (call_id: ${toolCallId.slice(0, 8)})`;
    }
  }

  // Handle tool calls from .tool_calls property (for AI messages)
  const toolCallsText: string[] = [];
  if (
    message.type === "ai" &&
    message.tool_calls &&
    Array.isArray(message.tool_calls) &&
    message.tool_calls.length > 0
  ) {
    message.tool_calls.forEach((call: any) => {
      const toolName = call.name || "unknown_tool";
      const toolArgs = call.args ? JSON.stringify(call.args, null, 2) : "{}";
      toolCallsText.push(`[Tool Call: ${toolName}]\nArguments: ${toolArgs}`);
    });
  }

  // Combine content and tool calls
  const parts: string[] = [];
  if (contentText) {
    parts.push(contentText);
  }
  if (toolCallsText.length > 0) {
    parts.push(...toolCallsText);
  }

  if (parts.length === 0) {
    return `${role}${timestamp}: [Empty message]`;
  }

  if (parts.length === 1) {
    return `${role}${timestamp}: ${parts[0]}`;
  }

  return `${role}${timestamp}:\n${parts.join("\n\n")}`;
}

export function formatConversationForLLM(messages: Message[]): string {
  const formattedMessages = messages.map(formatMessageForLLM);
  return formattedMessages.join("\n\n---\n\n");
}
