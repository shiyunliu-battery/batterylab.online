"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Assistant } from "@langchain/langgraph-sdk";
import {
  Activity,
  ArrowUpRight,
  CheckCircle,
  Circle,
  Clock,
  FileText,
  Files,
  FolderOpen,
  MessageSquare,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Settings,
  Sparkles,
  SquarePen,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import type { ImperativePanelHandle } from "react-resizable-panels";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { ChatInterface } from "@/app/components/ChatInterface";
import { FileViewDialog } from "@/app/components/FileViewDialog";
import { ThreadList } from "@/app/components/ThreadList";
import { useChatContext } from "@/providers/ChatProvider";
import {
  createChatFileData,
  getChatFileContent,
  getChatFileDisplayName,
  getVisibleChatFiles,
  LAB_DEFAULTS_THREAD_FILE_PATH,
  normalizeThreadFilePath,
  type ChatFileRecord,
  type ChatFileValue,
} from "@/app/lib/chatFiles";
import type { FileItem, TodoItem } from "@/app/types/types";
import {
  type LabDefaultsConfig,
  type UiPreferencesConfig,
} from "@/lib/config";
import { cn } from "@/lib/utils";

type NotebookTab = "sources" | "chat" | "studio";

interface NotebookWorkspaceProps {
  assistant: Assistant | null;
  assistantId: string;
  labDefaults?: LabDefaultsConfig;
  uiPreferences?: UiPreferencesConfig;
  sourcesPanelOpen: boolean;
  onOpenSources: () => void;
  onCloseSources: () => void;
  onNewThread: () => void | Promise<void>;
  onThreadSelect: (id: string) => void | Promise<void>;
  onOpenSettings: () => void;
  onMutateReady?: (mutate: () => void) => void;
  onInterruptCountChange?: (count: number) => void;
}

type NotebookFileEntry = {
  path: string;
  title: string;
  badge: string;
  preview: string;
  modifiedAtLabel: string;
  generatedFileKind?: string;
  displayName?: string;
  value: ChatFileValue;
};

function SectionCard({
  icon: Icon,
  eyebrow,
  title,
  subtitle,
  action,
  className,
  contentClassName,
  children,
}: {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
  contentClassName?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "flex min-h-0 flex-col overflow-hidden rounded-[22px] border border-[rgba(24,33,38,0.08)] bg-[rgba(255,255,255,0.92)] shadow-[0_12px_30px_rgba(24,33,38,0.04)] backdrop-blur",
        className
      )}
    >
      <div className="flex items-start justify-between gap-3 border-b border-[rgba(24,33,38,0.08)] px-4 py-3.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(232,242,239,0.9)] text-[rgba(17,92,73,0.92)]">
              <Icon className="h-4 w-4" />
            </span>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[rgba(94,84,72,0.78)]">
              {eyebrow}
            </p>
          </div>
          <h2 className="mt-3 text-[14px] font-semibold tracking-[-0.01em] text-foreground">
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-1 text-[13px] leading-6 text-muted-foreground">
              {subtitle}
            </p>
          ) : null}
        </div>
        {action}
      </div>
      <div className={cn("min-h-0 flex-1", contentClassName)}>{children}</div>
    </section>
  );
}

function stripUploadPrefixName(name: string): string {
  const trimmed = String(name || "").trim();
  if (!trimmed) {
    return trimmed;
  }

  return trimmed.replace(
    /^[0-9a-f]{8,}(?:-[0-9a-f]{4,})*-(?=[A-Za-z0-9].+)/i,
    ""
  );
}

function getRawFileName(filePath: string): string {
  const normalizedPath = normalizeThreadFilePath(filePath);
  const segments = normalizedPath.split("/").filter(Boolean);
  return segments[segments.length - 1] || normalizedPath;
}

function getFileExtensionFromPath(filePath: string): string {
  const fileName = getRawFileName(filePath);
  const lastDotIndex = fileName.lastIndexOf(".");
  return lastDotIndex > -1 ? fileName.slice(lastDotIndex + 1).toLowerCase() : "";
}

function getSemanticSourceExtension(
  filePath: string,
  fileValue: ChatFileValue
): string {
  if (fileValue && typeof fileValue === "object") {
    const originalFileName =
      typeof fileValue.original_filename === "string"
        ? fileValue.original_filename.trim()
        : "";
    if (originalFileName) {
      const lastDotIndex = originalFileName.lastIndexOf(".");
      if (lastDotIndex > -1) {
        return originalFileName.slice(lastDotIndex + 1).toLowerCase();
      }
    }
  }

  const fileName = getRawFileName(filePath).toLowerCase();
  if (fileName.endsWith(".xlsx.txt")) {
    return "xlsx";
  }
  if (fileName.endsWith(".xls.txt")) {
    return "xls";
  }
  if (fileName.endsWith(".pdf.txt")) {
    return "pdf";
  }

  return getFileExtensionFromPath(filePath);
}

function getNotebookFileDisplayName(
  filePath: string,
  fileValue: ChatFileValue
): string {
  if (fileValue && typeof fileValue === "object") {
    const originalFileName =
      typeof fileValue.original_filename === "string"
        ? fileValue.original_filename.trim()
        : "";
    if (originalFileName) {
      return originalFileName;
    }
  }

  return stripUploadPrefixName(getChatFileDisplayName(filePath, fileValue));
}

function getFilePreviewSnippet(fileValue: ChatFileValue): string {
  if (fileValue && typeof fileValue === "object") {
    const rawContent = fileValue.content;
    if (Array.isArray(rawContent)) {
      for (let index = 0; index < Math.min(rawContent.length, 8); index += 1) {
        const trimmedLine = String(rawContent[index] ?? "").trim();
        if (trimmedLine.length > 0) {
          return trimmedLine.length > 140
            ? `${trimmedLine.slice(0, 137)}...`
            : trimmedLine;
        }
      }
      return "No preview text available yet.";
    }

    if (typeof rawContent === "string") {
      const trimmedLine = rawContent.trim().split(/\r?\n/, 1)[0] ?? "";
      if (trimmedLine.length > 0) {
        return trimmedLine.length > 140
          ? `${trimmedLine.slice(0, 137)}...`
          : trimmedLine;
      }
    }
  }

  return "No preview text available yet.";
}

function getFileModifiedAtLabel(fileValue: ChatFileValue): string {
  if (
    fileValue &&
    typeof fileValue === "object" &&
    typeof fileValue.modified_at === "string"
  ) {
    const timestamp = Date.parse(fileValue.modified_at);
    if (Number.isFinite(timestamp)) {
      const elapsedMinutes = Math.max(
        0,
        Math.floor((Date.now() - timestamp) / 60_000)
      );
      if (elapsedMinutes < 1) {
        return "Updated just now";
      }
      if (elapsedMinutes < 60) {
        return `Updated ${elapsedMinutes}m ago`;
      }
      const elapsedHours = Math.floor(elapsedMinutes / 60);
      if (elapsedHours < 24) {
        return `Updated ${elapsedHours}h ago`;
      }
      const elapsedDays = Math.floor(elapsedHours / 24);
      if (elapsedDays < 7) {
        return `Updated ${elapsedDays}d ago`;
      }
      return `Updated ${new Date(timestamp).toLocaleDateString()}`;
    }
  }

  return "Updated recently";
}

function getSourceBadge(filePath: string, fileValue: ChatFileValue): string {
  const normalizedPath = normalizeThreadFilePath(filePath);
  const fileName = getRawFileName(normalizedPath).toLowerCase();

  if (
    fileValue &&
    typeof fileValue === "object" &&
    fileValue.system_file_kind === "thread_attachment_preview"
  ) {
    if (fileName.endsWith(".upload.json")) {
      return "Metadata placeholder";
    }
    if (fileName.endsWith(".xlsx.txt") || fileName.endsWith(".xls.txt")) {
      return "Spreadsheet preview";
    }
    if (fileName.endsWith(".pdf.txt")) {
      return "PDF preview";
    }
    return "Attachment preview";
  }

  if (normalizedPath.startsWith("/uploads/")) {
    return "Uploaded source";
  }

  return "Thread file";
}

function getArtifactBadge(filePath: string, fileValue: ChatFileValue): string {
  if (fileValue && typeof fileValue === "object") {
    switch (fileValue.generated_file_kind) {
      case "clean_experiment_plan":
        return "Experiment plan";
      case "cell_background_summary":
        return "Cell brief";
      case "cell_catalog_export":
        return "Catalog export";
      case "parsed_cycler_summary":
        return "Cycle summary";
      case "parsed_cycler_dataset":
        return "Normalized dataset";
      case "parsed_cycler_preview":
        return "Dataset preview";
      default:
        break;
    }
  }

  const extension = getRawFileName(filePath).split(".").pop()?.toUpperCase();
  return extension ? `${extension} artifact` : "Artifact";
}

function getFileSortTimestamp(fileValue: ChatFileValue): number {
  if (
    fileValue &&
    typeof fileValue === "object" &&
    typeof fileValue.modified_at === "string"
  ) {
    const timestamp = Date.parse(fileValue.modified_at);
    if (Number.isFinite(timestamp)) {
      return timestamp;
    }
  }

  return 0;
}

function getTodoStatusIcon(status: TodoItem["status"]) {
  switch (status) {
    case "completed":
      return <CheckCircle className="mt-0.5 h-4 w-4 text-emerald-600" />;
    case "in_progress":
      return <Clock className="mt-0.5 h-4 w-4 text-amber-600" />;
    default:
      return <Circle className="mt-0.5 h-4 w-4 text-muted-foreground" />;
  }
}

function FileList({
  entries,
  emptyLabel,
  tone,
  onOpen,
}: {
  entries: NotebookFileEntry[];
  emptyLabel: string;
  tone: "source" | "artifact";
  onOpen: (entry: NotebookFileEntry) => void;
}) {
  if (entries.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center">
        <p className="max-w-[260px] text-sm leading-6 text-muted-foreground">
          {emptyLabel}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3 p-4">
      {entries.map((entry) => (
        <button
          key={entry.path}
          type="button"
          onClick={() => onOpen(entry)}
          className={cn(
            "group w-full rounded-[18px] border px-4 py-4 text-left transition-all hover:-translate-y-0.5",
            tone === "source"
              ? "border-[rgba(36,59,51,0.08)] bg-[linear-gradient(180deg,rgba(250,249,245,0.96),rgba(244,241,234,0.96))] hover:border-[rgba(17,92,73,0.16)] hover:shadow-[0_14px_30px_rgba(24,33,38,0.06)]"
              : "border-[rgba(34,50,61,0.08)] bg-[linear-gradient(180deg,rgba(248,250,252,0.98),rgba(240,245,250,0.98))] hover:border-[rgba(54,92,131,0.16)] hover:shadow-[0_14px_30px_rgba(24,33,38,0.06)]"
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium",
                  tone === "source"
                    ? "bg-[rgba(232,242,239,0.96)] text-[rgba(17,92,73,0.94)]"
                    : "bg-[rgba(232,239,249,0.98)] text-[rgba(54,92,131,0.98)]"
                )}
              >
                {entry.badge}
              </span>
              <p className="mt-3 truncate text-sm font-semibold text-foreground">
                {entry.title}
              </p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {entry.preview}
              </p>
            </div>
            <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </div>
          <div className="mt-4 flex items-center justify-between gap-3 text-[11px] text-muted-foreground">
            <span className="truncate">{entry.path}</span>
            <span className="shrink-0">{entry.modifiedAtLabel}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

export function NotebookWorkspace({
  assistant,
  assistantId,
  labDefaults,
  uiPreferences,
  sourcesPanelOpen,
  onOpenSources,
  onCloseSources,
  onNewThread,
  onThreadSelect,
  onOpenSettings,
  onMutateReady,
  onInterruptCountChange,
}: NotebookWorkspaceProps) {
  const [mobileTab, setMobileTab] = useState<NotebookTab>("chat");
  const [isStudioCollapsed, setIsStudioCollapsed] = useState(false);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const studioPanelRef = useRef<ImperativePanelHandle | null>(null);
  const hadWorkspaceShellRef = useRef(false);
  const { files, setFiles, todos, isLoading, interrupt } = useChatContext();

  const syncStudioCollapsedState = useCallback((collapsed: boolean) => {
    setIsStudioCollapsed(collapsed);
  }, []);

  const handleToggleStudioPanel = useCallback(() => {
    const panel = studioPanelRef.current;
    if (!panel) {
      syncStudioCollapsedState(!isStudioCollapsed);
      return;
    }

    if (panel.isCollapsed()) {
      panel.expand();
      return;
    }

    panel.collapse();
  }, [isStudioCollapsed, syncStudioCollapsedState]);

  const visibleFiles = useMemo(() => getVisibleChatFiles(files), [files]);

  const sourceEntries = useMemo<NotebookFileEntry[]>(() => {
    return Object.entries(files)
      .filter(([filePath, fileValue]) => {
        const normalizedPath = normalizeThreadFilePath(filePath);
        if (normalizedPath === LAB_DEFAULTS_THREAD_FILE_PATH) {
          return false;
        }

        if (normalizedPath.startsWith("/uploads/")) {
          return true;
        }

        return Boolean(
          fileValue &&
            typeof fileValue === "object" &&
            fileValue.system_file_kind === "thread_attachment_preview"
        );
      })
      .sort(([, leftValue], [, rightValue]) => {
        return getFileSortTimestamp(rightValue) - getFileSortTimestamp(leftValue);
      })
      .map(([filePath, fileValue]) => ({
        path: filePath,
        title: getNotebookFileDisplayName(filePath, fileValue),
        badge: getSourceBadge(filePath, fileValue),
        preview: getFilePreviewSnippet(fileValue),
        modifiedAtLabel: getFileModifiedAtLabel(fileValue),
        displayName: getNotebookFileDisplayName(filePath, fileValue),
        value: fileValue,
      }));
  }, [files]);

  const artifactEntries = useMemo<NotebookFileEntry[]>(() => {
    return Object.entries(visibleFiles)
      .filter(([filePath]) => normalizeThreadFilePath(filePath) !== LAB_DEFAULTS_THREAD_FILE_PATH)
      .sort(([leftPath, leftValue], [rightPath, rightValue]) => {
        const leftKind =
          leftValue &&
          typeof leftValue === "object" &&
          typeof leftValue.generated_file_kind === "string"
            ? leftValue.generated_file_kind
            : "";
        const rightKind =
          rightValue &&
          typeof rightValue === "object" &&
          typeof rightValue.generated_file_kind === "string"
            ? rightValue.generated_file_kind
            : "";

        const priorityOrder = [
          "clean_experiment_plan",
          "cell_background_summary",
          "parsed_cycler_summary",
          "parsed_cycler_dataset",
          "parsed_cycler_preview",
          "cell_catalog_export",
        ];
        const leftPriority = priorityOrder.indexOf(leftKind);
        const rightPriority = priorityOrder.indexOf(rightKind);

        if (leftPriority !== rightPriority) {
          if (leftPriority === -1) {
            return 1;
          }
          if (rightPriority === -1) {
            return -1;
          }
          return leftPriority - rightPriority;
        }

        const modifiedDelta =
          getFileSortTimestamp(rightValue) - getFileSortTimestamp(leftValue);
        if (modifiedDelta !== 0) {
          return modifiedDelta;
        }

        return leftPath.localeCompare(rightPath);
      })
      .map(([filePath, fileValue]) => ({
        path: filePath,
        title: getNotebookFileDisplayName(filePath, fileValue),
        badge: getArtifactBadge(filePath, fileValue),
        preview: getFilePreviewSnippet(fileValue),
        modifiedAtLabel: getFileModifiedAtLabel(fileValue),
        generatedFileKind:
          fileValue &&
          typeof fileValue === "object" &&
          typeof fileValue.generated_file_kind === "string"
            ? fileValue.generated_file_kind
            : undefined,
        displayName: getChatFileDisplayName(filePath, fileValue),
        value: fileValue,
      }));
  }, [visibleFiles]);

  const dataSourceEntries = useMemo(
    () =>
      sourceEntries.filter((entry) => {
        const extension = getSemanticSourceExtension(entry.path, entry.value);
        return ["csv", "tsv", "xls", "xlsx"].includes(extension);
      }),
    [sourceEntries]
  );

  const documentSourceEntries = useMemo(
    () =>
      sourceEntries.filter((entry) => {
        const extension = getSemanticSourceExtension(entry.path, entry.value);
        return ["pdf", "md", "markdown", "html", "htm"].includes(extension);
      }),
    [sourceEntries]
  );

  const planArtifacts = useMemo(
    () =>
      artifactEntries.filter(
        (entry) => entry.generatedFileKind === "clean_experiment_plan"
      ),
    [artifactEntries]
  );

  const dataArtifacts = useMemo(
    () =>
      artifactEntries.filter((entry) =>
        [
          "parsed_cycler_summary",
          "parsed_cycler_dataset",
          "parsed_cycler_preview",
        ].includes(String(entry.generatedFileKind || ""))
      ),
    [artifactEntries]
  );

  const evidenceArtifacts = useMemo(
    () =>
      artifactEntries.filter((entry) =>
        ["cell_background_summary", "cell_catalog_export"].includes(
          String(entry.generatedFileKind || "")
        )
      ),
    [artifactEntries]
  );

  const runState = useMemo(() => {
    if (interrupt !== undefined) {
      return {
        label: "Needs attention",
        description:
          "The workflow paused for a review step or a required parameter.",
        accentClass:
          "border-amber-200 bg-amber-50 text-amber-900",
        icon: TriangleAlert,
      };
    }

    if (isLoading) {
      return {
        label: "Running",
        description:
          "The assistant is reading sources, calling tools, or drafting an artifact.",
        accentClass: "border-sky-200 bg-sky-50 text-sky-900",
        icon: Activity,
      };
    }

    if (artifactEntries.length > 0) {
      return {
        label: "Ready",
        description:
          "Recent outputs are pinned here and can be opened, exported, or revised.",
        accentClass:
          "border-emerald-200 bg-emerald-50 text-emerald-900",
        icon: CheckCircle,
      };
    }

    return {
      label: "Waiting for input",
      description:
        "Add a source or start a prompt to begin building a new experiment context.",
      accentClass:
        "border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.92)] text-foreground",
        icon: MessageSquare,
    };
  }, [artifactEntries.length, interrupt, isLoading]);

  const latestPlanArtifact = planArtifacts[0] ?? null;
  const latestDataArtifact = dataArtifacts[0] ?? null;
  const latestEvidenceArtifact = evidenceArtifacts[0] ?? null;


  const handleOpenEntry = useCallback((entry: NotebookFileEntry) => {
    setSelectedFile({
      path: entry.path,
      content: getChatFileContent(entry.value),
      generatedFileKind: entry.generatedFileKind,
      displayName: entry.displayName,
    });
  }, []);

  const handleSaveFile = useCallback(
    async (fileName: string, content: string) => {
      const existingFile = files[fileName];
      const existingCreatedAt =
        existingFile &&
        typeof existingFile === "object" &&
        typeof existingFile.created_at === "string"
          ? existingFile.created_at
          : undefined;
      const existingMetadata =
        existingFile && typeof existingFile === "object"
          ? Object.fromEntries(
              Object.entries(existingFile).filter(
                ([key]) => !["content", "created_at", "modified_at"].includes(key)
              )
            )
          : {};

      await setFiles((currentFiles: ChatFileRecord) => ({
        ...currentFiles,
        [fileName]: createChatFileData(content, existingCreatedAt, {
          ...existingMetadata,
          ...(existingMetadata.generated_file_kind
            ? { user_edited: true }
            : {}),
        }),
      }));

      setSelectedFile({
        path: fileName,
        content,
        generatedFileKind:
          typeof existingMetadata.generated_file_kind === "string"
            ? existingMetadata.generated_file_kind
            : undefined,
        displayName:
          typeof existingMetadata.display_name === "string"
            ? existingMetadata.display_name
            : undefined,
      });
    },
    [files, setFiles]
  );

  const sourcesPanel = (
    <div className="relative h-full overflow-hidden rounded-[20px] border border-[rgba(24,33,38,0.08)] bg-[rgba(248,247,244,0.9)]">
      <ThreadList
        assistantId={assistantId}
        uiPreferences={uiPreferences}
        onNewThread={onNewThread}
        onThreadSelect={onThreadSelect}
        onOpenSettings={onOpenSettings}
        onMutateReady={onMutateReady}
        onClose={onCloseSources}
        onInterruptCountChange={onInterruptCountChange}
      />
    </div>
  );

  const chatPanel = (
    <div className="flex h-full flex-col p-3">
      <section className="flex min-h-0 flex-1 flex-col rounded-[26px] border border-[rgba(24,33,38,0.08)] bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(249,247,242,0.94))] shadow-[0_18px_42px_rgba(24,33,38,0.05)]">
        <ChatInterface
          assistant={assistant}
          labDefaults={labDefaults}
          uiPreferences={uiPreferences}
          layoutMode="notebook"
        />
      </section>
    </div>
  );

  const collapsedSourcesRail = (
    <aside className="m-2 mr-0 flex w-[46px] shrink-0 flex-col overflow-hidden rounded-[16px] border border-[rgba(24,33,38,0.08)] bg-[rgba(248,247,244,0.9)] shadow-[0_10px_28px_rgba(24,33,38,0.04)]">
      <div className="flex min-h-0 flex-1 flex-col gap-1 p-1">
        <button
          type="button"
          onClick={onOpenSources}
          className="flex h-9 w-9 items-center justify-center self-center text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Open history panel"
          title="History"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => void onNewThread()}
          className="flex h-9 w-9 items-center justify-center self-center text-[#24575d] transition-colors hover:text-[#183f44]"
          aria-label="Start new session"
          title="New session"
        >
          <SquarePen className="h-4 w-4" />
        </button>
        <div className="mt-auto flex justify-center">
          <button
            type="button"
            onClick={onOpenSettings}
            className="flex h-9 w-9 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
            aria-label="Open settings"
            title="Settings"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );

  const hasToolApprovalInterrupt = useMemo(() => {
    if (!interrupt?.value || typeof interrupt.value !== "object") {
      return false;
    }

    const actionRequests = (interrupt.value as Record<string, unknown>)[
      "action_requests"
    ];

    return Array.isArray(actionRequests) && actionRequests.length > 0;
  }, [interrupt]);

  const showWorkflowModule =
    interrupt !== undefined && !hasToolApprovalInterrupt;
  const showTaskBoard = todos.length > 0;
  const showDataModule =
    dataArtifacts.length > 0 || dataSourceEntries.length > 0;
  const showPlanningModule =
    planArtifacts.length > 0 || documentSourceEntries.length > 0;
  const showEvidenceModule = evidenceArtifacts.length > 0;
  const showArtifactShelf = artifactEntries.length > 0;
  const showSourcesModule = sourceEntries.length > 0;
  const hasWorkspaceShell =
    showWorkflowModule ||
    showDataModule ||
    showPlanningModule ||
    showEvidenceModule ||
    showArtifactShelf ||
    showSourcesModule;
  const hasWorkspaceContent =
    hasWorkspaceShell ||
    showTaskBoard;

  useEffect(() => {
    if (!hasWorkspaceShell) {
      hadWorkspaceShellRef.current = false;
      syncStudioCollapsedState(false);
      return;
    }

    if (!hadWorkspaceShellRef.current) {
      syncStudioCollapsedState(false);
      window.requestAnimationFrame(() => {
        studioPanelRef.current?.expand();
      });
    }

    hadWorkspaceShellRef.current = true;
  }, [hasWorkspaceShell, syncStudioCollapsedState]);

  useEffect(() => {
    if (!hasWorkspaceShell && mobileTab === "studio") {
      setMobileTab("chat");
    }
  }, [hasWorkspaceShell, mobileTab]);

  const studioPanel = (
    <>
      <div
        className={cn(
          "hidden h-full flex-col items-center justify-start gap-3 px-1 py-3 lg:flex",
          !isStudioCollapsed && "lg:hidden"
        )}
      >
        <button
          type="button"
          onClick={handleToggleStudioPanel}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-[rgba(24,33,38,0.08)] bg-white text-foreground shadow-sm transition-colors hover:bg-[rgba(255,255,255,0.84)]"
          aria-label="Expand context drawer"
          title="Expand context panel"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
      </div>
      <div
        className={cn("flex h-full flex-col", isStudioCollapsed && "lg:hidden")}
      >
        <div className="flex items-start justify-between gap-3 border-b border-[rgba(24,33,38,0.08)] bg-[rgba(255,255,255,0.68)] px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">
              Pinned lab context
            </h2>
            <p className="mt-1 text-[13px] leading-6 text-muted-foreground">
              {hasWorkspaceContent
                ? "Files, plans, evidence, and task context stay here while you iterate in chat."
                : "This panel will appear here after the assistant creates reusable context."}
            </p>
          </div>
          <button
            type="button"
            onClick={handleToggleStudioPanel}
            className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[rgba(24,33,38,0.08)] bg-white text-foreground shadow-sm transition-colors hover:bg-[rgba(255,255,255,0.84)] lg:inline-flex"
            aria-label="Collapse context drawer"
            title="Collapse context panel"
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-3 p-3">
          <ScrollArea className="min-h-0 flex-1">
            <div className="space-y-3 pr-1">
              {showWorkflowModule ? (
                <SectionCard
                  icon={runState.icon}
                  eyebrow="Workflow"
                  title={runState.label}
                  subtitle={runState.description}
                  action={
                    <div className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-3 py-1 text-[11px] font-medium text-foreground">
                      v1
                    </div>
                  }
                  contentClassName="p-4"
                >
                  <div
                    className={cn(
                      "rounded-[18px] border px-4 py-3",
                      runState.accentClass
                    )}
                  >
                    <p className="text-[14px] font-medium">{runState.label}</p>
                    <p className="mt-1 text-[13px] leading-6 opacity-90">
                      Resume the interrupt or answer the active parameter request
                      to continue the run.
                    </p>
                  </div>
                </SectionCard>
              ) : null}

              {showDataModule ? (
                <SectionCard
                  icon={Files}
                  eyebrow="Data Review"
                  title={
                    latestDataArtifact
                      ? latestDataArtifact.title
                      : "Battery datasets are attached"
                  }
                  subtitle={
                    latestDataArtifact
                      ? "The latest normalized dataset or cycle summary is ready for inspection."
                      : "Raw spreadsheet or cycler sources are present. Ask chat to inspect or normalize them to populate the downstream panels."
                  }
                  action={
                    <div className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-3 py-1 text-[11px] font-medium text-foreground">
                      v1
                    </div>
                  }
                  contentClassName="p-4"
                >
                  <div className="rounded-[18px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.82)] px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      Current data context
                    </p>
                    <p className="mt-2 text-[14px] leading-6 text-foreground">
                      {latestDataArtifact
                        ? `Open ${latestDataArtifact.title} to inspect normalized columns, preview rows, or exported summaries.`
                        : `${dataSourceEntries.length} data source${dataSourceEntries.length === 1 ? "" : "s"} attached and waiting for inspection.`}
                    </p>
                    {(latestDataArtifact || dataSourceEntries[0]) && (
                      <button
                        type="button"
                        onClick={() =>
                          handleOpenEntry(latestDataArtifact ?? dataSourceEntries[0])
                        }
                        className="mt-3 inline-flex items-center gap-2 rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-3 py-1.5 text-[12px] font-medium text-foreground transition-colors hover:bg-[rgba(255,255,255,0.84)]"
                      >
                        Open {latestDataArtifact ? "latest dataset" : "latest source"}
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </SectionCard>
              ) : null}

              {showPlanningModule ? (
                <SectionCard
                  icon={Sparkles}
                  eyebrow="Planning"
                  title={
                    latestPlanArtifact
                      ? latestPlanArtifact.title
                      : "Planning sources are ready"
                  }
                  subtitle={
                    latestPlanArtifact
                      ? "A draft experiment plan is available to refine, export, or compare."
                      : "Datasheets or supporting planning sources are attached, so chat can draft a protocol around them."
                  }
                  action={
                    <div className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-3 py-1 text-[11px] font-medium text-foreground">
                      v1
                    </div>
                  }
                  contentClassName="p-4"
                >
                  <div className="rounded-[18px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.82)] px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      Planning focus
                    </p>
                    <p className="mt-2 text-[14px] leading-6 text-foreground">
                      {latestPlanArtifact
                        ? `Keep iterating in chat and use this panel to reopen ${latestPlanArtifact.title} whenever you need the latest draft.`
                        : `${documentSourceEntries.length} planning source${documentSourceEntries.length === 1 ? "" : "s"} available for protocol drafting and evidence-backed test design.`}
                    </p>
                    {(latestPlanArtifact || documentSourceEntries[0]) && (
                      <button
                        type="button"
                        onClick={() =>
                          handleOpenEntry(
                            latestPlanArtifact ?? documentSourceEntries[0]
                          )
                        }
                        className="mt-3 inline-flex items-center gap-2 rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-3 py-1.5 text-[12px] font-medium text-foreground transition-colors hover:bg-[rgba(255,255,255,0.84)]"
                      >
                        Open {latestPlanArtifact ? "current plan" : "latest planning source"}
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </SectionCard>
              ) : null}

              {showEvidenceModule ? (
                <SectionCard
                  icon={FileText}
                  eyebrow="Evidence"
                  title={
                    latestEvidenceArtifact?.title ?? "Reference evidence is available"
                  }
                  subtitle="Summaries and exports that support planning decisions stay grouped here."
                  action={
                    <div className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-3 py-1 text-[11px] font-medium text-foreground">
                      v1
                    </div>
                  }
                  contentClassName="p-4"
                >
                  <div className="space-y-2">
                    {evidenceArtifacts.slice(0, 3).map((entry) => (
                      <button
                        key={entry.path}
                        type="button"
                        onClick={() => handleOpenEntry(entry)}
                        className="flex w-full items-start justify-between gap-3 rounded-[16px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.82)] px-4 py-3 text-left transition-colors hover:bg-white"
                      >
                        <div className="min-w-0">
                          <p className="text-[13px] font-medium text-foreground">
                            {entry.title}
                          </p>
                          <p className="mt-1 text-[12px] leading-5 text-muted-foreground">
                            {entry.badge}
                          </p>
                        </div>
                        <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      </button>
                    ))}
                  </div>
                </SectionCard>
              ) : null}

              {showArtifactShelf ? (
                <SectionCard
                  icon={FileText}
                  eyebrow="Artifact Shelf"
                  title="Generated outputs"
                  subtitle="Open the latest files without digging through the conversation."
                  action={
                    <div className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-3 py-1 text-[11px] font-medium text-foreground">
                      v1
                    </div>
                  }
                  className="min-h-0"
                  contentClassName="min-h-0"
                >
                  <FileList
                    entries={artifactEntries}
                    emptyLabel="No generated artifacts yet. Ask for a plan, inspect a dataset, or export a report to populate Studio."
                    tone="artifact"
                    onOpen={handleOpenEntry}
                  />
                </SectionCard>
              ) : null}

              {showTaskBoard ? (
                <SectionCard
                  icon={Activity}
                  eyebrow="Task Board"
                  title="What the agent is tracking"
                  subtitle="Live steps remain pinned here during multi-stage planning and data workflows."
                  action={
                    <div className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-3 py-1 text-[11px] font-medium text-foreground">
                      v1
                    </div>
                  }
                  contentClassName="min-h-0"
                >
                  <div className="space-y-3 p-4">
                    {todos.map((todo, index) => (
                      <div
                        key={`${todo.id}-${index}`}
                        className="flex items-start gap-3 rounded-[16px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.88)] px-4 py-3"
                      >
                        {getTodoStatusIcon(todo.status)}
                        <div className="min-w-0">
                          <p className="text-[13px] leading-6 text-foreground">
                            {todo.content}
                          </p>
                          <p className="mt-1 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                            {todo.status.replace("_", " ")}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              ) : null}
              {showSourcesModule ? (
                <SectionCard
                  icon={Files}
                  eyebrow="Sources"
                  title="Source library"
                  subtitle={`${sourceEntries.length} source${sourceEntries.length === 1 ? "" : "s"} attached for this thread.`}
                  className="min-h-0"
                  contentClassName="min-h-0"
                >
                  <FileList
                    entries={sourceEntries}
                    emptyLabel="No sources yet."
                    tone="source"
                    onOpen={handleOpenEntry}
                  />
                </SectionCard>
              ) : null}
            </div>
          </ScrollArea>
        </div>
      </div>
    </>
  );

  const mobileTabs: Array<{ id: NotebookTab; label: string; icon: LucideIcon }> = [
    { id: "sources", label: "History", icon: FolderOpen },
    { id: "chat", label: "Chat", icon: MessageSquare },
    ...(hasWorkspaceShell
      ? [{ id: "studio" as NotebookTab, label: "Workspace", icon: Sparkles }]
      : []),
  ];

  return (
    <>
      <div className="hidden h-full lg:flex lg:flex-row">
        {!sourcesPanelOpen ? collapsedSourcesRail : null}
        <ResizablePanelGroup
          direction="horizontal"
          autoSaveId="notebook-workspace"
          className="min-w-0 flex-1"
        >
          {sourcesPanelOpen ? (
            <>
              <ResizablePanel
                id="sources"
                order={1}
                defaultSize={22}
                minSize={17}
                maxSize={28}
                className="min-w-[240px] p-2"
              >
                {sourcesPanel}
              </ResizablePanel>
              <ResizableHandle className="bg-transparent" />
            </>
          ) : null}

          <ResizablePanel
            id="chat"
            order={2}
            defaultSize={
              sourcesPanelOpen ? 45 : hasWorkspaceShell ? 64 : 94
            }
            minSize={36}
            className="min-w-[420px] bg-[rgba(255,255,255,0.38)]"
          >
            {chatPanel}
          </ResizablePanel>

          {hasWorkspaceShell ? (
            <>
              <ResizableHandle className="bg-transparent" />
              <ResizablePanel
                ref={studioPanelRef}
                id="studio"
                order={3}
                defaultSize={30}
                minSize={22}
                maxSize={38}
                collapsible
                collapsedSize={3}
                onCollapse={() => syncStudioCollapsedState(true)}
                onExpand={() => syncStudioCollapsedState(false)}
                className={cn(
                  "studio-panel-enter border-l border-[rgba(24,33,38,0.08)] bg-[linear-gradient(180deg,rgba(246,248,252,0.92),rgba(240,244,249,0.96))]",
                  isStudioCollapsed ? "min-w-[44px]" : "min-w-[320px]"
                )}
              >
                {studioPanel}
              </ResizablePanel>
            </>
          ) : null}
        </ResizablePanelGroup>
      </div>

      <div className="flex min-h-0 flex-1 flex-col lg:hidden">
        <div className="border-b border-[rgba(24,33,38,0.08)] bg-[rgba(255,255,255,0.78)] px-4 py-3">
          <div className="flex flex-wrap gap-2">
            {mobileTabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setMobileTab(id)}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm transition-colors",
                  mobileTab === id
                    ? "border-[rgba(17,92,73,0.16)] bg-[rgba(232,242,239,0.9)] text-[rgba(17,92,73,0.96)]"
                    : "border-[rgba(24,33,38,0.08)] bg-white text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="relative flex min-h-0 flex-1 flex-col">
          {mobileTab === "sources"
            ? sourcesPanel
            : mobileTab === "studio" && hasWorkspaceShell
              ? studioPanel
              : chatPanel}
        </div>
      </div>

      {selectedFile ? (
        <FileViewDialog
          file={selectedFile}
          onSaveFile={handleSaveFile}
          onClose={() => setSelectedFile(null)}
          editDisabled={isLoading || interrupt !== undefined}
        />
      ) : null}
    </>
  );
}
