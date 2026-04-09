"use client";

import React, {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Assistant, Message } from "@langchain/langgraph-sdk";
import {
  AlertCircle,
  ArrowUp,
  CheckCircle,
  Circle,
  Clock,
  FileIcon,
  Loader2,
  Plus,
  Square,
  X,
} from "lucide-react";
import { useStickToBottom } from "use-stick-to-bottom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "@/app/components/ChatMessage";
import { PendingAssistantIndicator } from "@/app/components/PendingAssistantIndicator";
import { ParameterRequestPopup } from "@/app/components/ParameterRequestPopup";
import type {
  ActionRequest,
  ParameterRequestPayload,
  ReviewConfig,
  TodoItem,
  ToolCall,
} from "@/app/types/types";
import {
  extractStringFromMessageContent,
  sanitizeAssistantDisplayText,
} from "@/app/utils/utils";
import { useChatContext } from "@/providers/ChatProvider";
import {
  DEFAULT_UI_PREFERENCES,
  type LabDefaultsConfig,
  type UiPreferencesConfig,
} from "@/lib/config";
import { cn } from "@/lib/utils";
import {
  createChatFileData,
  getChatFileContent,
  LAB_DEFAULTS_THREAD_FILE_PATH,
  normalizeThreadFilePath,
  type ChatFileRecord,
} from "@/app/lib/chatFiles";
import {
  buildCleanExperimentPlanFilePath,
  extractCleanExperimentPlan,
} from "@/app/lib/experimentPlan";

interface ChatInterfaceProps {
  assistant: Assistant | null;
  labDefaults?: LabDefaultsConfig;
  uiPreferences?: UiPreferencesConfig;
  layoutMode?: "standard" | "notebook";
}

const QUICK_START_PROMPTS = [
  "Plan a structured SOC-OCV test for an LFP pouch cell.",
  "Find representative LFP cells from different manufacturers.",
  "Inspect a raw battery export and show the normalized preview.",
  "Draft an HPPC planning workflow for an LFP cell.",
] as const;

const TEXT_ATTACHMENT_EXTENSIONS = new Set([
  "txt",
  "md",
  "markdown",
  "csv",
  "tsv",
  "json",
  "yaml",
  "yml",
  "xml",
  "log",
  "py",
  "ipynb",
  "js",
  "jsx",
  "ts",
  "tsx",
  "html",
  "htm",
]);
const TEXT_ATTACHMENT_CHAR_LIMIT = 200_000;
const TEXT_ATTACHMENT_READ_LIMIT_BYTES = 1_000_000;

type PendingAttachment = {
  id: string;
  name: string;
  mimeType: string;
  sizeBytes: number;
  storagePath: string;
  content: string;
  summaryLabel: string;
};

type AttachmentExtractionResult = {
  content: string;
  summaryLabel: string;
  extractedExtension: string;
};

type AttachmentQuickAction =
  | "parse-raw-cycler-export"
  | "draft-planning"
  | "send-to-admin-review";
const ATTACHMENT_QUICK_ACTION_ORDER: AttachmentQuickAction[] = [
  "parse-raw-cycler-export",
  "draft-planning",
  "send-to-admin-review",
];
type SubmitPhase = "idle" | "preparing" | "awaiting-stream" | "streaming";

const ATTACHMENT_NOTICE_HEADER =
  "Attached thread files for this request (these are thread file-state paths; use read_file on the exact path when needed):";
const ATTACHMENT_NOTICE_FOOTER =
  "Use the attached thread files as the source material for this request when relevant.";
const DATASHEET_DRAFT_ACTION_PROMPT =
  "Use the attached thread files as a user-supplied cell datasheet. Call extract_uploaded_cell_datasheet first, then use the uploaded cell-specific limits as the primary constraints for a draft planning answer. Prefer the uploaded cell limits over chemistry-family defaults whenever they exist, and keep any unresolved registry-specific gaps explicit.";
const DATASHEET_ADMIN_ACTION_PROMPT =
  "Use the attached thread files as a user-supplied cell datasheet. Call extract_uploaded_cell_datasheet_to_provisional_asset with submit_for_review=true so the record enters the provisional admin review queue. Return the provisional id, the key extracted fields, and any missing formal fields.";
const RAW_CYCLER_PARSE_ACTION_PROMPT =
  "Use the attached thread files as battery test tabular data. Call parse_raw_cycler_export on each relevant attachment, even when it is a public-dataset CSV, a non-standard raw export, or a spreadsheet preview. If a `/uploads/...` attachment cannot be opened directly by parse_raw_cycler_export, call read_file on that exact path and retry parse_raw_cycler_export with the same file_path plus attachment_text from read_file. When exact vendor normalization is possible, report the normalized schema preview; otherwise, use the tool's generic inspection fallback to classify the dataset, list recognized fields, and make preview limitations explicit.";
const EMPTY_MESSAGE_UI: any[] = [];

function getFileExtension(name: string): string {
  const segments = name.split(".");
  return segments.length > 1 ? segments[segments.length - 1].toLowerCase() : "";
}

function sanitizeAttachmentName(name: string): string {
  return name.replace(/[^A-Za-z0-9._-]+/g, "_");
}

function toWellFormedText(value: string): string {
  const maybeWellFormed = value as string & { toWellFormed?: () => string };
  if (typeof maybeWellFormed.toWellFormed === "function") {
    return maybeWellFormed.toWellFormed();
  }

  let normalized = "";
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
      const nextUnit = value.charCodeAt(index + 1);
      if (index + 1 < value.length && nextUnit >= 0xdc00 && nextUnit <= 0xdfff) {
        normalized += value[index] + value[index + 1];
        index += 1;
        continue;
      }
      normalized += "\uFFFD";
      continue;
    }
    if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
      normalized += "\uFFFD";
      continue;
    }
    normalized += value[index];
  }
  return normalized;
}

function buildThreadAttachmentPath(baseName: string): string {
  return normalizeThreadFilePath(baseName);
}

function buildAttachmentId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `attachment-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isTextAttachment(file: File): boolean {
  if (file.type.startsWith("text/")) return true;
  if (file.type === "application/json") return true;
  return TEXT_ATTACHMENT_EXTENSIONS.has(getFileExtension(file.name));
}

async function buildPendingAttachment(file: File): Promise<PendingAttachment> {
  const attachmentId = buildAttachmentId();
  const safeFileName = sanitizeAttachmentName(file.name);
  const storageBasePath = buildThreadAttachmentPath(
    `uploads/${attachmentId}-${safeFileName}`
  );

  if (isTextAttachment(file)) {
    const partialText = await file.slice(0, TEXT_ATTACHMENT_READ_LIMIT_BYTES).text();
    const rawText = toWellFormedText(partialText);
    const trimmedText = rawText.slice(0, TEXT_ATTACHMENT_CHAR_LIMIT);
    const wasTrimmed =
      file.size > TEXT_ATTACHMENT_READ_LIMIT_BYTES ||
      rawText.length > TEXT_ATTACHMENT_CHAR_LIMIT;
    const trimmingNote =
      file.size > TEXT_ATTACHMENT_READ_LIMIT_BYTES
        ? `\n\n[Truncated after ${TEXT_ATTACHMENT_READ_LIMIT_BYTES.toLocaleString()} bytes for chat upload preview.]`
        : rawText.length > TEXT_ATTACHMENT_CHAR_LIMIT
          ? `\n\n[Truncated after ${TEXT_ATTACHMENT_CHAR_LIMIT.toLocaleString()} characters for chat upload preview.]`
          : "";
    return {
      id: attachmentId,
      name: file.name,
      mimeType: file.type || "text/plain",
      sizeBytes: file.size,
      storagePath: storageBasePath,
      content: wasTrimmed ? `${trimmedText}${trimmingNote}` : trimmedText,
      summaryLabel: wasTrimmed ? "text preview (trimmed)" : "text preview",
    };
  }

  const extension = getFileExtension(file.name);
  if (extension === "pdf" || extension === "xlsx" || extension === "xls") {
    try {
      const extractedAttachment = await extractStructuredAttachmentPreview(file);
      return {
        id: attachmentId,
        name: file.name,
        mimeType: file.type || "application/octet-stream",
        sizeBytes: file.size,
        storagePath: `${storageBasePath}.${extractedAttachment.extractedExtension}`,
        content: toWellFormedText(extractedAttachment.content),
        summaryLabel: extractedAttachment.summaryLabel,
      };
    } catch (error) {
      console.error("Structured attachment extraction failed:", error);
      return buildMetadataPlaceholderAttachment({
        attachmentId,
        file,
        storageBasePath,
        note:
          error instanceof Error && error.message.trim().length > 0
            ? `Automatic text extraction failed. ${error.message}`
            : undefined,
      });
    }
  }

  return buildMetadataPlaceholderAttachment({
    attachmentId,
    file,
    storageBasePath,
  });
}

async function extractStructuredAttachmentPreview(
  file: File
): Promise<AttachmentExtractionResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/attachments/extract", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let errorMessage = `Automatic extraction failed for ${file.name}.`;
    try {
      const payload = (await response.json()) as { error?: string };
      if (typeof payload.error === "string" && payload.error.trim().length > 0) {
        errorMessage = payload.error;
      }
    } catch {
      // Keep the fallback error message when the response body is unavailable.
    }
    throw new Error(errorMessage);
  }

  return (await response.json()) as AttachmentExtractionResult;
}

function buildMetadataPlaceholderAttachment({
  attachmentId,
  file,
  storageBasePath,
  note,
}: {
  attachmentId: string;
  file: File;
  storageBasePath: string;
  note?: string;
}): PendingAttachment {
  const extension = getFileExtension(file.name);
  const placeholderKind =
    extension === "pdf"
      ? "pdf_attachment_placeholder"
      : extension === "xlsx" || extension === "xls"
        ? "spreadsheet_attachment_placeholder"
        : "binary_attachment_placeholder";

  return {
    id: attachmentId,
    name: file.name,
    mimeType: file.type || "application/octet-stream",
    sizeBytes: file.size,
    storagePath: `${storageBasePath}.upload.json`,
    content: JSON.stringify(
      {
        kind: placeholderKind,
        original_filename: file.name,
        mime_type: file.type || "application/octet-stream",
        size_bytes: file.size,
        note:
          note ??
          "Binary attachment captured in the chat UI. Frontend-side text extraction is not enabled for this format yet, so this entry stores metadata only.",
      },
      null,
      2
    ),
    summaryLabel: "metadata placeholder",
  };
}

function buildMessageWithAttachmentNotice(
  messageText: string,
  attachments: PendingAttachment[]
): string {
  if (attachments.length === 0) return messageText;

  const attachmentLines = attachments.map(
    (attachment) =>
      `- ${attachment.storagePath} (${attachment.summaryLabel}, ${formatBytes(attachment.sizeBytes)})`
  );

  return [
    messageText,
    "",
    ATTACHMENT_NOTICE_HEADER,
    ...attachmentLines,
    ATTACHMENT_NOTICE_FOOTER,
  ].join("\n");
}

function stripAttachmentNotice(content: string): string {
  const markerIndex = content.indexOf(`\n\n${ATTACHMENT_NOTICE_HEADER}`);
  if (markerIndex >= 0) {
    return content.slice(0, markerIndex).trimEnd();
  }
  if (content.startsWith(ATTACHMENT_NOTICE_HEADER)) {
    return "";
  }
  return content;
}

function getSubmissionDisplayText(
  currentInput: string,
  selectedActions: AttachmentQuickAction[],
  hasPendingAttachments: boolean
): string {
  const trimmedInput = currentInput.trim();
  if (trimmedInput) {
    return trimmedInput;
  }
  if (selectedActions.includes("parse-raw-cycler-export")) {
    return "Inspect uploaded battery data.";
  }
  if (selectedActions.includes("draft-planning")) {
    return selectedActions.includes("send-to-admin-review")
      ? "Use uploaded datasheet for draft planning and send it to Admin Review."
      : "Use uploaded datasheet for draft planning.";
  }
  if (selectedActions.includes("send-to-admin-review")) {
    return "Send uploaded datasheet to Admin Review.";
  }
  if (hasPendingAttachments) {
    return "Please inspect the attached files and use them for this request.";
  }
  return "";
}

function getVisibleHumanMessageContent(message: Message): string {
  const metadata = (message as Message & { metadata?: { display_content?: string } })
    .metadata;
  if (typeof metadata?.display_content === "string" && metadata.display_content.trim()) {
    return metadata.display_content;
  }

  const rawContent = extractStringFromMessageContent(message);
  const contentWithoutAttachmentNotice = stripAttachmentNotice(rawContent);

  if (contentWithoutAttachmentNotice === DATASHEET_DRAFT_ACTION_PROMPT) {
    return "Use uploaded datasheet for draft planning.";
  }
  if (contentWithoutAttachmentNotice === DATASHEET_ADMIN_ACTION_PROMPT) {
    return "Send uploaded datasheet to Admin Review.";
  }
  if (contentWithoutAttachmentNotice === RAW_CYCLER_PARSE_ACTION_PROMPT) {
    return "Inspect uploaded battery data.";
  }
  if (
    contentWithoutAttachmentNotice.endsWith(`\n\n${DATASHEET_DRAFT_ACTION_PROMPT}`)
  ) {
    const prefix = contentWithoutAttachmentNotice
      .slice(0, -(`\n\n${DATASHEET_DRAFT_ACTION_PROMPT}`.length))
      .trimEnd();
    return prefix || "Use uploaded datasheet for draft planning.";
  }
  if (
    contentWithoutAttachmentNotice.endsWith(`\n\n${DATASHEET_ADMIN_ACTION_PROMPT}`)
  ) {
    const prefix = contentWithoutAttachmentNotice
      .slice(0, -(`\n\n${DATASHEET_ADMIN_ACTION_PROMPT}`.length))
      .trimEnd();
    return prefix || "Send uploaded datasheet to Admin Review.";
  }
  if (
    contentWithoutAttachmentNotice.endsWith(`\n\n${RAW_CYCLER_PARSE_ACTION_PROMPT}`)
  ) {
    const prefix = contentWithoutAttachmentNotice
      .slice(0, -(`\n\n${RAW_CYCLER_PARSE_ACTION_PROMPT}`.length))
      .trimEnd();
    return prefix || "Inspect uploaded battery data.";
  }

  return contentWithoutAttachmentNotice || rawContent;
}

function isToolOnlyAssistantEntry(entry: {
  message: Message;
  toolCalls: ToolCall[];
}): boolean {
  if (entry.message.type !== "ai") {
    return false;
  }

  const visibleContent = sanitizeAssistantDisplayText(
    extractStringFromMessageContent(entry.message)
  ).trim();
  const visibleToolCalls = entry.toolCalls.filter(
    (toolCall) => toolCall.name !== "task"
  );

  return !visibleContent && visibleToolCalls.length > 0;
}

function getGeneratedPlanMetadata(fileValue: unknown): {
  generatedFromMessageId?: string;
  userEdited?: boolean;
} {
  if (!fileValue || typeof fileValue !== "object") {
    return {};
  }

  const metadata = fileValue as Record<string, unknown>;
  return {
    generatedFromMessageId:
      typeof metadata.generated_from_message_id === "string"
        ? metadata.generated_from_message_id
        : undefined,
    userEdited: metadata.user_edited === true,
  };
}

function isLikelyCellDatasheetAttachment(attachment: PendingAttachment): boolean {
  const attachmentName = attachment.name.toLowerCase();
  const preview = attachment.content.slice(0, 4000).toLowerCase();
  const combined = `${attachmentName}\n${attachment.summaryLabel.toLowerCase()}\n${preview}`;

  const strongSignals = [
    "datasheet",
    "specification",
    "specifications",
    "nominal voltage",
    "rated capacity",
    "charge voltage",
    "discharge cut",
    "discharge cutoff",
    "continuous discharge",
    "battery cell",
    "lithium ion",
    "li-po",
    "li ion",
  ];

  return strongSignals.some((signal) => combined.includes(signal));
}

function isLikelyCyclerExportAttachment(attachment: PendingAttachment): boolean {
  const extension = getFileExtension(attachment.name);
  if (!["csv", "tsv", "txt", "xls", "xlsx"].includes(extension)) {
    return false;
  }

  const preview = attachment.content.slice(0, 4000).toLowerCase();
  const signals = [
    "cycle_index",
    "step_index",
    "test_time",
    "voltage(v)",
    "current(ma)",
    "current(a)",
    "cycle id",
    "step id",
    "date_time",
    "test_time(s)",
    "step_time(s)",
    "time(h:min:s.ms)",
    "test_time,datetime,step_time",
    "current,voltage,charge_capacity",
    "ecell/v",
    "<i>/ma",
    "q charge/ma.h",
    "q discharge/ma.h",
    "cycle number",
    "power(w)",
    "internal_resistance(ohm)",
    "acr(ohm)",
    "aux_temperature_1(c)",
    "cyclereorder",
    "amphr",
    "sheet1",
    "## sheet:",
    "spreadsheet preview",
  ];

  const hitCount = signals.filter((signal) => preview.includes(signal)).length;
  return hitCount >= 2;
}

function buildLabDefaultsStatePatch(
  labDefaults: LabDefaultsConfig | undefined
): { labDefaults: LabDefaultsConfig } | undefined {
  if (
    !labDefaults?.defaultInstrumentId &&
    !labDefaults?.defaultInstrumentLabel &&
    !labDefaults?.defaultThermalChamberId &&
    !labDefaults?.defaultThermalChamberLabel &&
    !labDefaults?.defaultEisInstrumentId &&
    !labDefaults?.defaultEisInstrumentLabel &&
    !labDefaults?.defaultEisSetupNotes
  ) {
    return undefined;
  }

  return {
    labDefaults: {
      ...(labDefaults.defaultInstrumentId
        ? { defaultInstrumentId: labDefaults.defaultInstrumentId }
        : {}),
      ...(labDefaults.defaultInstrumentLabel
        ? { defaultInstrumentLabel: labDefaults.defaultInstrumentLabel }
        : {}),
      ...(labDefaults.defaultThermalChamberId
        ? { defaultThermalChamberId: labDefaults.defaultThermalChamberId }
        : {}),
      ...(labDefaults.defaultThermalChamberLabel
        ? { defaultThermalChamberLabel: labDefaults.defaultThermalChamberLabel }
        : {}),
      ...(labDefaults.defaultEisInstrumentId
        ? { defaultEisInstrumentId: labDefaults.defaultEisInstrumentId }
        : {}),
      ...(labDefaults.defaultEisInstrumentLabel
        ? { defaultEisInstrumentLabel: labDefaults.defaultEisInstrumentLabel }
        : {}),
      ...(labDefaults.defaultEisSetupNotes
        ? { defaultEisSetupNotes: labDefaults.defaultEisSetupNotes }
        : {}),
    },
  };
}

function buildAttachmentQuickActionPrompt(
  action: AttachmentQuickAction,
  currentInput: string
): string {
  const trimmedInput = currentInput.trim();

  const basePrompt =
    action === "parse-raw-cycler-export"
      ? RAW_CYCLER_PARSE_ACTION_PROMPT
      : action === "draft-planning"
        ? DATASHEET_DRAFT_ACTION_PROMPT
        : DATASHEET_ADMIN_ACTION_PROMPT;

  if (!trimmedInput) {
    return basePrompt;
  }

  return `${trimmedInput}\n\n${basePrompt}`;
}

function buildLabDefaultsThreadFile(
  labDefaults: LabDefaultsConfig | undefined
): ChatFileRecord | undefined {
  const statePatch = buildLabDefaultsStatePatch(labDefaults);
  if (!statePatch?.labDefaults) {
    return undefined;
  }

  return {
    [LAB_DEFAULTS_THREAD_FILE_PATH]: createChatFileData(
      JSON.stringify({ labDefaults: statePatch.labDefaults }, null, 2),
      undefined,
      {
        hidden: true,
        system_file_kind: "lab_defaults_context",
      }
    ),
  };
}

function parseToolArgs(value: unknown): Record<string, unknown> {
  const stripEmptyValues = (input: unknown): unknown => {
    if (input === null || input === undefined) {
      return undefined;
    }

    if (typeof input === "string") {
      const trimmed = input.trim();
      if (
        trimmed.length === 0 ||
        trimmed.toLowerCase() === "null" ||
        trimmed.toLowerCase() === "undefined"
      ) {
        return undefined;
      }
      return input;
    }

    if (Array.isArray(input)) {
      const normalizedItems = input
        .map((item) => stripEmptyValues(item))
        .filter((item) => item !== undefined);
      return normalizedItems.length > 0 ? normalizedItems : undefined;
    }

    if (input && typeof input === "object") {
      const normalizedEntries = Object.entries(input as Record<string, unknown>)
        .map(([key, entry]) => [key, stripEmptyValues(entry)] as const)
        .filter(([, entry]) => entry !== undefined);
      return normalizedEntries.length > 0
        ? Object.fromEntries(normalizedEntries)
        : undefined;
    }

    return input;
  };

  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return (stripEmptyValues(parsed) as Record<string, unknown>) ?? {};
      }
    } catch {
      return { raw: value };
    }
    return {};
  }

  if (value && typeof value === "object" && !Array.isArray(value)) {
    return (stripEmptyValues(value) as Record<string, unknown>) ?? {};
  }

  return {};
}

function parseToolResultPayload(
  value: unknown
): Record<string, unknown> | null {
  if (!value) {
    return null;
  }

  if (typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }

  if (typeof value !== "string" || value.trim().length === 0) {
    return null;
  }

  const tryParse = (candidate: string): Record<string, unknown> | null => {
    if (!candidate.trim()) {
      return null;
    }
    try {
      const parsed = JSON.parse(candidate) as unknown;
      return parsed && typeof parsed === "object" && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : null;
    } catch {
      return null;
    }
  };

  const directParse = tryParse(value);
  if (directParse) {
    return directParse;
  }

  const fencedJsonMatch = value.match(/```(?:json)?\s*([\s\S]+?)```/i);
  if (fencedJsonMatch?.[1]) {
    const fencedParse = tryParse(fencedJsonMatch[1]);
    if (fencedParse) {
      return fencedParse;
    }
  }

  const firstBraceIndex = value.indexOf("{");
  const lastBraceIndex = value.lastIndexOf("}");
  if (firstBraceIndex >= 0 && lastBraceIndex > firstBraceIndex) {
    const extractedParse = tryParse(value.slice(firstBraceIndex, lastBraceIndex + 1));
    if (extractedParse) {
      return extractedParse;
    }
  }

  return null;
}

function extractLargeToolResultPath(value: unknown): string | null {
  if (typeof value !== "string" || value.trim().length === 0) {
    return null;
  }

  const matchedPath = value.match(/\/large_tool_results\/[A-Za-z0-9._-]+/);
  return matchedPath?.[0] ?? null;
}

function resolveToolPayload(
  toolCall: ToolCall,
  files: ChatFileRecord
): Record<string, unknown> | null {
  const payloadCandidates = [toolCall.artifact, toolCall.result];
  for (const candidate of payloadCandidates) {
    let payload = parseToolResultPayload(candidate);
    if (!payload) {
      const largeResultPath = extractLargeToolResultPath(candidate);
      const largeResultContent = largeResultPath
        ? getChatFileContent(files[largeResultPath])
        : "";
      if (largeResultContent) {
        payload = parseToolResultPayload(largeResultContent);
      }
    }
    if (payload) {
      return payload;
    }
  }
  return null;
}

function slugifyFileSegment(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function humanizeGeneratedPlanLabel(payload: Record<string, unknown>): string {
  const methodId = String(payload.method_id || "").trim().toLowerCase();
  const labelMap: Record<string, string> = {
    pulse_hppc: "HPPC",
    capacity_test: "Capacity Test",
    cycle_life: "Cycle Life",
    calendar_ageing_test: "Calendar Ageing",
    ageing_drive_cycle: "Ageing Drive Cycle",
    constant_voltage_ageing: "CV Ageing",
    soc_ocv: "SOC-OCV",
  };
  if (labelMap[methodId]) {
    return labelMap[methodId];
  }

  const rawLabel =
    String(payload.method_label || payload.objective || payload.protocol_name || "").trim();
  if (!rawLabel) {
    return "Experiment Plan";
  }
  const firstSegment = rawLabel.split(" - ")[0]?.trim();
  return firstSegment || rawLabel;
}

type DerivedGeneratedFile = {
  path: string;
  content: string;
  generatedFileKind: string;
  displayName: string;
};

function extractStructuredGeneratedFiles(
  payload: Record<string, unknown>
): DerivedGeneratedFile[] {
  const rawGeneratedFiles = payload.generated_files;
  if (!Array.isArray(rawGeneratedFiles)) {
    return [];
  }

  return rawGeneratedFiles.flatMap((entry) => {
    if (!entry || typeof entry !== "object") {
      return [];
    }

    const candidate = entry as Record<string, unknown>;
    const rawPath = String(candidate.path || "").trim();
    const rawContent = typeof candidate.content === "string" ? candidate.content : "";
    if (!rawPath || !rawContent) {
      return [];
    }

    const normalizedPath = normalizeThreadFilePath(rawPath);
    const displayName =
      typeof candidate.display_name === "string" &&
      candidate.display_name.trim().length > 0
        ? candidate.display_name.trim()
        : normalizedPath.split("/").filter(Boolean).at(-1) || normalizedPath;

    return [
      {
        path: normalizedPath,
        content: rawContent,
        generatedFileKind:
          typeof candidate.generated_file_kind === "string" &&
          candidate.generated_file_kind.trim().length > 0
            ? candidate.generated_file_kind.trim()
            : "generated_artifact",
        displayName,
      },
    ];
  });
}

function extractGeneratedFilesFromToolCalls(
  toolCalls: ToolCall[],
  files: ChatFileRecord,
  messageId: string,
  assistantMessageContent?: string
): DerivedGeneratedFile[] {
  const generatedFiles: DerivedGeneratedFile[] = [];
  const assistantCleanPlan = assistantMessageContent
    ? extractCleanExperimentPlan(
        sanitizeAssistantDisplayText(String(assistantMessageContent))
      )
    : null;
  let usedAssistantCleanPlan = false;

  toolCalls.forEach((toolCall) => {
    if (toolCall.status !== "completed") {
      return;
    }
    const payload = resolveToolPayload(toolCall, files);
    if (!payload) {
      return;
    }

    generatedFiles.push(...extractStructuredGeneratedFiles(payload));

    if (typeof payload.ui_markdown !== "string") {
      return;
    }

    const uiMarkdown = sanitizeAssistantDisplayText(String(payload.ui_markdown));

    if (toolCall.name === "extract_uploaded_cell_datasheet") {
      const candidate =
        payload.candidate && typeof payload.candidate === "object"
          ? (payload.candidate as Record<string, unknown>)
          : {};
      const displayName =
        String(
          candidate.display_name || candidate.model || candidate.schema_name || "Cell Datasheet"
        ).trim() || "Cell Datasheet";
      const slugBase = slugifyFileSegment(
        String(candidate.model || candidate.schema_name || candidate.display_name || "cell-datasheet")
      );
      generatedFiles.push({
        path: `/plans/cell-datasheet-${slugBase || messageId.slice(0, 8).toLowerCase()}.md`,
        content: uiMarkdown,
        generatedFileKind: "cell_background_summary",
        displayName: `Cell Datasheet${displayName ? ` - ${displayName}` : ""}`,
      });
      return;
    }

    if (
      toolCall.name === "plan_standard_test" ||
      toolCall.name === "design_battery_protocol"
    ) {
      if (assistantCleanPlan && usedAssistantCleanPlan) {
        return;
      }
      const cleanPlan =
        assistantCleanPlan && !usedAssistantCleanPlan
          ? assistantCleanPlan
          : extractCleanExperimentPlan(uiMarkdown);
      if (!cleanPlan) {
        return;
      }
      if (assistantCleanPlan && !usedAssistantCleanPlan) {
        usedAssistantCleanPlan = true;
      }
      const shortLabel = humanizeGeneratedPlanLabel(payload);
      const cellSlugSource =
        payload.selected_cell_reference &&
        typeof payload.selected_cell_reference === "object"
          ? String(
              (payload.selected_cell_reference as Record<string, unknown>).display_name ||
                (payload.selected_cell_reference as Record<string, unknown>).cell_id ||
                ""
            )
          : "";
      const slugHint = [
        slugifyFileSegment(shortLabel),
        slugifyFileSegment(cellSlugSource),
      ]
        .filter(Boolean)
        .join("-");
      generatedFiles.push({
        path: buildCleanExperimentPlanFilePath(messageId, cleanPlan, { slugHint }),
        content: cleanPlan,
        generatedFileKind: "clean_experiment_plan",
        displayName: shortLabel || "Experiment Plan",
      });
    }
  });

  return generatedFiles;
}

function getToolResultStatus(result: string): ToolCall["status"] {
  const trimmed = result.trim();
  if (!trimmed.startsWith("{")) {
    return "completed";
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (
      parsed &&
      typeof parsed === "object" &&
      !Array.isArray(parsed) &&
      (parsed as Record<string, unknown>).status === "error"
    ) {
      return "error";
    }
  } catch {
    return "completed";
  }

  return "completed";
}

function isParameterRequestPayload(
  value: unknown
): value is ParameterRequestPayload {
  if (!value || typeof value !== "object") {
    return false;
  }

  const payload = value as Record<string, unknown>;
  return (
    typeof payload.request_id === "string" &&
    typeof payload.release_status === "string" &&
    Array.isArray(payload.questions)
  );
}

function stableNormalize(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => stableNormalize(item));
  }

  if (value && typeof value === "object") {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        acc[key] = stableNormalize((value as Record<string, unknown>)[key]);
        return acc;
      }, {});
  }

  return value;
}

function getToolCallDedupKey(
  name: string,
  args: Record<string, unknown>,
  id?: string
): string {
  return id
    ? `id:${id}`
    : `fallback:${name}:${JSON.stringify(stableNormalize(args))}`;
}

const getStatusIcon = (status: TodoItem["status"], className?: string) => {
  switch (status) {
    case "completed":
      return (
        <CheckCircle
          size={15}
          className={cn("text-emerald-600", className)}
        />
      );
    case "in_progress":
      return (
        <Clock
          size={15}
          className={cn("text-amber-600", className)}
        />
      );
    default:
      return (
        <Circle
          size={15}
          className={cn("text-muted-foreground", className)}
        />
      );
  }
};

export const ChatInterface = React.memo<ChatInterfaceProps>(
  ({ assistant, labDefaults, uiPreferences, layoutMode = "standard" }) => {
  const [metaOpen, setMetaOpen] = useState<"tasks" | null>(null);
  const [input, setInput] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [adminQueuedAttachmentIds, setAdminQueuedAttachmentIds] = useState<string[]>([]);
  const [selectedAttachmentActions, setSelectedAttachmentActions] = useState<
    AttachmentQuickAction[]
  >([]);
  const [submitPhase, setSubmitPhase] = useState<SubmitPhase>("idle");
  const [isAttaching, setIsAttaching] = useState(false);
  const [dismissedParameterRequestIds, setDismissedParameterRequestIds] =
    useState<Set<string>>(() => new Set());
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const submitLockRef = useRef(false);
  const { scrollRef, contentRef } = useStickToBottom();

  const {
    stream,
    messages,
    todos,
    files,
    ui,
    setFiles,
    isLoading,
    isThreadLoading,
    interrupt,
    streamErrorTick,
    sendMessage,
    stopStream,
    resumeInterrupt,
  } = useChatContext();

  const isSubmitPending = submitPhase !== "idle";
  const submitDisabled =
    isLoading || isSubmitPending || !assistant || isAttaching || interrupt !== undefined;
  const attachmentDisabled = isAttaching;
  const labDefaultsStatePatch = useMemo(
    () => buildLabDefaultsStatePatch(labDefaults),
    [labDefaults]
  );
  const labDefaultsThreadFile = useMemo(
    () => buildLabDefaultsThreadFile(labDefaults),
    [labDefaults]
  );
  const effectiveUiPreferences = useMemo(
    () => ({
      ...DEFAULT_UI_PREFERENCES,
      ...uiPreferences,
    }),
    [uiPreferences]
  );
  const isNotebookLayout = layoutMode === "notebook";
  const datasheetReadyAttachments = useMemo(
    () =>
      pendingAttachments.filter((attachment) =>
        isLikelyCellDatasheetAttachment(attachment)
      ),
    [pendingAttachments]
  );
  const cyclerReadyAttachments = useMemo(
    () =>
      pendingAttachments.filter((attachment) =>
        isLikelyCyclerExportAttachment(attachment)
      ),
    [pendingAttachments]
  );
  const datasheetAttachmentsPendingAdmin = useMemo(
    () =>
      datasheetReadyAttachments.filter(
        (attachment) => !adminQueuedAttachmentIds.includes(attachment.id)
      ),
    [adminQueuedAttachmentIds, datasheetReadyAttachments]
  );

  useEffect(() => {
    setSelectedAttachmentActions((current) => {
      const nextActions = current.filter((action) => {
        if (
          action === "parse-raw-cycler-export" &&
          cyclerReadyAttachments.length === 0
        ) {
          return false;
        }
        if (datasheetReadyAttachments.length === 0) {
          return action === "parse-raw-cycler-export";
        }
        if (
          action === "send-to-admin-review" &&
          datasheetAttachmentsPendingAdmin.length === 0
        ) {
          return false;
        }
        return true;
      });

      if (
        nextActions.length === current.length &&
        nextActions.every((action, index) => action === current[index])
      ) {
        return current;
      }
      return nextActions;
    });
  }, [
    cyclerReadyAttachments.length,
    datasheetAttachmentsPendingAdmin.length,
    datasheetReadyAttachments.length,
  ]);

  useEffect(() => {
    if (submitPhase === "awaiting-stream" && isLoading) {
      setSubmitPhase("streaming");
    }
  }, [isLoading, submitPhase]);

  useEffect(() => {
    if (submitPhase === "streaming" && !isLoading) {
      setSubmitPhase("idle");
    }
  }, [isLoading, submitPhase]);

  useEffect(() => {
    setSubmitPhase((current) => (current !== "idle" ? "idle" : current));
  }, [streamErrorTick]);

  useEffect(() => {
    if (submitPhase === "idle" && !isLoading) {
      submitLockRef.current = false;
    }
  }, [isLoading, submitPhase]);

  useEffect(() => {
    if (
      !labDefaultsThreadFile ||
      !(LAB_DEFAULTS_THREAD_FILE_PATH in labDefaultsThreadFile)
    ) {
      return;
    }

    const nextLabDefaultsFile = labDefaultsThreadFile[LAB_DEFAULTS_THREAD_FILE_PATH];
    const existingLabDefaultsFile = files[LAB_DEFAULTS_THREAD_FILE_PATH];

    if (
      getChatFileContent(existingLabDefaultsFile) ===
      getChatFileContent(nextLabDefaultsFile)
    ) {
      return;
    }

    void setFiles((currentFiles) => ({
      ...currentFiles,
      ...labDefaultsThreadFile,
    }));
  }, [files, labDefaultsThreadFile, setFiles]);

  const removePendingAttachment = useCallback((attachmentId: string) => {
    setPendingAttachments((current) =>
      current.filter((attachment) => attachment.id !== attachmentId)
    );
    setAdminQueuedAttachmentIds((current) =>
      current.filter((id) => id !== attachmentId)
    );
  }, []);

  const handleAttachmentSelection = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(event.target.files ?? []);
      event.target.value = "";
      if (selectedFiles.length === 0) return;

      setIsAttaching(true);
      try {
        const createdAttachments: PendingAttachment[] = [];
        for (const file of selectedFiles) {
          try {
            createdAttachments.push(await buildPendingAttachment(file));
          } catch (error) {
            console.error("Failed to process attachment:", error);
            toast.error(`Failed to read ${file.name}.`);
          }
        }

        if (createdAttachments.length > 0) {
          setPendingAttachments((current) => [...current, ...createdAttachments]);
          toast.success(
            `${createdAttachments.length} attachment${createdAttachments.length > 1 ? "s" : ""} added`
          );
        }
      } finally {
        setIsAttaching(false);
      }
    },
    []
  );

  const sendWithPreparedAttachments = useCallback(
    async (messageText: string, displayMessageText?: string) => {
      let nextFiles: ChatFileRecord | undefined;
      if (pendingAttachments.length > 0 || labDefaultsThreadFile) {
        nextFiles = { ...files };
        if (labDefaultsThreadFile) {
          nextFiles = { ...nextFiles, ...labDefaultsThreadFile };
        }
          for (const attachment of pendingAttachments) {
            nextFiles[attachment.storagePath] = createChatFileData(
              attachment.content,
              undefined,
              {
                hidden: true,
                system_file_kind: "thread_attachment_preview",
                original_filename: attachment.name,
              }
            );
          }
        }

      sendMessage(buildMessageWithAttachmentNotice(messageText, pendingAttachments), {
        ...(nextFiles ? { files: nextFiles } : {}),
        ...(labDefaultsStatePatch ?? {}),
      }, displayMessageText);
      setInput("");
      setPendingAttachments([]);
      setAdminQueuedAttachmentIds([]);
      return true;
    },
    [files, labDefaultsStatePatch, labDefaultsThreadFile, pendingAttachments, sendMessage]
  );

  const queueSpecificDatasheetAttachmentsForAdminReview = useCallback(
    async (attachmentsToQueue: PendingAttachment[]) => {
      if (attachmentsToQueue.length === 0) {
        toast.message("This datasheet is already queued for admin review.");
        return false;
      }

      const provisionalIds: string[] = [];

      try {
        for (const targetAttachment of attachmentsToQueue) {
          const response = await fetch(
            "/api/admin/provisional-cells/register-from-attachment",
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                filePath: toWellFormedText(targetAttachment.storagePath),
                attachmentText: toWellFormedText(targetAttachment.content),
                submittedBy: "chat_user",
                submitForReview: true,
              }),
            }
          );
          const payload = (await response.json()) as {
            status?: string;
            message?: string;
            asset?: { provisional_id?: string };
          };

          if (!response.ok || payload.status === "error") {
            throw new Error(
              payload.message || "Failed to queue the datasheet for admin review."
            );
          }

          if (payload.asset?.provisional_id) {
            provisionalIds.push(payload.asset.provisional_id);
          }
          setAdminQueuedAttachmentIds((current) =>
            current.includes(targetAttachment.id)
              ? current
              : [...current, targetAttachment.id]
          );
        }

        toast.success(
          provisionalIds.length === 1
            ? `Queued for admin review: ${provisionalIds[0]}`
            : `Queued ${attachmentsToQueue.length} datasheet${attachmentsToQueue.length > 1 ? "s" : ""} for Admin Review.`
        );
        return true;
      } catch (error) {
        console.error("Failed to queue datasheet for admin review:", error);
        toast.error(
          error instanceof Error
            ? error.message
            : "Failed to queue the datasheet for admin review."
        );
        return false;
      }
    },
    []
  );

  const handleSubmit = useCallback(
    async (e?: FormEvent) => {
      if (e) {
        e.preventDefault();
      }
      if (submitLockRef.current || isLoading || submitDisabled) return;
      submitLockRef.current = true;
      setSubmitPhase("preparing");

      const shouldQueueForAdminReview = selectedAttachmentActions.includes(
        "send-to-admin-review"
      );
      const shouldUseDraftPlanning = selectedAttachmentActions.includes(
        "draft-planning"
      );
      const shouldParseRawCyclerExport = selectedAttachmentActions.includes(
        "parse-raw-cycler-export"
      );
      const attachmentsForAdminReview = shouldQueueForAdminReview
        ? [...datasheetAttachmentsPendingAdmin]
        : [];

      const trimmedInput = input.trim();
      const messageText = shouldParseRawCyclerExport
        ? buildAttachmentQuickActionPrompt("parse-raw-cycler-export", input)
        : shouldUseDraftPlanning
          ? buildAttachmentQuickActionPrompt("draft-planning", input)
          : trimmedInput ||
            (!shouldQueueForAdminReview && pendingAttachments.length > 0
              ? "Please inspect the attached files and use them for this request."
              : "");
      const displayMessageText = getSubmissionDisplayText(
        input,
        selectedAttachmentActions,
        pendingAttachments.length > 0
      );

      if (!messageText) {
        if (shouldQueueForAdminReview && !shouldUseDraftPlanning) {
          const queued = await queueSpecificDatasheetAttachmentsForAdminReview(
            attachmentsForAdminReview
          );
          if (queued) {
            setSelectedAttachmentActions([]);
          }
          submitLockRef.current = false;
          setSubmitPhase("idle");
          return;
        }
        if (shouldQueueForAdminReview) {
          setSelectedAttachmentActions([]);
        }
        submitLockRef.current = false;
        setSubmitPhase("idle");
        return;
      }

      const sent = await sendWithPreparedAttachments(
        messageText,
        displayMessageText || undefined
      );
      if (!sent) {
        submitLockRef.current = false;
        setSubmitPhase("idle");
        return;
      }

      setSubmitPhase("awaiting-stream");
      if (
        shouldParseRawCyclerExport ||
        shouldUseDraftPlanning ||
        shouldQueueForAdminReview
      ) {
        setSelectedAttachmentActions([]);
      }

      if (shouldQueueForAdminReview) {
        void queueSpecificDatasheetAttachmentsForAdminReview(
          attachmentsForAdminReview
        );
      }

      if (shouldUseDraftPlanning) {
        toast.success("Draft planning request sent with the uploaded datasheet.");
      } else if (shouldParseRawCyclerExport) {
        toast.success("Battery-data inspection request sent with the uploaded file.");
      }
    },
    [
      datasheetAttachmentsPendingAdmin,
      input,
      isLoading,
      pendingAttachments.length,
      queueSpecificDatasheetAttachmentsForAdminReview,
      selectedAttachmentActions,
      sendWithPreparedAttachments,
      submitDisabled,
    ]
  );

  const handleDatasheetQuickAction = useCallback(
    (action: AttachmentQuickAction) => {
      if (submitDisabled || isLoading) {
        return;
      }
      if (
        action === "parse-raw-cycler-export" &&
        cyclerReadyAttachments.length === 0
      ) {
        return;
      }
      if (
        action !== "parse-raw-cycler-export" &&
        datasheetReadyAttachments.length === 0
      ) {
        return;
      }
      if (
        action === "send-to-admin-review" &&
        datasheetAttachmentsPendingAdmin.length === 0
      ) {
        toast.message("This datasheet is already queued for admin review.");
        return;
      }

      setSelectedAttachmentActions((current) => {
        const hasAction = current.includes(action);
        const nextActions = hasAction
          ? current.filter((entry) => entry !== action)
          : action === "parse-raw-cycler-export"
            ? ["parse-raw-cycler-export"]
            : [
                ...current.filter((entry) => entry !== "parse-raw-cycler-export"),
                action,
              ];

        return ATTACHMENT_QUICK_ACTION_ORDER.filter((entry) =>
          nextActions.includes(entry)
        );
      });
    },
    [
      cyclerReadyAttachments.length,
      datasheetAttachmentsPendingAdmin.length,
      datasheetReadyAttachments.length,
      isLoading,
      submitDisabled,
    ]
  );

  const handleQuickStart = useCallback(
    (prompt: string) => {
      if (submitLockRef.current || submitDisabled || isLoading) return;
      submitLockRef.current = true;
      setSubmitPhase("awaiting-stream");
      const statePatch = {
        ...(labDefaultsStatePatch ?? {}),
        ...(labDefaultsThreadFile
          ? { files: { ...files, ...labDefaultsThreadFile } }
          : {}),
      };
      sendMessage(prompt, Object.keys(statePatch).length > 0 ? statePatch : undefined);
    },
    [files, isLoading, labDefaultsStatePatch, labDefaultsThreadFile, sendMessage, submitDisabled]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (submitDisabled) return;
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        void handleSubmit();
      }
    },
    [handleSubmit, submitDisabled]
  );

  const processedMessages = useMemo(() => {
    const messageMap = new Map<
      string,
      { message: Message; toolCalls: ToolCall[] }
    >();

    messages.forEach((message: Message) => {
      if (message.type === "ai") {
        const toolCallsInMessage: Array<{
          id?: string;
          function?: { name?: string; arguments?: unknown };
          name?: string;
          type?: string;
          args?: unknown;
          input?: unknown;
        }> = [];

        if (
          message.additional_kwargs?.tool_calls &&
          Array.isArray(message.additional_kwargs.tool_calls)
        ) {
          toolCallsInMessage.push(...message.additional_kwargs.tool_calls);
        } else if (message.tool_calls && Array.isArray(message.tool_calls)) {
          toolCallsInMessage.push(
            ...message.tool_calls.filter(
              (toolCall: { name?: string }) => toolCall.name !== ""
            )
          );
        } else if (Array.isArray(message.content)) {
          const toolUseBlocks = message.content.filter(
            (block: { type?: string }) => block.type === "tool_use"
          );
          toolCallsInMessage.push(...toolUseBlocks);
        }

        const seenToolCallKeys = new Set<string>();
        const toolCallsWithStatus = toolCallsInMessage.flatMap((toolCall) => {
          const name =
            toolCall.function?.name ||
            toolCall.name ||
            toolCall.type ||
            "unknown";
          const args = parseToolArgs(
            toolCall.function?.arguments ||
              toolCall.args ||
              toolCall.input ||
              {}
          );
          const dedupeKey = getToolCallDedupKey(name, args, toolCall.id);

          if (seenToolCallKeys.has(dedupeKey)) {
            return [];
          }
          seenToolCallKeys.add(dedupeKey);

          return [
            {
              id: toolCall.id || dedupeKey,
              name,
              args,
              status: interrupt ? "interrupted" : ("pending" as const),
            } as ToolCall,
          ];
        });

        messageMap.set(message.id!, {
          message,
          toolCalls: toolCallsWithStatus,
        });
      } else if (message.type === "tool") {
        const toolCallId = message.tool_call_id;
        if (!toolCallId) return;

        for (const [, data] of messageMap.entries()) {
          const toolCallIndex = data.toolCalls.findIndex(
            (toolCall: ToolCall) => toolCall.id === toolCallId
          );
          if (toolCallIndex === -1) continue;
          const toolResultText = extractStringFromMessageContent(message);

          data.toolCalls[toolCallIndex] = {
            ...data.toolCalls[toolCallIndex],
            status: getToolResultStatus(toolResultText),
            result: toolResultText,
            artifact: "artifact" in message ? message.artifact : undefined,
          };
          break;
        }
      } else if (message.type === "human") {
        const visibleContent = getVisibleHumanMessageContent(message);
        messageMap.set(message.id!, {
          message:
            visibleContent !== extractStringFromMessageContent(message)
              ? ({ ...message, content: visibleContent } as Message)
              : message,
          toolCalls: [],
        });
      }
    });

    const processedArray = Array.from(messageMap.values());
    return processedArray.map((data, index) => {
      const prevMessage = index > 0 ? processedArray[index - 1].message : null;
      return {
        ...data,
        showAvatar: data.message.type !== prevMessage?.type,
      };
    });
  }, [interrupt, messages]);

  const messageUiMap = useMemo(() => {
    const nextMap = new Map<string, any[]>();
    if (!Array.isArray(ui)) {
      return nextMap;
    }

    ui.forEach((entry: any) => {
      const messageId = entry?.metadata?.message_id;
      if (!messageId || typeof messageId !== "string") {
        return;
      }

      const existingEntries = nextMap.get(messageId);
      if (existingEntries) {
        existingEntries.push(entry);
        return;
      }

      nextMap.set(messageId, [entry]);
    });

    return nextMap;
  }, [ui]);

  const derivedGeneratedPlanFiles = useMemo(() => {
    if (processedMessages.length === 0) {
      return {};
    }

    const nextGeneratedFiles: ChatFileRecord = {};

    processedMessages.forEach(({ message, toolCalls }) => {
      if (message.type !== "ai") {
        return;
      }

      const toolGeneratedFiles = extractGeneratedFilesFromToolCalls(
        toolCalls,
        files,
        message.id ?? "plan",
        extractStringFromMessageContent(message)
      );

      toolGeneratedFiles.forEach((generatedFile) => {
        const existingFile = files[generatedFile.path];
        const existingContent = getChatFileContent(existingFile);
        const existingCreatedAt =
          existingFile &&
          typeof existingFile === "object" &&
          typeof existingFile.created_at === "string"
            ? existingFile.created_at
            : undefined;
        const generatedMetadata = getGeneratedPlanMetadata(existingFile);

        if (generatedMetadata.userEdited) {
          return;
        }

        if (
          generatedMetadata.generatedFromMessageId === message.id &&
          existingContent.trim() === generatedFile.content.trim()
        ) {
          return;
        }

        nextGeneratedFiles[generatedFile.path] = createChatFileData(
          generatedFile.content,
          existingCreatedAt,
          {
            generated_file_kind: generatedFile.generatedFileKind,
            generated_from_message_id: message.id,
            user_edited: false,
            display_name: generatedFile.displayName,
          }
        );
      });
    });

    return nextGeneratedFiles;
  }, [files, processedMessages]);

  const shouldRevealGeneratedPlanFiles =
    !isLoading && submitPhase === "idle";

  useEffect(() => {
    if (
      !shouldRevealGeneratedPlanFiles ||
      Object.keys(derivedGeneratedPlanFiles).length === 0
    ) {
      return;
    }

    void setFiles((currentFiles) => ({
      ...currentFiles,
      ...derivedGeneratedPlanFiles,
    }));
  }, [derivedGeneratedPlanFiles, setFiles, shouldRevealGeneratedPlanFiles]);

  const displayTodos = useMemo(() => {
    if (isLoading || interrupt !== undefined) {
      return todos;
    }

    return todos.map((todo) =>
      todo.status === "in_progress" ? { ...todo, status: "pending" as const } : todo
    );
  }, [interrupt, isLoading, todos]);

  const groupedTodos = {
    in_progress: displayTodos.filter((todo) => todo.status === "in_progress"),
    pending: displayTodos.filter((todo) => todo.status === "pending"),
    completed: displayTodos.filter((todo) => todo.status === "completed"),
  };

  const hasTasks = displayTodos.length > 0;
  const hasConversation = processedMessages.length > 0;
  const pendingAssistantState = useMemo(() => {
    let lastHumanIndex = -1;
    let lastAiIndex = -1;
    let lastHumanMessageId: string | undefined;
    let lastAiEntry: { message: Message; toolCalls: ToolCall[] } | null = null;

    for (const [index, entry] of processedMessages.entries()) {
      if (entry.message.type === "human") {
        lastHumanIndex = index;
        lastHumanMessageId = entry.message.id;
        continue;
      }

      if (entry.message.type === "ai") {
        lastAiIndex = index;
        lastAiEntry = entry;
      }
    }

    const latestAiContent = lastAiEntry
      ? sanitizeAssistantDisplayText(
          extractStringFromMessageContent(lastAiEntry.message)
        ).trim()
      : "";
    const latestAiHasUi = Boolean(
      lastAiEntry &&
        Array.isArray(ui) &&
        ui.some((entry: any) => entry.metadata?.message_id === lastAiEntry?.message.id)
    );
    const latestAiHasVisibleOutput = Boolean(
      latestAiContent ||
        (lastAiEntry?.toolCalls.length ?? 0) > 0 ||
        latestAiHasUi
    );

    return {
      lastHumanIndex,
      lastAiIndex,
      lastHumanMessageId,
      latestAiHasVisibleOutput,
    };
  }, [processedMessages, ui]);
  const showPendingAssistantIndicator = useMemo(() => {
    if (!(isSubmitPending || isLoading)) {
      return false;
    }

    if (pendingAssistantState.lastHumanIndex === -1) {
      return submitPhase !== "idle";
    }

    if (pendingAssistantState.lastHumanIndex > pendingAssistantState.lastAiIndex) {
      return true;
    }

    return (
      pendingAssistantState.lastAiIndex > pendingAssistantState.lastHumanIndex &&
      !pendingAssistantState.latestAiHasVisibleOutput
    );
  }, [isLoading, isSubmitPending, pendingAssistantState, submitPhase]);
  const pendingAssistantPhase =
    submitPhase === "idle"
      ? isLoading
        ? "streaming"
        : "awaiting-stream"
      : submitPhase;
  const pendingIndicatorSpacingClass =
    processedMessages.length === 0
      ? undefined
      : effectiveUiPreferences.conversationDensity === "compact"
        ? "mt-4"
        : "mt-5";

  const workspaceContextPanel =
    hasTasks ? (
      <div
        className={cn(
          "rounded-[16px] border border-[rgba(24,33,38,0.08)]",
          isNotebookLayout ? "bg-[rgba(255,255,255,0.88)]" : "bg-white"
        )}
      >
        {!metaOpen ? (
          <div className="px-4 py-3">
            {isNotebookLayout ? (
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Current workspace
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {hasTasks && (
                <button
                  type="button"
                  onClick={() => setMetaOpen("tasks")}
                  className="inline-flex items-center gap-2 rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] px-3 py-1.5 text-left"
                >
                  {getStatusIcon(
                    groupedTodos.in_progress[0]?.status ?? "pending"
                  )}
                  <span>
                    Tasks{" "}
                    <span className="text-muted-foreground">
                      {groupedTodos.completed.length}/{displayTodos.length}
                    </span>
                  </span>
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="px-4 py-3">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground">
                Tasks
              </div>
              <button
                type="button"
                onClick={() => setMetaOpen(null)}
                className="text-xs text-muted-foreground"
              >
                Close
              </button>
            </div>

            <div>
              {metaOpen === "tasks" &&
                Object.entries(groupedTodos)
                  .filter(([_, todoItems]) => todoItems.length > 0)
                  .map(([status, todoItems]) => (
                    <div
                      key={status}
                      className="mb-4 last:mb-0"
                    >
                      <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
                        {
                          {
                            pending: "Pending",
                            in_progress: "In Progress",
                            completed: "Completed",
                          }[status]
                        }
                      </h3>
                      <div className="space-y-2">
                        {todoItems.map((todo, index) => (
                          <div
                            key={`${status}_${todo.id}_${index}`}
                            className="flex items-start gap-2 text-sm text-foreground"
                          >
                            {getStatusIcon(todo.status, "mt-0.5")}
                            <span className="break-words">
                              {todo.content}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
            </div>
          </div>
        )}
      </div>
    ) : null;

  const actionRequestsMap: Map<string, ActionRequest> | null = useMemo(() => {
    const actionRequests =
      interrupt?.value && (interrupt.value as any)["action_requests"];
    if (!actionRequests) return new Map<string, ActionRequest>();
    return new Map(actionRequests.map((ar: ActionRequest) => [ar.name, ar]));
  }, [interrupt]);

  const reviewConfigsMap: Map<string, ReviewConfig> | null = useMemo(() => {
    const reviewConfigs =
      interrupt?.value && (interrupt.value as any)["review_configs"];
    if (!reviewConfigs) return new Map<string, ReviewConfig>();
    return new Map(
      reviewConfigs.map((rc: ReviewConfig) => [rc.actionName, rc])
    );
  }, [interrupt]);

  const activeParameterRequest = useMemo(() => {
    const interruptValue =
      interrupt?.value && typeof interrupt.value === "object"
        ? (interrupt.value as Record<string, unknown>)
        : null;
    const interruptRequest = isParameterRequestPayload(interruptValue)
      ? interruptValue
      : interruptValue?.["parameter_request"];
    if (
      isParameterRequestPayload(interruptRequest) &&
      !dismissedParameterRequestIds.has(
        `${interruptRequest.request_id}::${interrupt?.ns?.join("/") ?? "interrupt"}`
      )
    ) {
      return {
        request: interruptRequest,
        instanceId: `${interruptRequest.request_id}::${interrupt?.ns?.join("/") ?? "interrupt"}`,
        source: "interrupt" as const,
      };
    }

    for (let messageIndex = processedMessages.length - 1; messageIndex >= 0; messageIndex -= 1) {
      const processedMessage = processedMessages[messageIndex];
      for (
        let toolIndex = processedMessage.toolCalls.length - 1;
        toolIndex >= 0;
        toolIndex -= 1
      ) {
        const payload =
          parseToolResultPayload(processedMessage.toolCalls[toolIndex].artifact) ??
          parseToolResultPayload(processedMessage.toolCalls[toolIndex].result);
        const request =
          payload && isParameterRequestPayload(payload.parameter_request)
            ? payload.parameter_request
            : null;
        if (
          request &&
          !dismissedParameterRequestIds.has(
            `${request.request_id}::${processedMessage.message.id ?? toolIndex}`
          )
        ) {
          return {
            request,
            instanceId: `${request.request_id}::${processedMessage.message.id ?? toolIndex}`,
            source: "tool_result" as const,
          };
        }
      }
    }

    return null;
  }, [dismissedParameterRequestIds, interrupt, processedMessages]);

  const dismissParameterRequest = useCallback((instanceId: string) => {
    setDismissedParameterRequestIds((current) => {
      const next = new Set(current);
      next.add(instanceId);
      return next;
    });
  }, []);

  const handleParameterRequestComplete = useCallback(
    (
      instanceId: string,
      requestId: string,
      answers: Record<string, unknown>,
      source: "interrupt" | "tool_result"
    ) => {
      setDismissedParameterRequestIds((current) => {
        const next = new Set(current);
        next.add(instanceId);
        return next;
      });

      if (source === "interrupt") {
        resumeInterrupt({
          parameter_request_response: {
            request_id: requestId,
            answers,
          },
        });
        return;
      }

      const questionLookup = new Map(
        activeParameterRequest?.request.questions.map((question) => [
          question.key,
          question.label,
        ]) ?? []
      );
      const answerLines = Object.entries(answers).map(([key, value]) => {
        const label = questionLookup.get(key) ?? key;
        return `- ${label}: ${String(value)}`;
      });
      const summaryMessage = [
        "Parameter confirmation for the active Experiment Plan:",
        ...answerLines,
        "",
        "Use these values to continue the blocked plan.",
      ].join("\n");

      const nextFiles =
        labDefaultsThreadFile != null
          ? { ...files, ...labDefaultsThreadFile }
          : undefined;
      const nextStatePatch = {
        ...(labDefaultsStatePatch ?? {}),
        ...(nextFiles ? { files: nextFiles } : {}),
      };
      if (submitLockRef.current || isLoading) {
        return;
      }
      submitLockRef.current = true;
      setSubmitPhase("awaiting-stream");
      sendMessage(
        summaryMessage,
        Object.keys(nextStatePatch).length > 0 ? nextStatePatch : undefined
      );
    },
    [
      activeParameterRequest,
      files,
      labDefaultsStatePatch,
      labDefaultsThreadFile,
      isLoading,
      resumeInterrupt,
      sendMessage,
    ]
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-transparent">
      <div
        ref={scrollRef}
        className="chat-scroll-area scrollbar-pretty min-h-0 flex-1 overflow-y-auto"
      >
        <div
          ref={contentRef}
          className={cn(
            "mx-auto w-full px-4 pb-10 pt-6 sm:px-6",
            isNotebookLayout ? "max-w-[860px]" : "max-w-[900px]"
          )}
        >
          {isThreadLoading ? (
            <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
              Loading...
            </div>
          ) : (
            <>
              {isNotebookLayout ? workspaceContextPanel : null}

              {!hasConversation && (
                <div className="mb-8 rounded-[18px] border border-[rgba(24,33,38,0.08)] bg-white px-5 py-5">
                  <p className="text-[15px] leading-7 text-muted-foreground">
                    Ask for a protocol, a cell search, a standards-based test
                    plan, or a raw dataset inspection.
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {QUICK_START_PROMPTS.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => handleQuickStart(prompt)}
                        disabled={submitDisabled || isLoading}
                        className="rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] px-3 py-2 text-left text-xs text-foreground transition-colors hover:bg-[rgba(232,242,239,0.9)] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-col">
                {processedMessages.map((data, index) => {
                  const messageUi = messageUiMap.get(data.message.id ?? "") ?? EMPTY_MESSAGE_UI;
                  const isLastMessage = index === processedMessages.length - 1;
                  const previousEntry =
                    index > 0 ? processedMessages[index - 1] : null;
                  const useCompactToolSpacing = Boolean(
                    previousEntry &&
                      isToolOnlyAssistantEntry(previousEntry) &&
                      isToolOnlyAssistantEntry(data)
                  );
                  const messageSpacingClass =
                    index === 0
                      ? undefined
                      : useCompactToolSpacing
                        ? "mt-2"
                        : effectiveUiPreferences.conversationDensity === "compact"
                          ? "mt-4"
                          : "mt-5";

                  return (
                    <div
                      key={data.message.id}
                      className={messageSpacingClass}
                    >
                      <ChatMessage
                        message={data.message}
                        toolCalls={data.toolCalls}
                        isLoading={isLastMessage ? isLoading : false}
                        isStreamingMessage={
                          Boolean(
                            isLoading &&
                              isLastMessage &&
                              data.message.type === "ai"
                          )
                        }
                        actionRequestsMap={
                          isLastMessage ? actionRequestsMap : undefined
                        }
                        reviewConfigsMap={
                          isLastMessage ? reviewConfigsMap : undefined
                        }
                        ui={messageUi}
                        stream={isLastMessage ? stream : undefined}
                        onResumeInterrupt={isLastMessage ? resumeInterrupt : undefined}
                        graphId={assistant?.graph_id}
                        smoothStreaming={effectiveUiPreferences.smoothStreaming}
                        conversationDensity={effectiveUiPreferences.conversationDensity}
                      />
                    </div>
                  );
                })}
                {showPendingAssistantIndicator && (
                  <div className={pendingIndicatorSpacingClass}>
                    <PendingAssistantIndicator
                      phase={pendingAssistantPhase}
                      requestKey={pendingAssistantState.lastHumanMessageId}
                    />
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="border-t border-[rgba(24,33,38,0.08)] bg-[rgba(246,244,239,0.96)] px-4 py-3 sm:px-6">
        <div
          className={cn(
            "mx-auto flex w-full flex-col gap-3",
            isNotebookLayout ? "max-w-[860px]" : "max-w-[900px]"
          )}
        >
          {!isNotebookLayout ? workspaceContextPanel : null}

          {activeParameterRequest && (
            <ParameterRequestPopup
              instanceId={activeParameterRequest.instanceId}
              request={activeParameterRequest.request}
              source={activeParameterRequest.source}
              onDismiss={dismissParameterRequest}
              onComplete={handleParameterRequestComplete}
              isLoading={isLoading}
            />
          )}

          <form
            onSubmit={handleSubmit}
            className="rounded-[20px] border border-[rgba(24,33,38,0.08)] bg-white shadow-[0_10px_24px_rgba(24,33,38,0.04)]"
          >
            <input
              ref={fileInputRef}
              id="chat-attachment-input"
              type="file"
              multiple
              accept=".pdf,.csv,.tsv,.xlsx,.xls,.json,.txt,.md,.markdown,.yaml,.yml,.xml,.log,.py,.ipynb,.js,.jsx,.ts,.tsx,.html,.htm"
              tabIndex={-1}
              aria-hidden="true"
              className="pointer-events-none absolute -left-[9999px] top-auto h-px w-px overflow-hidden opacity-0"
              onChange={(event) => {
                void handleAttachmentSelection(event);
              }}
            />
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isLoading
                  ? "Running..."
                  : "Ask a question or start a planning / simulation task..."
              }
              className={cn(
                "field-sizing-content w-full resize-none border-0 bg-transparent px-4 pb-3 pt-4 text-[15px] text-foreground outline-none placeholder:text-muted-foreground",
                effectiveUiPreferences.conversationDensity === "compact"
                  ? "min-h-[72px] leading-[1.6]"
                  : "min-h-[82px] leading-[1.7]"
              )}
              rows={1}
            />
            {(pendingAttachments.length > 0 || isAttaching) && (
              <div className="flex flex-wrap gap-2 border-t border-[rgba(24,33,38,0.08)] px-4 py-3">
                {pendingAttachments.map((attachment) => (
                  <div
                    key={attachment.id}
                    className="inline-flex max-w-full items-center gap-2 rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] px-3 py-1.5 text-xs text-foreground"
                  >
                    {attachment.summaryLabel === "metadata placeholder" ? (
                      <AlertCircle
                        size={14}
                        className="shrink-0 text-amber-600"
                      />
                    ) : (
                      <FileIcon size={14} className="shrink-0 text-muted-foreground" />
                    )}
                    <div className="min-w-0">
                      <div className="truncate font-medium">{attachment.name}</div>
                      <div className="truncate text-[11px] text-muted-foreground">
                        {attachment.summaryLabel} · {formatBytes(attachment.sizeBytes)}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removePendingAttachment(attachment.id)}
                      className="rounded-full p-0.5 text-muted-foreground transition-colors hover:bg-[rgba(24,33,38,0.08)] hover:text-foreground"
                      aria-label={`Remove ${attachment.name}`}
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
                {isAttaching && (
                  <div className="inline-flex items-center gap-2 rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] px-3 py-1.5 text-xs text-muted-foreground">
                    <Loader2 size={14} className="animate-spin" />
                    <span>Processing attachment…</span>
                  </div>
                )}
              </div>
            )}
            <div className="flex flex-col gap-3 border-t border-[rgba(24,33,38,0.08)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <label
                  htmlFor="chat-attachment-input"
                  aria-disabled={attachmentDisabled}
                  className={cn(
                    "inline-flex h-9 w-9 items-center justify-center rounded-full border text-sm font-medium transition-colors",
                    "border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] hover:bg-accent hover:text-accent-foreground",
                    attachmentDisabled
                      ? "cursor-not-allowed opacity-60 pointer-events-none"
                      : "cursor-pointer"
                  )}
                  onClick={() => {
                    if (fileInputRef.current) {
                      fileInputRef.current.value = "";
                    }
                  }}
                >
                  {isAttaching ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Plus size={15} />
                  )}
                </label>
              </div>

              <div className="flex items-center justify-between gap-3 sm:justify-end">
                <div className="flex min-w-0 flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  {cyclerReadyAttachments.length > 0 && (
                    <button
                      type="button"
                      onClick={() =>
                        void handleDatasheetQuickAction("parse-raw-cycler-export")
                      }
                      disabled={submitDisabled || isLoading}
                      className={cn(
                        "truncate rounded-full border px-2.5 py-1 transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                        selectedAttachmentActions.includes("parse-raw-cycler-export")
                          ? "border-sky-300 bg-sky-100 text-sky-950"
                          : "border-transparent text-muted-foreground hover:border-[rgba(24,33,38,0.08)] hover:text-foreground"
                      )}
                    >
                      Inspect battery data
                    </button>
                  )}
                  {datasheetReadyAttachments.length > 0 && (
                    <>
                      <button
                        type="button"
                        onClick={() =>
                          void handleDatasheetQuickAction("draft-planning")
                        }
                        disabled={submitDisabled || isLoading}
                        className={cn(
                          "truncate rounded-full border px-2.5 py-1 transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                          selectedAttachmentActions.includes("draft-planning")
                            ? "border-amber-300 bg-amber-100 text-amber-950"
                            : "border-transparent text-muted-foreground hover:border-[rgba(24,33,38,0.08)] hover:text-foreground"
                        )}
                      >
                        Use for draft planning
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          void handleDatasheetQuickAction("send-to-admin-review")
                        }
                        disabled={
                          submitDisabled ||
                          isLoading ||
                          datasheetAttachmentsPendingAdmin.length === 0
                        }
                        className={cn(
                          "truncate rounded-full border px-2.5 py-1 transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                          selectedAttachmentActions.includes("send-to-admin-review")
                            ? "border-amber-300 bg-amber-100 text-amber-950"
                            : "border-transparent text-muted-foreground hover:border-[rgba(24,33,38,0.08)] hover:text-foreground"
                        )}
                      >
                        {datasheetAttachmentsPendingAdmin.length === 0
                          ? "Queued for Admin Review"
                          : "Send to Admin Review"}
                      </button>
                    </>
                  )}
                  {selectedAttachmentActions.length > 0 && (
                    <span className="truncate text-[11px] text-amber-700">
                      {`Selected: ${selectedAttachmentActions
                        .map((action) =>
                          action === "parse-raw-cycler-export"
                            ? "battery data inspection"
                            : action === "draft-planning"
                              ? "draft planning"
                              : "admin review"
                        )
                        .join(" + ")}. Press Send.`}
                    </span>
                  )}
                </div>

                <Button
                  type={isLoading ? "button" : "submit"}
                  variant={isLoading ? "outline" : "default"}
                  onClick={isLoading ? stopStream : undefined}
                  disabled={
                    !isLoading &&
                    (submitDisabled ||
                      (input.trim().length === 0 && pendingAttachments.length === 0))
                  }
                  className={cn(
                    "rounded-full px-4",
                    isLoading &&
                      "border-[rgba(36,87,93,0.18)] bg-[rgba(247,250,249,0.96)] text-foreground hover:bg-[rgba(232,242,239,0.94)]"
                  )}
                >
                  {isLoading ? (
                    <>
                      <Square size={14} />
                      <span>Stop</span>
                    </>
                  ) : isSubmitPending ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      <span>Sending...</span>
                    </>
                  ) : (
                    <>
                      <ArrowUp size={16} />
                      <span>Send</span>
                    </>
                  )}
                </Button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
});

ChatInterface.displayName = "ChatInterface";
