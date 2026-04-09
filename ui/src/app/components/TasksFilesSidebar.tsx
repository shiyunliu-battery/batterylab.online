"use client";

import React, {
  useMemo,
  useCallback,
  useState,
  useEffect,
  useRef,
} from "react";
import {
  FileText,
  CheckCircle,
  Circle,
  Clock,
  ChevronDown,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { TodoItem, FileItem } from "@/app/types/types";
import { useChatContext } from "@/providers/ChatProvider";
import { cn } from "@/lib/utils";
import { FileViewDialog } from "@/app/components/FileViewDialog";
import { stripExperimentPlanTitleHeadingForPreview } from "@/app/lib/experimentPlan";
import {
  createChatFileData,
  getChatFileContent,
  getChatFileDisplayName,
  getVisibleChatFiles,
  type ChatFileRecord,
  type ChatFileUpdate,
} from "@/app/lib/chatFiles";

function getFileDownloadMimeType(fileName: string): string {
  const extension = String(fileName || "")
    .split(".")
    .pop()
    ?.toLowerCase();

  switch (extension) {
    case "csv":
      return "text/csv;charset=utf-8";
    case "tsv":
      return "text/tab-separated-values;charset=utf-8";
    case "json":
      return "application/json;charset=utf-8";
    case "md":
    case "markdown":
      return "text/markdown;charset=utf-8";
    default:
      return "text/plain;charset=utf-8";
  }
}

type FileDialogBoundaryProps = {
  file: FileItem;
  onClose: () => void;
  onSaveFile: (fileName: string, content: string) => Promise<void>;
  editDisabled: boolean;
  children: React.ReactNode;
};

type FileDialogBoundaryState = {
  hasError: boolean;
  isEditing: boolean;
  draftPath: string;
  draftContent: string;
  isSaving: boolean;
};

class FileDialogBoundary extends React.Component<
  FileDialogBoundaryProps,
  FileDialogBoundaryState
> {
  constructor(props: FileDialogBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      isEditing: false,
      draftPath: props.file.path,
      draftContent: String(props.file.content || ""),
      isSaving: false,
    };
  }

  static getDerivedStateFromError(
    _error: unknown,
    prevState: FileDialogBoundaryState
  ): FileDialogBoundaryState {
    return { ...prevState, hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("File dialog rendering failed:", error);
  }

  componentDidUpdate(prevProps: FileDialogBoundaryProps) {
    if (
      prevProps.file.path !== this.props.file.path &&
      this.state.hasError
    ) {
      this.setState({
        hasError: false,
        isEditing: false,
        draftPath: this.props.file.path,
        draftContent: String(this.props.file.content || ""),
        isSaving: false,
      });
    }
  }

  private handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(this.getRenderableContent());
    } catch (error) {
      console.error("Failed to copy fallback file content:", error);
    }
  };

  private isExperimentPlanFile(): boolean {
    return (
      this.props.file.generatedFileKind === "clean_experiment_plan" ||
      this.props.file.generatedFileKind === "cell_background_summary" ||
      this.state.draftPath.startsWith("/plans/")
    );
  }

  private getRenderableContent(): string {
    return this.isExperimentPlanFile()
      ? stripExperimentPlanTitleHeadingForPreview(this.state.draftContent)
      : this.state.draftContent;
  }

  private handleDownload = () => {
    const fileName =
      this.props.file.displayName || this.state.draftPath.split("/").pop() || "file.txt";
    const blob = new Blob([this.state.draftContent], {
      type: getFileDownloadMimeType(fileName),
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  private handleEdit = () => {
    if (this.props.editDisabled) {
      return;
    }
    this.setState({ isEditing: true });
  };

  private handleCancelEdit = () => {
    this.setState({
      isEditing: false,
      draftPath: this.props.file.path,
      draftContent: String(this.props.file.content || ""),
    });
  };

  private handleSave = async () => {
    if (
      this.state.isSaving ||
      !this.state.draftPath.trim() ||
      !this.state.draftContent.trim()
    ) {
      return;
    }

    this.setState({ isSaving: true });
    try {
      await this.props.onSaveFile(this.state.draftPath, this.state.draftContent);
      this.setState({ isEditing: false, hasError: false, isSaving: false });
    } catch (error) {
      console.error("Failed to save fallback file content:", error);
      this.setState({ isSaving: false });
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6">
          <div className="flex max-h-[80vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-border bg-white shadow-xl">
            <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground">
                  {this.props.file.displayName || this.props.file.path}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Rich preview failed for this file, so it is shown in a safe text editor.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {!this.state.isEditing && (
                  <button
                    type="button"
                    onClick={this.handleEdit}
                    disabled={this.props.editDisabled}
                    className="rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Edit
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void this.handleCopy()}
                  className="rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  Copy
                </button>
                <button
                  type="button"
                  onClick={this.handleDownload}
                  className="rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  Download
                </button>
                {this.state.isEditing && (
                  <button
                    type="button"
                    onClick={() => void this.handleSave()}
                    disabled={this.state.isSaving}
                    className="rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {this.state.isSaving ? "Saving..." : "Save"}
                  </button>
                )}
                {this.state.isEditing && (
                  <button
                    type="button"
                    onClick={this.handleCancelEdit}
                    className="rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    Cancel
                  </button>
                )}
                <button
                  type="button"
                  onClick={this.props.onClose}
                  className="rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  Close
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-auto p-5">
              {this.state.isEditing ? (
                <textarea
                  value={this.state.draftContent}
                  onChange={(event) =>
                    this.setState({ draftContent: event.target.value })
                  }
                  className="min-h-[60vh] w-full resize-none rounded-md border border-border bg-white p-4 font-mono text-xs leading-6 text-foreground outline-none"
                />
              ) : (
                <pre className="whitespace-pre-wrap break-words rounded-md border border-border bg-[rgba(247,245,241,0.92)] p-4 text-xs leading-6 text-foreground">
                  {this.getRenderableContent()}
                </pre>
              )}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

function FilesPopoverInner({
  files,
  setFiles,
  editDisabled,
}: {
  files: ChatFileRecord;
  setFiles: (files: ChatFileUpdate) => Promise<void>;
  editDisabled: boolean;
}) {
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const visibleFiles = useMemo(() => getVisibleChatFiles(files), [files]);

  const getGeneratedFileKind = useCallback(
    (filePath: string): string | undefined => {
      const fileValue = visibleFiles[filePath];
      return fileValue &&
        typeof fileValue === "object" &&
        typeof fileValue.generated_file_kind === "string"
        ? fileValue.generated_file_kind
        : undefined;
    },
    [visibleFiles]
  );
  const filePaths = useMemo(() => {
    return Object.keys(visibleFiles).sort((leftPath, rightPath) => {
      const leftValue = visibleFiles[leftPath];
      const rightValue = visibleFiles[rightPath];
      const leftKind =
        leftValue && typeof leftValue === "object"
          ? leftValue.generated_file_kind
          : undefined;
      const rightKind =
        rightValue && typeof rightValue === "object"
          ? rightValue.generated_file_kind
          : undefined;

      if (
        leftKind === "cell_background_summary" &&
        rightKind !== "cell_background_summary"
      ) {
        return -1;
      }
      if (
        rightKind === "cell_background_summary" &&
        leftKind !== "cell_background_summary"
      ) {
        return 1;
      }

      if (
        leftKind === "clean_experiment_plan" &&
        rightKind !== "clean_experiment_plan"
      ) {
        return -1;
      }
      if (
        rightKind === "clean_experiment_plan" &&
        leftKind !== "clean_experiment_plan"
      ) {
        return 1;
      }

      if (
        leftKind === "parsed_cycler_summary" &&
        rightKind !== "parsed_cycler_summary"
      ) {
        return -1;
      }
      if (
        rightKind === "parsed_cycler_summary" &&
        leftKind !== "parsed_cycler_summary"
      ) {
        return 1;
      }

      if (
        leftKind === "parsed_cycler_dataset" &&
        !["parsed_cycler_dataset", "parsed_cycler_summary"].includes(
          String(rightKind || "")
        )
      ) {
        return -1;
      }
      if (
        rightKind === "parsed_cycler_dataset" &&
        !["parsed_cycler_dataset", "parsed_cycler_summary"].includes(
          String(leftKind || "")
        )
      ) {
        return 1;
      }

      if (
        leftKind === "parsed_cycler_preview" &&
        ![
          "parsed_cycler_preview",
          "parsed_cycler_dataset",
          "parsed_cycler_summary",
        ].includes(
          String(rightKind || "")
        )
      ) {
        return -1;
      }
      if (
        rightKind === "parsed_cycler_preview" &&
        ![
          "parsed_cycler_preview",
          "parsed_cycler_dataset",
          "parsed_cycler_summary",
        ].includes(
          String(leftKind || "")
        )
      ) {
        return 1;
      }

      return leftPath.localeCompare(rightPath);
    });
  }, [visibleFiles]);

  const handleSaveFile = useCallback(
    async (fileName: string, content: string) => {
      const existingFile = files[fileName];
      const existingCreatedAt =
        existingFile &&
        typeof existingFile === "object" &&
        "created_at" in existingFile &&
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

      await setFiles((currentFiles) => ({
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

  return (
    <>
      {filePaths.length === 0 ? (
        <div className="flex h-full items-center justify-center p-4 text-center">
          <p className="text-xs text-muted-foreground">No files created yet</p>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(256px,1fr))] gap-2">
          {filePaths.map((filePath) => {
            return (
              <button
                key={filePath}
                type="button"
                onClick={() =>
                  setSelectedFile({
                    path: filePath,
                    content: getChatFileContent(visibleFiles[filePath]),
                    generatedFileKind: getGeneratedFileKind(filePath),
                    displayName: getChatFileDisplayName(
                      filePath,
                      visibleFiles[filePath]
                    ),
                  })
                }
                className="cursor-pointer space-y-1 truncate rounded-md border border-border px-2 py-3 shadow-sm transition-colors"
                style={{
                  backgroundColor: "var(--color-file-button)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor =
                    "var(--color-file-button-hover)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor =
                    "var(--color-file-button)";
                }}
              >
                <FileText
                  size={24}
                  className="mx-auto text-muted-foreground"
                />
                <span className="mx-auto block w-full truncate break-words text-center text-sm leading-relaxed text-foreground">
                  {getChatFileDisplayName(filePath, visibleFiles[filePath])}
                </span>
                {getChatFileDisplayName(filePath, visibleFiles[filePath]) !==
                  filePath && (
                  <span className="mx-auto block w-full truncate text-center text-[11px] leading-relaxed text-muted-foreground">
                    {filePath}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {selectedFile && (
        <FileDialogBoundary
          file={selectedFile}
          onClose={() => setSelectedFile(null)}
          onSaveFile={handleSaveFile}
          editDisabled={editDisabled}
        >
          <FileViewDialog
            file={selectedFile}
            onSaveFile={handleSaveFile}
            onClose={() => setSelectedFile(null)}
            editDisabled={editDisabled}
          />
        </FileDialogBoundary>
      )}
    </>
  );
}

export const FilesPopover = React.memo(FilesPopoverInner);

export const TasksFilesSidebar = React.memo<{
  todos: TodoItem[];
  files: ChatFileRecord;
  setFiles: (files: ChatFileUpdate) => Promise<void>;
}>(({ todos, files, setFiles }) => {
  const { isLoading, interrupt } = useChatContext();
  const [tasksOpen, setTasksOpen] = useState(false);
  const [filesOpen, setFilesOpen] = useState(false);

  // Track previous counts to detect when content goes from empty to having items
  const prevTodosCount = useRef(todos.length);
  const visibleFiles = useMemo(() => getVisibleChatFiles(files), [files]);
  const prevFilesCount = useRef(Object.keys(visibleFiles).length);
  const generatedPlanCount = useMemo(
    () =>
      Object.values(visibleFiles).filter(
        (value) =>
          value &&
          typeof value === "object" &&
          (
            value.generated_file_kind === "clean_experiment_plan" ||
            value.generated_file_kind === "cell_background_summary" ||
            value.generated_file_kind === "parsed_cycler_summary" ||
            value.generated_file_kind === "parsed_cycler_dataset" ||
            value.generated_file_kind === "parsed_cycler_preview"
          )
      ).length,
    [visibleFiles]
  );
  const prevGeneratedPlanCount = useRef(generatedPlanCount);

  // Auto-expand when todos go from empty to having content
  useEffect(() => {
    if (prevTodosCount.current === 0 && todos.length > 0) {
      setTasksOpen(true);
    }
    prevTodosCount.current = todos.length;
  }, [todos.length]);

  // Auto-expand when files go from empty to having content
  const filesCount = Object.keys(visibleFiles).length;
  useEffect(() => {
    if (prevFilesCount.current === 0 && filesCount > 0) {
      setFilesOpen(true);
    }
    prevFilesCount.current = filesCount;
  }, [filesCount]);

  useEffect(() => {
    if (prevGeneratedPlanCount.current === 0 && generatedPlanCount > 0) {
      setFilesOpen(true);
    }
    prevGeneratedPlanCount.current = generatedPlanCount;
  }, [generatedPlanCount]);

  const getStatusIcon = useCallback((status: TodoItem["status"]) => {
    switch (status) {
      case "completed":
        return (
          <CheckCircle
            size={12}
            className="text-success/80"
          />
        );
      case "in_progress":
        return (
          <Clock
            size={12}
            className="text-warning/80"
          />
        );
      default:
        return (
          <Circle
            size={10}
            className="text-tertiary/70"
          />
        );
    }
  }, []);

  const groupedTodos = useMemo(() => {
    return {
      pending: todos.filter((t) => t.status === "pending"),
      in_progress: todos.filter((t) => t.status === "in_progress"),
      completed: todos.filter((t) => t.status === "completed"),
    };
  }, [todos]);

  const groupedLabels = {
    pending: "Pending",
    in_progress: "In Progress",
    completed: "Completed",
  };

  return (
    <div className="min-h-0 w-full flex-1">
      <div className="font-inter flex h-full w-full flex-col p-0">
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
          <div className="flex items-center justify-between px-3 pb-1.5 pt-2">
            <span className="text-xs font-semibold tracking-wide text-zinc-600">
              AGENT TASKS
            </span>
            <button
              onClick={() => setTasksOpen((v) => !v)}
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-transform duration-200 hover:bg-muted",
                tasksOpen ? "rotate-180" : "rotate-0"
              )}
              aria-label="Toggle tasks panel"
            >
              <ChevronDown size={14} />
            </button>
          </div>
          {tasksOpen && (
            <div className="bg-muted-secondary rounded-xl px-3 pb-2">
              <ScrollArea className="h-full">
                {todos.length === 0 ? (
                  <div className="flex h-full items-center justify-center p-4 text-center">
                    <p className="text-xs text-muted-foreground">
                      No tasks created yet
                    </p>
                  </div>
                ) : (
                  <div className="ml-1 p-0.5">
                    {Object.entries(groupedTodos).map(([status, todos]) => (
                      <div
                        key={status}
                        className="mb-4"
                      >
                        <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-tertiary">
                          {groupedLabels[status as keyof typeof groupedLabels]}
                        </h3>
                        {todos.map((todo, index) => (
                          <div
                            key={`${status}_${todo.id}_${index}`}
                            className="mb-1.5 flex items-start gap-2 rounded-sm p-1 text-sm"
                          >
                            {getStatusIcon(todo.status)}
                            <span className="flex-1 break-words leading-relaxed text-inherit">
                              {todo.content}
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </div>
          )}

          <div className="flex items-center justify-between px-3 pb-1.5 pt-2">
            <span className="text-xs font-semibold tracking-wide text-zinc-600">
              FILE SYSTEM
            </span>
            <button
              onClick={() => setFilesOpen((v) => !v)}
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-transform duration-200 hover:bg-muted",
                filesOpen ? "rotate-180" : "rotate-0"
              )}
              aria-label="Toggle files panel"
            >
              <ChevronDown size={14} />
            </button>
          </div>
          {filesOpen && (
              <FilesPopover
                files={files}
                setFiles={setFiles}
              editDisabled={isLoading === true || interrupt !== undefined}
            />
          )}
        </div>
      </div>
    </div>
  );
});

TasksFilesSidebar.displayName = "TasksFilesSidebar";
