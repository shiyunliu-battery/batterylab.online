"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  StopCircle,
  Terminal,
} from "lucide-react";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { Button } from "@/components/ui/button";
import { CellCatalogResultPanel } from "@/app/components/CellCatalogResultPanel";
import { MarkdownContent } from "@/app/components/MarkdownContent";
import { ToolApprovalInterrupt } from "@/app/components/ToolApprovalInterrupt";
import {
  ToolExecutionProgress,
  ToolExecutionStep,
} from "@/app/components/ToolExecutionProgress";
import {
  humanizeInternalIdentifier,
  sanitizeAssistantDisplayText,
} from "@/app/utils/utils";
import type {
  ActionRequest,
  ReviewConfig,
  ToolCall,
} from "@/app/types/types";
import { cn } from "@/lib/utils";

interface ToolCallBoxProps {
  toolCall: ToolCall;
  uiComponent?: any;
  stream?: any;
  graphId?: string;
  actionRequest?: ActionRequest;
  reviewConfig?: ReviewConfig;
  onResume?: (value: any) => void;
  isLoading?: boolean;
  entryIndex?: number;
}

interface ToolStepBlueprint {
  id: string;
  label: string;
  description: string;
}

const RAW_PREVIEW_MAX_ITEMS = 24;

function sanitizePayloadForRawPreview(
  value: unknown,
  depth = 0
): unknown {
  if (typeof value === "string") {
    const trimmed = value.trimStart();
    if (trimmed.startsWith("<svg")) {
      return `[inline svg omitted; ${value.length} chars]`;
    }
    return sanitizeAssistantDisplayText(value);
  }

  if (Array.isArray(value)) {
    const sanitizedItems = value
      .slice(0, RAW_PREVIEW_MAX_ITEMS)
      .map((item) => sanitizePayloadForRawPreview(item, depth + 1));

    if (value.length > RAW_PREVIEW_MAX_ITEMS) {
      sanitizedItems.push(
        `[${value.length - RAW_PREVIEW_MAX_ITEMS} more items omitted]`
      );
    }

    return sanitizedItems;
  }

  if (value && typeof value === "object") {
    if (depth > 6) {
      return "[nested object omitted]";
    }

    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, entry]) => {
        if (key === "chart_svg" || key.endsWith("_chart_svg")) {
          return [key, "[inline chart svg omitted; see rendered chart above]"];
        }

        return [
          sanitizeAssistantDisplayText(key),
          sanitizePayloadForRawPreview(entry, depth + 1),
        ];
      })
    );
  }

  return value;
}

function summarizeArgValue(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.slice(0, 3).map((item) => String(item)).join(", ");
  }
  return null;
}

function shouldDisplayArgValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }

  if (typeof value === "string") {
    const trimmed = value.trim().toLowerCase();
    return trimmed.length > 0 && trimmed !== "null" && trimmed !== "undefined";
  }

  if (Array.isArray(value)) {
    return value.length > 0;
  }

  if (typeof value === "object") {
    return Object.keys(value as Record<string, unknown>).length > 0;
  }

  return true;
}

function shouldHideToolArgument(
  toolName: string,
  _key: string,
  _value: unknown
): boolean {
  if (toolName === "export_imported_cell_catalog") {
    return true;
  }

  return false;
}

export function getToolActivityMeta(
  name: string,
  args: Record<string, unknown>
): { title: string; subtitle: string; chips: string[]; steps: ToolStepBlueprint[] } {
  const query = summarizeArgValue(args.query);
  const chemistry = summarizeArgValue(args.chemistry);
  const methodId = summarizeArgValue(args.method_id);
  const objective = summarizeArgValue(args.objective);
  const cellId = summarizeArgValue(args.cell_id);
  const chips = [chemistry, methodId, objective, cellId, query].filter(
    (item): item is string => Boolean(item)
  );

  switch (name) {
    case "load_battery_knowledge":
      return {
        title: "Search battery knowledge",
        subtitle: "Read the controlled knowledge layer before composing the reply.",
        chips,
        steps: [
          {
            id: "resolve-request",
            label: "Resolve request",
            description: "Identify the chemistry or method detail being requested.",
          },
          {
            id: "search-knowledge",
            label: "Search knowledge",
            description: "Read the relevant structured source.",
          },
          {
            id: "attach-result",
            label: "Attach result",
            description: "Send the selected facts back into the thread.",
          },
        ],
      };
    case "list_pdf_test_methods":
      return {
        title: "Browse method library",
        subtitle: "Check the imported standards and available method list.",
        chips,
        steps: [
          {
            id: "open-index",
            label: "Open method index",
            description: "Read the extracted method list.",
          },
          {
            id: "filter-methods",
            label: "Filter methods",
            description: "Match the request to likely methods.",
          },
          {
            id: "attach-shortlist",
            label: "Attach shortlist",
            description: "Return candidate methods to the chat.",
          },
        ],
      };
    case "load_pdf_test_method":
      return {
        title: "Load method details",
        subtitle: "Fetch the selected standard-method chapter and structure.",
        chips,
        steps: [
          {
            id: "resolve-method",
            label: "Resolve method",
            description: "Locate the requested method chapter.",
          },
          {
            id: "load-content",
            label: "Load content",
            description: "Read the method detail and outputs.",
          },
          {
            id: "attach-method",
            label: "Attach method",
            description: "Return the method payload to the thread.",
          },
        ],
      };
    case "search_imported_cell_catalog":
      return {
        title: "Search imported cell catalog",
        subtitle: "Look for matching cells and organize them for planning.",
        chips,
        steps: [
          {
            id: "parse-query",
            label: "Parse query",
            description: "Normalize chemistry and selection hints.",
          },
          {
            id: "search-catalog",
            label: "Search catalog",
            description: "Match imported cell records.",
          },
          {
            id: "group-results",
            label: "Group results",
            description: "Prepare representative cells and manufacturer groups.",
          },
          {
            id: "attach-results",
            label: "Attach result",
            description: "Render the shortlist in the thread.",
          },
        ],
      };
    case "load_imported_cell_record":
      return {
        title: "Load cell record",
        subtitle: "Open a single imported cell record for planning use.",
        chips,
        steps: [
          {
            id: "resolve-record",
            label: "Resolve record",
            description: "Match the selected cell identifier.",
          },
          {
            id: "load-metadata",
            label: "Load metadata",
            description: "Read technical fields for the cell.",
          },
          {
            id: "attach-record",
            label: "Attach record",
            description: "Expose the record to the planner UI.",
          },
        ],
      };
    case "export_imported_cell_catalog":
      return {
        title: "Export cell catalog",
        subtitle: "Prepare a downloadable catalog file from the filtered result set.",
        chips,
        steps: [
          {
            id: "resolve-filter",
            label: "Resolve filter",
            description: "Interpret the requested cell subset and export format.",
          },
          {
            id: "build-file",
            label: "Build file",
            description: "Generate the structured export from the approved catalog.",
          },
          {
            id: "attach-file",
            label: "Attach file",
            description: "Add the export to the thread files panel.",
          },
        ],
      };
    case "design_battery_protocol":
      return {
        title: "Draft protocol",
        subtitle: "Apply method, chemistry, and safety constraints to a protocol draft.",
        chips,
        steps: [
          {
            id: "resolve-objective",
            label: "Resolve objective",
            description: "Map the request to a supported protocol objective.",
          },
          {
            id: "apply-constraints",
            label: "Apply constraints",
            description: "Inject chemistry and safety guardrails.",
          },
          {
            id: "assemble-protocol",
            label: "Assemble draft",
            description: "Build the ordered protocol steps.",
          },
        ],
      };
    case "plan_standard_test":
      return {
        title: "Plan standard test",
        subtitle: "Combine method registry content with chemistry and equipment rules.",
        chips,
        steps: [
          {
            id: "load-method",
            label: "Load method",
            description: "Resolve the selected standard test.",
          },
          {
            id: "apply-rules",
            label: "Apply rules",
            description: "Add chemistry, equipment, and safety constraints.",
          },
          {
            id: "compose-plan",
            label: "Compose plan",
            description: "Build the final structured test plan.",
          },
          {
            id: "attach-plan",
            label: "Attach result",
            description: "Return the plan to the chat.",
          },
        ],
      };
    case "run_cycle_data_analysis":
      return {
        title: "Analyze data",
        subtitle: "Load the file, compute metrics, and attach the summary.",
        chips,
        steps: [
          {
            id: "load-data",
            label: "Load data",
            description: "Read the supplied file and normalize columns.",
          },
          {
            id: "compute-metrics",
            label: "Compute metrics",
            description: "Calculate the battery metrics used in reporting.",
          },
          {
            id: "attach-analysis",
            label: "Attach result",
            description: "Return the analysis payload to the chat.",
          },
        ],
      };
    case "parse_raw_cycler_export":
      return {
        title: "Inspect battery dataset",
        subtitle: "Normalize the upload when possible and fall back to a structured battery-data preview when needed.",
        chips,
        steps: [
          {
            id: "detect-adapter",
            label: "Inspect columns",
            description: "Identify the vendor/export mapping or battery-data structure.",
          },
          {
            id: "normalize-columns",
            label: "Normalize preview",
            description: "Rename, scale, and validate recognized battery-data fields.",
          },
          {
            id: "attach-preview",
            label: "Attach preview",
            description: "Return the normalized preview and generated artifacts.",
          },
        ],
      };
    default:
      return {
        title: humanizeInternalIdentifier(name),
        subtitle: "Execute the tool and return its result.",
        chips,
        steps: [
          {
            id: "execute-tool",
            label: "Execute tool",
            description: "Run the requested tool logic.",
          },
          {
            id: "attach-result",
            label: "Attach result",
            description: "Return the output to the thread.",
          },
        ],
      };
  }
}

function materializeExecutionSteps(
  status: string,
  blueprints: ToolStepBlueprint[]
): ToolExecutionStep[] {
  if (blueprints.length === 0) return [];

  if (status === "completed") {
    return blueprints.map((step) => ({ ...step, status: "completed" }));
  }

  if (status === "error") {
    return blueprints.map((step, index) => ({
      ...step,
      status:
        index === blueprints.length - 1 ? "failed" : "completed",
    }));
  }

  if (status === "interrupted") {
    return blueprints.map((step, index) => ({
      ...step,
      status:
        index === 0
          ? "completed"
          : index === 1
            ? "in_progress"
            : "pending",
    }));
  }

  return blueprints.map((step, index) => ({
    ...step,
    status:
      index === 0
        ? "completed"
        : index === 1
          ? "in_progress"
          : "pending",
  }));
}

function getDuplicateResultNote(name: string): string | null {
  switch (name) {
    case "load_battery_knowledge":
      return "Used to gather controlled planning context for the final reply.";
    case "load_pdf_test_method":
    case "load_knowledge_source":
      return "Used to load the requested reference details for the final reply.";
    case "search_knowledge_evidence_cards":
      return "Used to gather source-backed evidence for the final reply.";
    case "plan_standard_test":
    case "design_battery_protocol":
      return "Used to build the final experiment plan shown in the assistant response.";
    default:
      return null;
  }
}

function shouldSuppressDuplicateResultBody(name: string): boolean {
  return getDuplicateResultNote(name) !== null;
}

export const ToolCallBox = React.memo<ToolCallBoxProps>(
  ({
    toolCall,
    uiComponent,
    stream,
    graphId,
    actionRequest,
    reviewConfig,
    onResume,
    isLoading,
    entryIndex = 0,
  }) => {
    const [isExpanded, setIsExpanded] = useState(
      () => !!uiComponent || !!actionRequest
    );
    const [expandedArgs, setExpandedArgs] = useState<Record<string, boolean>>(
      {}
    );
    const [startedAt] = useState(() => Date.now());
    const [elapsedMs, setElapsedMs] = useState(0);
    const autoOpenedRef = useRef(false);
    const [isMounted, setIsMounted] = useState(false);
    const [shouldRenderDetails, setShouldRenderDetails] = useState(
      () => !!uiComponent || !!actionRequest
    );
    const [detailsVisible, setDetailsVisible] = useState(
      () => !!uiComponent || !!actionRequest
    );
    const [statusPulse, setStatusPulse] = useState(false);
    const previousStatusRef = useRef(toolCall.status || "completed");

    const { name, args, result, artifact, status } = useMemo(() => {
      return {
        name: toolCall.name || "Unknown Tool",
        args: toolCall.args || {},
        result: toolCall.result,
        artifact: toolCall.artifact,
        status: toolCall.status || "completed",
      };
    }, [toolCall]);

    const parsedResult = useMemo<Record<string, unknown> | null>(() => {
      if (typeof result !== "string") {
        return typeof result === "object" && result !== null
          ? (result as Record<string, unknown>)
          : null;
      }

      try {
        return JSON.parse(result) as Record<string, unknown>;
      } catch {
        return null;
      }
    }, [result]);

    const parsedArtifact = useMemo<Record<string, unknown> | null>(() => {
      if (typeof artifact === "string") {
        try {
          return JSON.parse(artifact) as Record<string, unknown>;
        } catch {
          return null;
        }
      }

      return typeof artifact === "object" && artifact !== null
        ? (artifact as Record<string, unknown>)
        : null;
    }, [artifact]);

    const displayPayload = parsedArtifact ?? parsedResult;

    const activityMeta = useMemo(
      () => getToolActivityMeta(name, args as Record<string, unknown>),
      [args, name]
    );
    const displayArgs = useMemo(
      () =>
        Object.entries(args).filter(
          ([key, value]) =>
            shouldDisplayArgValue(value) &&
            !shouldHideToolArgument(name, key, value)
        ),
      [args, name]
    );

    const executionSteps = useMemo(
      () => materializeExecutionSteps(status, activityMeta.steps),
      [activityMeta.steps, status]
    );

    const resultMarkdown = useMemo(() => {
      const markdown =
        displayPayload && typeof displayPayload["ui_markdown"] === "string"
          ? String(displayPayload["ui_markdown"])
          : parsedArtifact && typeof result === "string"
            ? result
            : null;

      return markdown ? sanitizeAssistantDisplayText(markdown) : null;
    }, [displayPayload, parsedArtifact, result]);

    const resultChartSvg =
      displayPayload && typeof displayPayload["chart_svg"] === "string"
        ? String(displayPayload["chart_svg"])
        : null;

    const resultChartTitle =
      displayPayload && typeof displayPayload["chart_title"] === "string"
        ? String(displayPayload["chart_title"])
        : null;

    const resultSummaryChartSvg =
      displayPayload && typeof displayPayload["summary_chart_svg"] === "string"
        ? String(displayPayload["summary_chart_svg"])
        : null;

    const resultSummaryChartTitle =
      displayPayload &&
      typeof displayPayload["summary_chart_title"] === "string"
        ? String(displayPayload["summary_chart_title"])
        : null;
    const isErrorResult = useMemo(() => {
      if (status === "error") {
        return true;
      }
      return displayPayload?.status === "error";
    }, [displayPayload, status]);
    const duplicateResultNote = useMemo(() => getDuplicateResultNote(name), [name]);
    const suppressDuplicateResultBody = useMemo(
      () => shouldSuppressDuplicateResultBody(name),
      [name]
    );

    const parsedCyclerPreview = useMemo(() => {
      if (name !== "parse_raw_cycler_export" || !displayPayload) {
        return null;
      }

      const previewRows = Array.isArray(displayPayload["preview_rows"])
        ? displayPayload["preview_rows"].filter(
            (row): row is Record<string, unknown> =>
              typeof row === "object" && row !== null
          )
        : [];
      const canonicalColumns = Array.isArray(displayPayload["canonical_columns"])
        ? displayPayload["canonical_columns"]
            .filter((value): value is string => typeof value === "string")
        : [];
      const warnings = Array.isArray(displayPayload["warnings"])
        ? displayPayload["warnings"]
            .filter((value): value is string => typeof value === "string")
        : [];

      return {
        adapterVendor:
          typeof displayPayload["adapter_vendor"] === "string"
            ? String(displayPayload["adapter_vendor"])
            : "Unknown",
        sourceFile:
          typeof displayPayload["source_file"] === "string"
            ? String(displayPayload["source_file"])
            : "Unknown",
        rowCount:
          typeof displayPayload["row_count"] === "number"
            ? displayPayload["row_count"]
            : null,
        cycleCount:
          typeof displayPayload["cycle_count"] === "number"
            ? displayPayload["cycle_count"]
            : null,
        datasetKind:
          typeof displayPayload["dataset_kind"] === "string"
            ? String(displayPayload["dataset_kind"])
            : "unknown",
        fieldSummaryLabel:
          typeof displayPayload["field_summary_label"] === "string"
            ? String(displayPayload["field_summary_label"])
            : "Recognized fields",
        previewOnly: displayPayload["preview_only"] === true,
        canonicalColumns,
        previewRows,
        warnings,
      };
    }, [displayPayload, name]);

    const showCellCatalogPanel = useMemo(() => {
      if (!parsedResult) return false;
      return (
        name === "search_imported_cell_catalog" ||
        name === "load_imported_cell_record"
      );
    }, [name, parsedResult]);

    const statusIcon = useMemo(() => {
      switch (status) {
        case "completed":
          return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
        case "error":
          return <AlertCircle className="h-4 w-4 text-destructive" />;
        case "pending":
          return <Loader2 className="h-4 w-4 animate-spin text-amber-600" />;
        case "interrupted":
          return <StopCircle className="h-4 w-4 text-orange-500" />;
        default:
          return <Terminal className="h-4 w-4 text-muted-foreground" />;
      }
    }, [status]);

    const statusLabel = useMemo(() => {
      switch (status) {
        case "completed":
          return "Completed";
        case "error":
          return "Error";
        case "pending":
          return "Running";
        case "interrupted":
          return "Interrupted";
        default:
          return "Queued";
      }
    }, [status]);

    const hasContent = Boolean(
      result ||
      artifact ||
        displayArgs.length > 0 ||
        status === "pending"
    );

    const rawResult = useMemo(() => {
      const previewPayload =
        parsedArtifact ??
        parsedResult ??
        (typeof result === "string" ? result : result ?? "");

      const sanitizedPreview = sanitizePayloadForRawPreview(previewPayload);
      if (typeof sanitizedPreview === "string") {
        return sanitizeAssistantDisplayText(sanitizedPreview);
      }

      return sanitizedPreview
        ? sanitizeAssistantDisplayText(
            JSON.stringify(sanitizedPreview, null, 2)
          )
        : "";
    }, [parsedArtifact, parsedResult, result]);

    const toggleExpanded = useCallback(() => {
      setIsExpanded((prev) => !prev);
    }, []);

    const toggleArgExpanded = useCallback((argKey: string) => {
      setExpandedArgs((prev) => ({
        ...prev,
        [argKey]: !prev[argKey],
      }));
    }, []);

    useEffect(() => {
      if (status === "pending" || actionRequest || uiComponent) {
        autoOpenedRef.current = true;
        setIsExpanded(true);
      }
    }, [actionRequest, status, uiComponent]);

    useEffect(() => {
      if (
        status === "completed" &&
        autoOpenedRef.current &&
        !actionRequest &&
        !uiComponent
      ) {
        const timeoutId = window.setTimeout(() => {
          setIsExpanded(false);
          autoOpenedRef.current = false;
        }, 180);
        return () => window.clearTimeout(timeoutId);
      }
      return undefined;
    }, [actionRequest, status, uiComponent]);

    useEffect(() => {
      if (status === "pending") {
        setElapsedMs(Date.now() - startedAt);
        const intervalId = window.setInterval(() => {
          setElapsedMs(Date.now() - startedAt);
        }, 500);
        return () => window.clearInterval(intervalId);
      }
      setElapsedMs(Date.now() - startedAt);
      return undefined;
    }, [startedAt, status]);

    useEffect(() => {
      const animationFrame = window.requestAnimationFrame(() => {
        setIsMounted(true);
      });
      return () => window.cancelAnimationFrame(animationFrame);
    }, []);

    useEffect(() => {
      if (!hasContent) {
        setShouldRenderDetails(false);
        setDetailsVisible(false);
        return undefined;
      }

      if (isExpanded) {
        setShouldRenderDetails(true);
        const animationFrame = window.requestAnimationFrame(() => {
          setDetailsVisible(true);
        });
        return () => window.cancelAnimationFrame(animationFrame);
      }

      setDetailsVisible(false);
      const timeoutId = window.setTimeout(() => {
        setShouldRenderDetails(false);
      }, 260);
      return () => window.clearTimeout(timeoutId);
    }, [hasContent, isExpanded]);

    useEffect(() => {
      if (previousStatusRef.current === status) {
        return;
      }

      previousStatusRef.current = status;
      setStatusPulse(true);
      const timeoutId = window.setTimeout(() => {
        setStatusPulse(false);
      }, 320);
      return () => window.clearTimeout(timeoutId);
    }, [status]);

    return (
      <div
        className={cn(
          "overflow-hidden rounded-[16px] border border-[rgba(24,33,38,0.08)] bg-white transition-[opacity,transform,box-shadow,border-color] duration-300 ease-out",
          isMounted
            ? "translate-y-0 opacity-100"
            : "translate-y-2 opacity-0",
          statusPulse && "border-[rgba(24,33,38,0.14)] shadow-[0_10px_24px_rgba(24,33,38,0.06)]"
        )}
        style={{
          transitionDelay: `${Math.min(entryIndex * 60, 180)}ms`,
        }}
      >
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleExpanded}
          disabled={!hasContent}
          className="flex h-auto w-full items-center justify-between gap-3 rounded-none px-4 py-3 text-left transition-colors duration-200 hover:bg-[rgba(247,245,241,0.7)]"
        >
            <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.9)]">
              {statusIcon}
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-foreground">
                {activityMeta.title}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.9)] px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
              {statusLabel}
            </span>
            {hasContent &&
              (isExpanded ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ))}
          </div>
        </Button>

        {shouldRenderDetails && hasContent && (
          <div
            className={cn(
              "grid transition-[grid-template-rows,opacity] duration-300 ease-out",
              detailsVisible
                ? "grid-rows-[1fr] opacity-100"
                : "grid-rows-[0fr] opacity-0"
            )}
          >
            <div className="overflow-hidden">
              <div className="border-t border-[rgba(24,33,38,0.08)] px-4 py-4">
                <div className="text-xs text-muted-foreground">
                  {activityMeta.subtitle}
                </div>

                {activityMeta.chips.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {activityMeta.chips.map((chip) => (
                      <span
                        key={chip}
                        className="rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.9)] px-2.5 py-1 text-[10px] text-muted-foreground"
                      >
                        {chip}
                      </span>
                    ))}
                  </div>
                )}

                <ToolExecutionProgress
                  title="Progress"
                  description="Tool execution steps"
                  steps={executionSteps}
                  elapsedMs={elapsedMs}
                />

                {uiComponent && stream && graphId ? (
                  <div className="mt-4">
                    <LoadExternalComponent
                      key={uiComponent.id}
                      stream={stream}
                      message={uiComponent}
                      namespace={graphId}
                      meta={{ status, args, result: result ?? "No Result Yet" }}
                    />
                  </div>
                ) : actionRequest && onResume ? (
                  <div className="mt-4">
                    <ToolApprovalInterrupt
                      actionRequest={actionRequest}
                      reviewConfig={reviewConfig}
                      onResume={onResume}
                      isLoading={isLoading}
                    />
                  </div>
                ) : (
                  <div className="mt-4 space-y-4">
                    {displayArgs.length > 0 && (
                      <div>
                        <h4 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
                          Arguments
                        </h4>
                        <div className="space-y-2">
                          {displayArgs.map(([key, value]) => (
                            <div
                              key={key}
                              className="overflow-hidden rounded-[12px] border border-[rgba(24,33,38,0.08)]"
                            >
                              <button
                                type="button"
                                onClick={() => toggleArgExpanded(key)}
                                className="flex w-full items-center justify-between bg-[rgba(247,245,241,0.75)] px-3 py-2 text-left text-xs font-medium"
                              >
                                <span>{humanizeInternalIdentifier(key)}</span>
                                {expandedArgs[key] ? (
                                  <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                                )}
                              </button>
                              {expandedArgs[key] && (
                                <div className="border-t border-[rgba(24,33,38,0.08)] bg-white px-3 py-2">
                                  <pre className="whitespace-pre-wrap break-all text-xs leading-6 text-foreground">
                                    {typeof value === "string"
                                      ? value
                                      : JSON.stringify(value, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {result && (
                      <div>
                        {showCellCatalogPanel ? (
                          <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.72)] p-3">
                            <CellCatalogResultPanel
                              toolName={name}
                              payload={parsedResult || {}}
                            />
                          </div>
                        ) : parsedCyclerPreview ? (
                          <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.72)] p-3">
                            <div className="grid gap-3 rounded-[12px] bg-white p-4">
                              <div className="grid gap-2 text-xs text-foreground sm:grid-cols-2">
                                <div>
                                  <span className="text-muted-foreground">Adapter</span>
                                  <div className="mt-1 font-medium">
                                    {parsedCyclerPreview.adapterVendor}
                                  </div>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Rows / cycles</span>
                                  <div className="mt-1 font-medium">
                                    {parsedCyclerPreview.rowCount ?? "n/a"} /{" "}
                                    {parsedCyclerPreview.cycleCount ?? "n/a"}
                                  </div>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Dataset kind</span>
                                  <div className="mt-1 font-medium">
                                    {humanizeInternalIdentifier(
                                      parsedCyclerPreview.datasetKind
                                    )}
                                  </div>
                                </div>
                                <div className="sm:col-span-2">
                                  <span className="text-muted-foreground">Source</span>
                                  <div className="mt-1 break-all font-medium">
                                    {parsedCyclerPreview.sourceFile}
                                  </div>
                                </div>
                              </div>
                              {parsedCyclerPreview.canonicalColumns.length > 0 && (
                                <div className="rounded-[12px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.55)] p-3 text-xs leading-6 text-foreground">
                                  <span className="font-medium text-muted-foreground">
                                    {parsedCyclerPreview.fieldSummaryLabel}
                                  </span>
                                  <div className="mt-1">
                                    {parsedCyclerPreview.canonicalColumns.join(", ")}
                                  </div>
                                </div>
                              )}
                              {parsedCyclerPreview.previewOnly && (
                                <div className="rounded-[12px] border border-sky-200 bg-sky-50 p-3 text-xs leading-6 text-sky-950">
                                  Parsed from a spreadsheet preview or truncated upload, so this card shows an informational subset rather than a full ingest.
                                </div>
                              )}
                              {parsedCyclerPreview.warnings.length > 0 && (
                                <div className="rounded-[12px] border border-amber-200 bg-amber-50 p-3 text-xs leading-6 text-amber-950">
                                  <span className="font-medium">Warnings</span>
                                  <ul className="mt-1 list-disc pl-4">
                                    {parsedCyclerPreview.warnings.map((warning) => (
                                      <li key={warning}>{warning}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {parsedCyclerPreview.previewRows.length > 0 && (
                                <div className="overflow-x-auto rounded-[12px] border border-[rgba(24,33,38,0.08)] bg-white p-3">
                                  <table className="w-full border-collapse text-left text-xs leading-6">
                                    <thead>
                                      <tr className="border-b border-[rgba(24,33,38,0.08)] text-muted-foreground">
                                        {Object.keys(parsedCyclerPreview.previewRows[0]).map(
                                          (column) => (
                                            <th
                                              key={column}
                                              className="px-2 py-2 font-medium"
                                            >
                                              {humanizeInternalIdentifier(column)}
                                            </th>
                                          )
                                        )}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {parsedCyclerPreview.previewRows.map((row, rowIndex) => (
                                        <tr
                                          key={`preview-row-${rowIndex}`}
                                          className="border-b border-[rgba(24,33,38,0.06)] last:border-b-0"
                                        >
                                          {Object.entries(row).map(([column, value]) => (
                                            <td
                                              key={`${rowIndex}-${column}`}
                                              className="px-2 py-2 text-foreground"
                                            >
                                              {value === null || value === undefined
                                                ? "n/a"
                                                : String(value)}
                                            </td>
                                          ))}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              )}
                            </div>
                          </div>
                        ) : suppressDuplicateResultBody &&
                          !isErrorResult &&
                          !resultChartSvg &&
                          !resultSummaryChartSvg ? (
                          <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.72)] p-3 text-sm text-muted-foreground">
                            {duplicateResultNote}
                          </div>
                        ) : resultMarkdown ||
                          resultChartSvg ||
                          resultSummaryChartSvg ? (
                          <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.72)] p-3">
                            {resultMarkdown && (
                              <div className="rounded-[12px] bg-white p-4">
                                <MarkdownContent content={resultMarkdown} />
                              </div>
                            )}
                            {resultChartSvg && (
                              <div className="mt-3 rounded-[12px] border border-[rgba(24,33,38,0.08)] bg-white p-3">
                                {resultChartTitle && (
                                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                                    {resultChartTitle}
                                  </p>
                                )}
                                <div
                                  className="overflow-x-auto"
                                  dangerouslySetInnerHTML={{ __html: resultChartSvg }}
                                />
                              </div>
                            )}
                            {resultSummaryChartSvg && (
                              <div className="mt-3 rounded-[12px] border border-[rgba(24,33,38,0.08)] bg-white p-3">
                                {resultSummaryChartTitle && (
                                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                                    {resultSummaryChartTitle}
                                  </p>
                                )}
                                <div
                                  className="overflow-x-auto"
                                  dangerouslySetInnerHTML={{
                                    __html: resultSummaryChartSvg,
                                  }}
                                />
                              </div>
                            )}
                          </div>
                        ) : rawResult ? (
                          <pre className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.72)] px-3 py-3 text-xs leading-6 text-foreground">
                            {rawResult}
                          </pre>
                        ) : (
                          <div className="rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.72)] p-3 text-sm text-muted-foreground">
                            {duplicateResultNote ?? "Tool output captured for the assistant response."}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }
);

ToolCallBox.displayName = "ToolCallBox";
