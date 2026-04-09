"use client";

export type ChatFileData = {
  content: string[];
  created_at: string;
  modified_at: string;
  [key: string]: unknown;
};

export const LAB_DEFAULTS_THREAD_FILE_PATH = "/context/lab-defaults.json";

export type ChatFileValue =
  | string
  | ChatFileData
  | {
      content?: unknown;
      created_at?: unknown;
      modified_at?: unknown;
      [key: string]: unknown;
    };

export type ChatFileRecord = Record<string, ChatFileValue>;
export type ChatFileUpdate =
  | ChatFileRecord
  | ((prevFiles: ChatFileRecord) => ChatFileRecord);

const UPLOAD_THREAD_FILE_PREFIX = "/uploads/";
const LARGE_TOOL_RESULT_PREFIX = "/large_tool_results/";

function nowIsoString(): string {
  return new Date().toISOString();
}

export function normalizeThreadFilePath(filePath: string): string {
  const trimmed = String(filePath || "").trim().replace(/\\/g, "/");
  if (trimmed.length === 0) {
    return "/";
  }
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

export function createChatFileData(
  content: string,
  createdAt?: string,
  extraFields: Record<string, unknown> = {}
): ChatFileData {
  const normalizedContent = String(content ?? "");
  const now = nowIsoString();

  return {
    ...extraFields,
    content: normalizedContent.split("\n"),
    created_at: createdAt ?? now,
    modified_at: now,
  };
}

export function getChatFileContent(fileValue: ChatFileValue | null | undefined): string {
  if (typeof fileValue === "string") {
    return fileValue;
  }

  if (!fileValue || typeof fileValue !== "object") {
    return "";
  }

  const rawContent = fileValue.content;
  if (Array.isArray(rawContent)) {
    return rawContent.map((line) => String(line ?? "")).join("\n");
  }

  if (typeof rawContent === "string") {
    return rawContent;
  }

  return rawContent == null ? "" : String(rawContent);
}

export function isHiddenChatFile(
  filePath: string,
  fileValue: ChatFileValue | null | undefined
): boolean {
  const normalizedPath = normalizeThreadFilePath(filePath);
  if (
    normalizedPath.startsWith(UPLOAD_THREAD_FILE_PREFIX) ||
    normalizedPath.startsWith(LARGE_TOOL_RESULT_PREFIX)
  ) {
    return true;
  }

  return Boolean(
    fileValue &&
      typeof fileValue === "object" &&
      "hidden" in fileValue &&
      fileValue.hidden === true
  );
}

export function getVisibleChatFiles(files: ChatFileRecord): ChatFileRecord {
  return Object.entries(files).reduce<ChatFileRecord>((acc, [filePath, fileValue]) => {
    if (!isHiddenChatFile(filePath, fileValue)) {
      acc[filePath] = fileValue;
    }
    return acc;
  }, {});
}

export function getChatFileDisplayName(
  filePath: string,
  fileValue: ChatFileValue | null | undefined
): string {
  if (fileValue && typeof fileValue === "object") {
    const rawDisplayName = fileValue.display_name;
    if (typeof rawDisplayName === "string" && rawDisplayName.trim().length > 0) {
      return rawDisplayName.trim();
    }
  }

  const normalizedPath = normalizeThreadFilePath(filePath);
  const segments = normalizedPath.split("/").filter(Boolean);
  return segments[segments.length - 1] || normalizedPath;
}

function isNormalizedChatFileData(fileValue: ChatFileValue): fileValue is ChatFileData {
  return Boolean(
    fileValue &&
      typeof fileValue === "object" &&
      Array.isArray(fileValue.content) &&
      typeof fileValue.created_at === "string" &&
      typeof fileValue.modified_at === "string"
  );
}

function normalizeChatFileValue(fileValue: ChatFileValue): ChatFileData {
  if (isNormalizedChatFileData(fileValue)) {
    return fileValue;
  }

  if (typeof fileValue === "string") {
    return createChatFileData(fileValue);
  }

  if (!fileValue || typeof fileValue !== "object") {
    return createChatFileData("");
  }

  const { created_at, modified_at, content: _content, ...extraFields } =
    fileValue;
  const normalizedContent = getChatFileContent(fileValue);
  const createdAtValue =
    typeof created_at === "string" && created_at.trim().length > 0
      ? created_at
      : undefined;
  const modifiedAtValue =
    typeof modified_at === "string" && modified_at.trim().length > 0
      ? modified_at
      : undefined;

  return {
    ...extraFields,
    content: normalizedContent.split("\n"),
    created_at: createdAtValue ?? nowIsoString(),
    modified_at: modifiedAtValue ?? nowIsoString(),
  };
}

export function normalizeChatFiles(files: ChatFileRecord): Record<string, ChatFileData> {
  return Object.entries(files).reduce<Record<string, ChatFileData>>(
    (acc, [filePath, fileValue]) => {
      acc[normalizeThreadFilePath(filePath)] = normalizeChatFileValue(fileValue);
      return acc;
    },
    {}
  );
}

export function chatFilesNeedNormalization(files: ChatFileRecord): boolean {
  return Object.entries(files).some(([filePath, fileValue]) => {
    if (normalizeThreadFilePath(filePath) !== filePath) {
      return true;
    }

    if (typeof fileValue === "string") {
      return true;
    }

    if (!fileValue || typeof fileValue !== "object") {
      return true;
    }

    if (!Array.isArray(fileValue.content)) {
      return true;
    }

    if (
      typeof fileValue.created_at !== "string" ||
      typeof fileValue.modified_at !== "string"
    ) {
      return true;
    }

    return false;
  });
}
