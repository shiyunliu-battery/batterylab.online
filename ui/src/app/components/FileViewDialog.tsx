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
  Copy,
  Download,
  Edit,
  Save,
  X,
  Loader2,
  ChevronDown,
} from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { toast } from "sonner";
import { MarkdownContent } from "@/app/components/MarkdownContent";
import type { FileItem } from "@/app/types/types";
import { stripExperimentPlanTitleHeadingForPreview } from "@/app/lib/experimentPlan";

type ExportFormat = "md" | "tex" | "pdf";

type PreviewErrorBoundaryProps = {
  resetKey: string;
  fallbackContent: string;
  children: React.ReactNode;
};

type PreviewErrorBoundaryState = {
  hasError: boolean;
};

const LANGUAGE_MAP: Record<string, string> = {
  js: "javascript",
  jsx: "javascript",
  ts: "typescript",
  tsx: "typescript",
  py: "python",
  rb: "ruby",
  go: "go",
  rs: "rust",
  java: "java",
  cpp: "cpp",
  c: "c",
  cs: "csharp",
  php: "php",
  swift: "swift",
  kt: "kotlin",
  scala: "scala",
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  json: "json",
  xml: "xml",
  html: "html",
  css: "css",
  scss: "scss",
  sass: "sass",
  less: "less",
  sql: "sql",
  yaml: "yaml",
  yml: "yaml",
  toml: "toml",
  ini: "ini",
  dockerfile: "dockerfile",
  makefile: "makefile",
};

const DELIMITED_FILE_EXTENSIONS = new Set(["csv", "tsv"]);
const DELIMITED_PREVIEW_ROW_LIMIT = 200;

type DelimitedPreview = {
  headers: string[];
  rows: string[][];
  totalRowCount: number;
  totalColumnCount: number;
  truncated: boolean;
};

function getDownloadMimeType(fileName: string): string {
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
    case "html":
    case "htm":
      return "text/html;charset=utf-8";
    case "xml":
      return "application/xml;charset=utf-8";
    default:
      return "text/plain;charset=utf-8";
  }
}

function getDownloadFileName(fileName: string, displayName?: string): string {
  const normalizedPath = String(fileName || "").replace(/\\/g, "/");
  const segments = normalizedPath.split("/").filter(Boolean);
  const fallbackName = segments[segments.length - 1] || "file.txt";
  const cleanDisplayName = String(displayName || "").trim();
  if (cleanDisplayName) {
    if (cleanDisplayName.includes(".")) {
      return cleanDisplayName;
    }

    const lastDotIndex = fallbackName.lastIndexOf(".");
    const fallbackExtension =
      lastDotIndex > 0 ? fallbackName.slice(lastDotIndex) : "";
    return fallbackExtension
      ? `${cleanDisplayName}${fallbackExtension}`
      : cleanDisplayName;
  }

  return fallbackName;
}

function parseDelimitedText(content: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentCell = "";
  let inQuotes = false;

  const pushCell = () => {
    currentRow.push(currentCell);
    currentCell = "";
  };

  const pushRow = () => {
    pushCell();
    if (currentRow.length > 1 || currentRow[0] !== "") {
      rows.push(currentRow);
    }
    currentRow = [];
  };

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index];
    const nextCharacter = content[index + 1];

    if (inQuotes) {
      if (character === '"') {
        if (nextCharacter === '"') {
          currentCell += '"';
          index += 1;
        } else {
          inQuotes = false;
        }
      } else {
        currentCell += character;
      }
      continue;
    }

    if (character === '"') {
      inQuotes = true;
      continue;
    }

    if (character === delimiter) {
      pushCell();
      continue;
    }

    if (character === "\r") {
      if (nextCharacter === "\n") {
        index += 1;
      }
      pushRow();
      continue;
    }

    if (character === "\n") {
      pushRow();
      continue;
    }

    currentCell += character;
  }

  if (currentCell !== "" || currentRow.length > 0) {
    pushRow();
  }

  return rows;
}

function buildDelimitedPreview(
  content: string,
  fileExtension: string
): DelimitedPreview | null {
  const delimiter = fileExtension === "tsv" ? "\t" : ",";
  const parsedRows = parseDelimitedText(content, delimiter);
  if (parsedRows.length === 0) {
    return null;
  }

  const totalRowCount = parsedRows.length;
  const [rawHeaders, ...bodyRows] = parsedRows;
  const headers = rawHeaders.map((header, index) => {
    const trimmed = String(header || "").trim();
    return trimmed || `Column ${index + 1}`;
  });
  const limitedBodyRows = bodyRows
    .slice(0, DELIMITED_PREVIEW_ROW_LIMIT)
    .map((row) =>
      headers.map((_, index) => String(row[index] ?? ""))
    );

  return {
    headers,
    rows: limitedBodyRows,
    totalRowCount: Math.max(totalRowCount - 1, 0),
    totalColumnCount: headers.length,
    truncated: bodyRows.length > DELIMITED_PREVIEW_ROW_LIMIT,
  };
}

class PreviewErrorBoundary extends React.Component<
  PreviewErrorBoundaryProps,
  PreviewErrorBoundaryState
> {
  constructor(props: PreviewErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): PreviewErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("File preview failed:", error);
  }

  componentDidUpdate(prevProps: PreviewErrorBoundaryProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Preview rendering failed for this file. Showing plain text instead.
          </p>
          <pre className="max-h-[60vh] overflow-auto rounded-md border border-border bg-[rgba(247,245,241,0.92)] p-4 text-xs leading-6 text-foreground">
            {this.props.fallbackContent}
          </pre>
        </div>
      );
    }

    return this.props.children;
  }
}

export const FileViewDialog = React.memo<{
  file: FileItem | null;
  onSaveFile: (fileName: string, content: string) => Promise<void>;
  onClose: () => void;
  editDisabled: boolean;
}>(({ file, onSaveFile, onClose, editDisabled }) => {
  const [isEditingMode, setIsEditingMode] = useState(file === null);
  const [fileName, setFileName] = useState(String(file?.path || ""));
  const [fileContent, setFileContent] = useState(String(file?.content || ""));
  const [downloadMenuOpen, setDownloadMenuOpen] = useState(false);
  const [isStructuredExporting, setIsStructuredExporting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const downloadMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setFileName(String(file?.path || ""));
    setFileContent(String(file?.content || ""));
    setIsEditingMode(file === null);
    setDownloadMenuOpen(false);
    setIsSaving(false);
  }, [file]);

  const fileExtension = useMemo(() => {
    const fileNameStr = String(fileName || "");
    return fileNameStr.split(".").pop()?.toLowerCase() || "";
  }, [fileName]);

  const isMarkdown = useMemo(() => {
    return fileExtension === "md" || fileExtension === "markdown";
  }, [fileExtension]);

  const isDelimitedText = useMemo(() => {
    return DELIMITED_FILE_EXTENSIONS.has(fileExtension);
  }, [fileExtension]);

  const language = useMemo(() => {
    return LANGUAGE_MAP[fileExtension] || "text";
  }, [fileExtension]);

  const isGeneratedCleanPlan = useMemo(() => {
    const normalizedPath = String(fileName || "");
    if (normalizedPath.startsWith("/uploads/")) {
      return false;
    }

    return (
      file?.generatedFileKind === "clean_experiment_plan" ||
      file?.generatedFileKind === "cell_background_summary" ||
      normalizedPath.startsWith("/plans/")
    );
  }, [file?.generatedFileKind, fileName]);

  const previewContent = useMemo(() => {
    if (!isGeneratedCleanPlan) {
      return fileContent;
    }
    return stripExperimentPlanTitleHeadingForPreview(fileContent);
  }, [fileContent, isGeneratedCleanPlan]);

  const delimitedPreview = useMemo(() => {
    if (!isDelimitedText) {
      return null;
    }
    return buildDelimitedPreview(previewContent, fileExtension);
  }, [fileExtension, isDelimitedText, previewContent]);

  useEffect(() => {
    if (!downloadMenuOpen) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (
        downloadMenuRef.current &&
        !downloadMenuRef.current.contains(event.target as Node)
      ) {
        setDownloadMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [downloadMenuOpen]);

  const handleCopy = useCallback(() => {
    if (fileContent) {
      navigator.clipboard.writeText(fileContent);
    }
  }, [fileContent]);

  const handleDownload = useCallback(() => {
    if (fileContent && fileName) {
      const blob = new Blob([fileContent], {
        type: getDownloadMimeType(fileName),
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = getDownloadFileName(fileName, file?.displayName);
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  }, [file?.displayName, fileContent, fileName]);

  const handleStructuredDownload = useCallback(
    async (format: ExportFormat) => {
      if (!fileContent || !fileName) {
        return;
      }

      setIsStructuredExporting(true);
      setDownloadMenuOpen(false);

      try {
        const response = await fetch("/api/documents/export", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            content: fileContent,
            fileName,
            format,
          }),
        });

        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as
            | { error?: string }
            | null;
          throw new Error(
            payload?.error || `Failed to export ${format.toUpperCase()}.`
          );
        }

        const blob = await response.blob();
        const disposition = response.headers.get("Content-Disposition") || "";
        const matchedFileName = disposition.match(/filename="?([^"]+)"?/i)?.[1];
        const downloadName =
          matchedFileName ||
          `${String(fileName).replace(/\.[^.]+$/, "")}.${format}`;

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = downloadName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : `Failed to export ${format}.`
        );
      } finally {
        setIsStructuredExporting(false);
      }
    },
    [fileContent, fileName]
  );

  const handleEdit = useCallback(() => {
    setIsEditingMode(true);
  }, []);

  const handleCancel = useCallback(() => {
    if (file === null) {
      onClose();
    } else {
      setFileName(String(file.path));
      setFileContent(String(file.content));
      setIsEditingMode(false);
    }
  }, [file, onClose]);

  const fileNameIsValid = useMemo(() => {
    if (file !== null) {
      return fileName.trim() !== "";
    }

    return (
      fileName.trim() !== "" &&
      !fileName.includes("/") &&
      !fileName.includes(" ")
    );
  }, [file, fileName]);

  const handleSave = useCallback(async () => {
    if (!fileName.trim() || !fileContent.trim() || !fileNameIsValid || isSaving) {
      return;
    }

    setIsSaving(true);
    try {
      await onSaveFile(fileName, fileContent);
      setIsEditingMode(false);
    } catch (error) {
      toast.error(`Failed to save file: ${error}`);
    } finally {
      setIsSaving(false);
    }
  }, [fileContent, fileName, fileNameIsValid, isSaving, onSaveFile]);

  return (
    <Dialog
      open={true}
      onOpenChange={onClose}
    >
      <DialogContent className="flex h-[80vh] max-h-[80vh] min-w-[60vw] flex-col p-6">
        <DialogTitle className="sr-only">
          {file?.displayName || file?.path || "New File"}
        </DialogTitle>
        <div className="mb-4 flex items-center justify-between border-b border-border pb-4">
          <div className="flex min-w-0 items-center gap-2">
            <FileText className="text-primary/50 h-5 w-5 shrink-0" />
            {isEditingMode && file === null ? (
              <Input
                value={fileName}
                onChange={(e) => setFileName(e.target.value)}
                placeholder="Enter filename..."
                className="text-base font-medium"
                aria-invalid={!fileNameIsValid}
              />
            ) : (
              <span className="overflow-hidden text-ellipsis whitespace-nowrap text-base font-medium text-primary">
                {file?.displayName || file?.path}
              </span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {!isEditingMode && (
              <>
                <Button
                  onClick={handleEdit}
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2"
                  disabled={editDisabled}
                >
                  <Edit
                    size={16}
                    className="mr-1"
                  />
                  Edit
                </Button>
                <Button
                  onClick={handleCopy}
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2"
                >
                  <Copy
                    size={16}
                    className="mr-1"
                  />
                  Copy
                </Button>
                {isGeneratedCleanPlan ? (
                  <div
                    ref={downloadMenuRef}
                    className="relative"
                  >
                    <Button
                      onClick={() => setDownloadMenuOpen((prev) => !prev)}
                      variant="ghost"
                      size="sm"
                      className="h-8 px-2"
                      disabled={isStructuredExporting}
                    >
                      {isStructuredExporting ? (
                        <Loader2
                          size={16}
                          className="mr-1 animate-spin"
                        />
                      ) : (
                        <Download
                          size={16}
                          className="mr-1"
                        />
                      )}
                      Download
                      <ChevronDown
                        size={14}
                        className="ml-1"
                      />
                    </Button>
                    {downloadMenuOpen && (
                      <div className="absolute right-0 z-20 mt-1 min-w-[132px] overflow-hidden rounded-[12px] border border-[rgba(24,33,38,0.08)] bg-white shadow-lg">
                        {([
                          ["pdf", "PDF"],
                          ["md", "MD"],
                        ] as Array<[ExportFormat, string]>).map(
                          ([format, label]) => (
                            <button
                              key={format}
                              type="button"
                              onClick={() => void handleStructuredDownload(format)}
                              className="block w-full px-3 py-2 text-left text-xs text-foreground transition-colors hover:bg-[rgba(247,245,241,0.8)]"
                            >
                              {label}
                            </button>
                          )
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <Button
                    onClick={handleDownload}
                    variant="ghost"
                    size="sm"
                    className="h-8 px-2"
                  >
                    <Download
                      size={16}
                      className="mr-1"
                    />
                    Download
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">
          {isEditingMode ? (
            <Textarea
              value={fileContent}
              onChange={(e) => setFileContent(e.target.value)}
              placeholder="Enter file content..."
              className="h-full min-h-[400px] resize-none font-mono text-sm"
            />
          ) : (
            <ScrollArea className="bg-surface h-full rounded-md">
              <div className="p-4">
                <PreviewErrorBoundary
                  resetKey={`${fileName}:${fileContent.length}`}
                  fallbackContent={previewContent}
                >
                  {previewContent ? (
                    isMarkdown ? (
                      <div className="rounded-md p-6">
                        <MarkdownContent
                          content={previewContent}
                          enableMath={!isGeneratedCleanPlan}
                        />
                      </div>
                    ) : delimitedPreview ? (
                      <div className="space-y-3 rounded-md p-2">
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-2 text-xs text-muted-foreground">
                          <span>
                            {fileExtension.toUpperCase()} preview
                          </span>
                          <span>
                            Rows: {delimitedPreview.totalRowCount}
                          </span>
                          <span>
                            Columns: {delimitedPreview.totalColumnCount}
                          </span>
                          {delimitedPreview.truncated && (
                            <span>
                              Showing first {DELIMITED_PREVIEW_ROW_LIMIT} rows
                            </span>
                          )}
                        </div>
                        <div className="overflow-auto rounded-md border border-[rgba(24,33,38,0.08)] bg-white">
                          <table className="min-w-full border-collapse text-left text-xs text-foreground">
                            <thead className="sticky top-0 z-10 bg-[rgba(247,245,241,0.98)]">
                              <tr>
                                {delimitedPreview.headers.map((header, headerIndex) => (
                                  <th
                                    key={`${headerIndex}-${header}`}
                                    className="border-b border-r border-[rgba(24,33,38,0.08)] px-3 py-2 font-medium last:border-r-0"
                                  >
                                    {header}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {delimitedPreview.rows.map((row, rowIndex) => (
                                <tr
                                  key={`${rowIndex}-${row[0] || "row"}`}
                                  className="odd:bg-[rgba(250,249,246,0.65)]"
                                >
                                  {row.map((cell, cellIndex) => (
                                    <td
                                      key={`${rowIndex}-${cellIndex}`}
                                      className="border-b border-r border-[rgba(24,33,38,0.08)] px-3 py-2 align-top last:border-r-0"
                                    >
                                      {cell || <span className="text-muted-foreground"> </span>}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : (
                      <SyntaxHighlighter
                        language={language}
                        style={oneDark}
                        customStyle={{
                          margin: 0,
                          borderRadius: "0.5rem",
                          fontSize: "0.875rem",
                        }}
                        showLineNumbers
                        wrapLines={true}
                        lineProps={{
                          style: {
                            whiteSpace: "pre-wrap",
                          },
                        }}
                      >
                        {previewContent}
                      </SyntaxHighlighter>
                    )
                  ) : (
                    <div className="flex items-center justify-center p-12">
                      <p className="text-sm text-muted-foreground">
                        File is empty
                      </p>
                    </div>
                  )}
                </PreviewErrorBoundary>
              </div>
            </ScrollArea>
          )}
        </div>
        {isEditingMode && (
          <div className="mt-4 flex justify-end gap-2 border-t border-border pt-4">
            <Button
              onClick={handleCancel}
              variant="outline"
              size="sm"
            >
              <X
                size={16}
                className="mr-1"
              />
              Cancel
            </Button>
            <Button
              onClick={() => void handleSave()}
              size="sm"
              disabled={
                isSaving ||
                !fileName.trim() ||
                !fileContent.trim() ||
                !fileNameIsValid
              }
            >
              {isSaving ? (
                <Loader2
                  size={16}
                  className="mr-1 animate-spin"
                />
              ) : (
                <Save
                  size={16}
                  className="mr-1"
                />
              )}
              Save
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
});

FileViewDialog.displayName = "FileViewDialog";
